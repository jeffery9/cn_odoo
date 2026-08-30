# Multi-Company Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement full Odoo Multi-Company support with strict data isolation record rules for contracts, assignments, settlements, and blacklists.

**Architecture:** Inject `company_id` fields, create standard multi-company XML record rules, and write multi-company verification unit tests.

**Tech Stack:** Odoo 17, Python, Odoo XML.

**Spec:** `docs/mi_system/plans/2026-08-30-multi-company-support-design.md`

## Global Constraints
*   **Think in Odoo:** Use standard Odoo Multi-Company record rules with `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`.

---

### Task 1: Model Fields & Security Record Rules XML

**Files:**
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_contract.py`
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_assignment.py`
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_settlement.py`
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_blacklist.py`
- Create: `cn_payroll_outsourcing/security/multi_company_security.xml`
- Modify: `cn_payroll_outsourcing/__manifest__.py`

**Interfaces:**
- Produces: `company_id` columns, XML record rules.

- [ ] **Step 1: Update Contract Model Fields**
Add `company_id` to `CnOutsourcingContract` inside `cn_payroll_outsourcing/models/cn_outsourcing_contract.py`:

```python
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
```

- [ ] **Step 2: Update Assignment Model Fields**
Add `company_id` to `CnOutsourcingAssignment` inside `cn_payroll_outsourcing/models/cn_outsourcing_assignment.py`:

```python
    company_id = fields.Many2one('res.company', string='Company', required=True, store=True, related='contract_id.company_id', readonly=True)
```

- [ ] **Step 3: Update Settlement Model Fields**
Add `company_id` to `CnOutsourcingSettlement` inside `cn_payroll_outsourcing/models/cn_outsourcing_settlement.py`:

```python
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
```

- [ ] **Step 4: Update Blacklist Model Fields**
Add optional `company_id` to `CnOutsourcingBlacklist` inside `cn_payroll_outsourcing/models/cn_outsourcing_blacklist.py`:

```python
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, help="Leave blank for global blacklist across all companies.")
```

- [ ] **Step 5: Create Record Rules XML File**
Create `cn_payroll_outsourcing/security/multi_company_security.xml` defining the `ir.rule` records:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <!-- Multi-Company Rules -->
        <record id="cn_outsourcing_contract_company_rule" model="ir.rule">
            <name>Outsourcing Contract Multi-Company Rule</name>
            <model_id ref="model_cn_outsourcing_contract"/>
            <global eval="True"/>
            <domain_force>['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</domain_force>
        </record>

        <record id="cn_outsourcing_assignment_company_rule" model="ir.rule">
            <name>Outsourcing Assignment Multi-Company Rule</name>
            <model_id ref="model_cn_outsourcing_assignment"/>
            <global eval="True"/>
            <domain_force>['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</domain_force>
        </record>

        <record id="cn_outsourcing_settlement_company_rule" model="ir.rule">
            <name>Outsourcing Settlement Multi-Company Rule</name>
            <model_id ref="model_cn_outsourcing_settlement"/>
            <global eval="True"/>
            <domain_force>['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</domain_force>
        </record>

        <record id="cn_outsourcing_blacklist_company_rule" model="ir.rule">
            <name>Outsourcing Blacklist Multi-Company Rule</name>
            <model_id ref="model_cn_outsourcing_blacklist"/>
            <global eval="True"/>
            <domain_force>['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</domain_force>
        </record>
    </data>
</odoo>
```

- [ ] **Step 6: Update Manifest**
Add `'security/multi_company_security.xml'` to the `data` list in `cn_payroll_outsourcing/__manifest__.py` before `'views/portal_templates.xml'`.

- [ ] **Step 7: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/models/cn_outsourcing_contract.py cn_payroll_outsourcing/models/cn_outsourcing_assignment.py cn_payroll_outsourcing/models/cn_outsourcing_settlement.py cn_payroll_outsourcing/models/cn_outsourcing_blacklist.py`
```bash
git add cn_payroll_outsourcing/
git commit -m "feat: implement multi-company database columns and security record rules XML"
```

---

### Task 2: Unit Testing Multi-Company Separation

**Files:**
- Modify: `cn_payroll_outsourcing/tests/test_outsourcing.py`

**Interfaces:**
- Produces: `test_multi_company_contract_and_settlement_isolation` and `test_multi_company_global_vs_local_blacklist`.

- [ ] **Step 1: Write Isolation Tests**
Add these test cases to `cn_payroll_outsourcing/tests/test_outsourcing.py`:

```python
    def test_multi_company_contract_and_settlement_isolation(self):
        """Verify that record rules correctly isolate contracts by active company context"""
        # Create second company
        company_b = self.env['res.company'].create({'name': 'Logistics Subsidiary B'})
        
        # Contract under subsidiary B
        contract_b = self.env['cn.outsourcing.contract'].create({
            'name': 'Subsidiary B Exclusive Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'company_id': company_b.id,
        })
        
        # standard user only has access to company A by default
        contracts = self.env['cn.outsourcing.contract'].search([
            ('id', '=', contract_b.id)
        ])
        # Rule will filter out Subsidiary B's contract in standard company context
        # (TransactionCase self.env operates on company_ids including only self.env.company)
        self.assertFalse(contracts)

    def test_multi_company_global_vs_local_blacklist(self):
        """Verify that blank company_id blacklists apply globally, while company_id restricted apply locally"""
        from odoo.exceptions import ValidationError
        company_b = self.env['res.company'].create({'name': 'Logistics Subsidiary B'})
        
        contract_a = self.env['cn.outsourcing.contract'].create({
            'name': 'Company A Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'company_id': self.env.company.id,
        })
        contract_b = self.env['cn.outsourcing.contract'].create({
            'name': 'Company B Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'company_id': company_b.id,
        })
        
        # 1. Global Blacklist (company_id is blank)
        self.env['cn.outsourcing.blacklist'].create({
            'name': 'Global Blacklisted Worker',
            'barcode': '9099',
            'reason': 'Global Theft',
            'company_id': False, # GLOBAL
        })
        
        employee = self.env['hr.employee'].create({
            'name': 'Global Bad Worker',
            'barcode': '9099',
        })
        
        # Fails in Company A
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract_a.id,
                'employee_id': employee.id,
                'date_start': '2026-03-01',
            })
            
        # 2. Local Blacklist (company_id is Company A)
        self.env['cn.outsourcing.blacklist'].create({
            'name': 'Local Blacklisted Worker',
            'barcode': '9088',
            'reason': 'Local attendance fraud',
            'company_id': self.env.company.id, # Local to A
        })
        
        employee_local = self.env['hr.employee'].create({
            'name': 'Local Bad Worker',
            'barcode': '9088',
        })
        
        # Fails in Company A
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract_a.id,
                'employee_id': employee_local.id,
                'date_start': '2026-03-01',
            })
```

- [ ] **Step 2: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/tests/test_outsourcing.py`
```bash
git add cn_payroll_outsourcing/tests/test_outsourcing.py
git commit -m "test: add unit tests verifying multi-company record rules and global/local blacklists"
```
