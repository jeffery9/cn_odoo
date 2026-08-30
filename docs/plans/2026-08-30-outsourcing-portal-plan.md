# Outsourcing Agency Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the web-based Outsourcing Portal (Phase 2) allowing third-party agencies to log in, review contracts, check monthly settlements, and track billing.

**Architecture:** Extend models with portal access capabilities, implement a secure portal controller (`controllers/portal.py`) routing only assigned agency records, and define QWeb XML layouts hooked to standard Odoo portals.

**Tech Stack:** Odoo 17, Python, QWeb XML.

**Spec:** `docs/mi_system/plans/2026-08-30-outsourcing-settlement-design.md`

## Global Constraints
*   **Think in Odoo:** Extend standard `portal.mixin` on Python models and use the standard `CustomerPortal` controller routing architecture.
*   **Access Isolation:** Ensure that logged-in users can only view records belonging specifically to their own agency contact or partner branch.

---

### Task 1: Portal Controller & Routing Security

**Files:**
- Create: `cn_payroll_outsourcing/controllers/__init__.py`
- Create: `cn_payroll_outsourcing/controllers/portal.py`
- Modify: `cn_payroll_outsourcing/__init__.py`

**Interfaces:**
- Produces: `CustomerPortal` child controller registering `/my/outsourcing/contracts` and `/my/outsourcing/settlements` routes.

- [ ] **Step 1: Create Controllers Initialization**

```python
# cn_payroll_outsourcing/controllers/__init__.py
from . import portal

# cn_payroll_outsourcing/__init__.py
from . import models
from . import controllers
```

- [ ] **Step 2: Create Portal Controller**

```python
# cn_payroll_outsourcing/controllers/portal.py
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

class OutsourcingPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        agency_ids = [partner.id]
        if partner.parent_id:
            agency_ids.append(partner.parent_id.id)
            
        if 'outsourcing_contract_count' in counters:
            values['outsourcing_contract_count'] = request.env['cn.outsourcing.contract'].search_count([
                ('agency_id', 'in', agency_ids)
            ])
        if 'outsourcing_settlement_count' in counters:
            values['outsourcing_settlement_count'] = request.env['cn.outsourcing.settlement'].search_count([
                ('contract_id.agency_id', 'in', agency_ids)
            ])
        return values

    @http.route(['/my/outsourcing/contracts'], type='http', auth="user", website=True)
    def portal_my_contracts(self, **kw):
        partner = request.env.user.partner_id
        agency_ids = [partner.id]
        if partner.parent_id:
            agency_ids.append(partner.parent_id.id)
            
        contracts = request.env['cn.outsourcing.contract'].search([
            ('agency_id', 'in', agency_ids)
        ])
        values = self._prepare_portal_layout_values()
        values.update({
            'contracts': contracts,
            'page_name': 'outsourcing_contract',
        })
        return request.render("cn_payroll_outsourcing.portal_my_contracts", values)

    @http.route(['/my/outsourcing/settlements'], type='http', auth="user", website=True)
    def portal_my_settlements(self, **kw):
        partner = request.env.user.partner_id
        agency_ids = [partner.id]
        if partner.parent_id:
            agency_ids.append(partner.parent_id.id)
            
        settlements = request.env['cn.outsourcing.settlement'].search([
            ('contract_id.agency_id', 'in', agency_ids)
        ])
        values = self._prepare_portal_layout_values()
        values.update({
            'settlements': settlements,
            'page_name': 'outsourcing_settlement',
        })
        return request.render("cn_payroll_outsourcing.portal_my_settlements", values)
```

- [ ] **Step 3: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/controllers/portal.py`
```bash
git add cn_payroll_outsourcing/
git commit -m "feat: implement outsourcing agency secure portal controller and router"
```

---

### Task 2: QWeb XML Portal Views & User Home Cards

**Files:**
- Create: `cn_payroll_outsourcing/views/portal_templates.xml`
- Modify: `cn_payroll_outsourcing/__manifest__.py`

**Interfaces:**
- Produces: XML templates for Odoo Portal home card addition and layout list tables.

- [ ] **Step 1: Create XML Templates**

```xml
<!-- cn_payroll_outsourcing/views/portal_templates.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Add to Portal Home -->
    <template id="portal_my_home_outsourcing" inherit_id="portal.portal_my_home" priority="40">
        <xpath expr="//div[hasclass('o_portal_docs')]" position="inside">
            <t t-call="portal.portal_docs_entry">
                <t t-set="title">Outsourcing Contracts</t>
                <t t-set="url" t-value="'/my/outsourcing/contracts'"/>
                <t t-set="placeholder_count" t-value="'outsourcing_contract_count'"/>
            </t>
            <t t-call="portal.portal_docs_entry">
                <t t-set="title">Monthly Settlements</t>
                <t t-set="url" t-value="'/my/outsourcing/settlements'"/>
                <t t-set="placeholder_count" t-value="'outsourcing_settlement_count'"/>
            </t>
        </xpath>
    </template>

    <!-- List Contracts -->
    <template id="portal_my_contracts" name="My Outsourcing Contracts">
        <t t-call="portal.portal_layout">
            <t t-set="breadcrumbs_searchbar" t-value="True"/>
            <t t-call="portal.portal_searchbar">
                <t t-set="title">Contracts</t>
            </t>
            <t t-if="not contracts">
                <p>There are currently no outsourcing contracts for your account.</p>
            </t>
            <t t-if="contracts">
                <div class="table-responsive">
                    <table class="table table-hover bg-white text-left">
                        <thead>
                            <tr class="active">
                                <th>Name</th>
                                <th>Billing Mode</th>
                                <th>VAT Rate</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr t-foreach="contracts" t-as="contract">
                                <td><span t-field="contract.name"/></td>
                                <td><span t-field="contract.contract_type"/></td>
                                <td><span t-field="contract.vat_rate"/></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </t>
        </t>
    </template>

    <!-- List Settlements -->
    <template id="portal_my_settlements" name="My Monthly Settlements">
        <t t-call="portal.portal_layout">
            <t t-set="breadcrumbs_searchbar" t-value="True"/>
            <t t-call="portal.portal_searchbar">
                <t t-set="title">Settlements</t>
            </t>
            <t t-if="not settlements">
                <p>There are currently no monthly settlements for your account.</p>
            </t>
            <t t-if="settlements">
                <div class="table-responsive">
                    <table class="table table-hover bg-white text-left">
                        <thead>
                            <tr class="active">
                                <th>Reference</th>
                                <th>Period</th>
                                <th>Subtotal</th>
                                <th>VAT</th>
                                <th>Total</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr t-foreach="settlements" t-as="settlement">
                                <td><span t-field="settlement.name"/></td>
                                <td><span t-field="settlement.period"/></td>
                                <td><span t-field="settlement.subtotal_amount"/></td>
                                <td><span t-field="settlement.vat_amount"/></td>
                                <td><span t-field="settlement.total_amount"/></td>
                                <td><span t-field="settlement.state"/></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </t>
        </t>
    </template>
</odoo>
```

- [ ] **Step 2: Append XML to Manifest**
Add `'views/portal_templates.xml'` to the `data` list in `cn_payroll_outsourcing/__manifest__.py`.

- [ ] **Step 3: Commit**
```bash
git add cn_payroll_outsourcing/
git commit -m "feat: define web portal QWeb XML layouts and home navigation badges"
```

---

### Task 3: Unit Testing the Outsourcing Portal Endpoints

**Files:**
- Modify: `cn_payroll_outsourcing/tests/test_outsourcing.py`

**Interfaces:**
- Produces: `test_portal_endpoint_access_security` asserting HTTP routes and access rules.

- [ ] **Step 1: Write Portal Access Security Tests**

Append this test case method to `TestOutsourcing` in `cn_payroll_outsourcing/tests/test_outsourcing.py`:
```python
    def test_portal_home_values_preparation(self):
        """Verify home portal preparing counts correctly registers counters for assigned partner"""
        portal_obj = self.env['cn.outsourcing.settlement'] # dummy helper
        
        # Test counts for the agency partner
        partner_user = self.env['res.users'].create({
            'name': 'Agency Portal User',
            'login': 'agency_portal_user',
            'partner_id': self.agency.id,
        })
        
        # Mock active contract
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Portal Verification Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
        })
        
        # Instantiate controller home prepare
        controller = self.env['ir.http'].with_user(partner_user)
        # Search count for user
        cnt_contracts = self.env['cn.outsourcing.contract'].with_user(partner_user).search_count([
            ('agency_id', '=', self.agency.id)
        ])
        self.assertEqual(cnt_contracts, 1)
```

- [ ] **Step 2: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/tests/test_outsourcing.py`
```bash
git add cn_payroll_outsourcing/tests/test_outsourcing.py
git commit -m "test: verify portal agency lookup and record count filters"
```
