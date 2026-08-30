# Worker Blacklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `cn.outsourcing.blacklist` model, enforce multi-dimensional identity matching validations on contract assignments, and write corresponding tests.

**Architecture:** Create `cn.outsourcing.blacklist` model, add security access configuration, inject the check domain search inside `cn.outsourcing.assignment._check_worker_qualifications()`, and add verification test cases.

**Tech Stack:** Odoo 17, Python.

**Spec:** `docs/mi_system/plans/2026-08-30-worker-blacklist-design.md`

## Global Constraints
*   **Think in Odoo:** Run active server-side constraint checks on save (`@api.constrains`).
*   **Decoupling:** Implement checks without affecting core `hr.employee` primary configurations outside the blacklist matching.

---

### Task 1: Blacklist Model Definition & Security Access

**Files:**
- Create: `cn_payroll_outsourcing/models/cn_outsourcing_blacklist.py`
- Modify: `cn_payroll_outsourcing/models/__init__.py`
- Modify: `cn_payroll_outsourcing/security/ir.model.access.csv`

**Interfaces:**
- Produces: `cn.outsourcing.blacklist` table.

- [ ] **Step 1: Create Blacklist Model**

```python
# cn_payroll_outsourcing/models/cn_outsourcing_blacklist.py
from odoo import models, fields

class CnOutsourcingBlacklist(models.Model):
    _name = 'cn.outsourcing.blacklist'
    _description = 'Enterprise Outsourcing Blacklist'

    name = fields.Char(required=True, string='Worker Name')
    id_card_num = fields.Char(string='ID Card Number')
    barcode = fields.Char(string='Barcode')
    mobile = fields.Char(string='Mobile Phone')
    reason = fields.Text(required=True, string='Reason for Blacklist')
    active = fields.Boolean(default=True, string='Active')
```

- [ ] **Step 2: Update Init**
Import `cn_outsourcing_blacklist` in `cn_payroll_outsourcing/models/__init__.py`.

- [ ] **Step 3: Update Security Access**
Add `access_cn_outsourcing_blacklist_manager,cn.outsourcing.blacklist.manager,model_cn_outsourcing_blacklist,base.group_user,1,1,1,1` to `cn_payroll_outsourcing/security/ir.model.access.csv`.

- [ ] **Step 4: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/models/cn_outsourcing_blacklist.py`
```bash
git add cn_payroll_outsourcing/
git commit -m "feat: implement corporate worker blacklist data model and security access"
```

---

### Task 2: Implement Assignment Constraint Hook

**Files:**
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_assignment.py`

**Interfaces:**
- Produces: Proactive check in `_check_worker_qualifications()`.

- [ ] **Step 1: Inject Blacklist Check in `cn_outsourcing_assignment.py`**
Append this validation logic to `_check_worker_qualifications`:

```python
            # 3. Validate against Enterprise Blacklist
            domain = []
            if employee.barcode:
                domain.append(('barcode', '=', employee.barcode))
            if employee.identification_id:
                domain.append(('id_card_num', '=', employee.identification_id))
            if employee.mobile_phone:
                domain.append(('mobile', '=', employee.mobile_phone))
                
            if domain:
                # Build OR condition for multiple matches
                if len(domain) > 1:
                    domain = ['|'] * (len(domain) - 1) + domain
                # Enforce active blacklist records search
                domain = [('active', '=', True)] + domain
                if len(domain) > 1:
                    # Append AND
                    domain = ['&'] + domain
                
                blacklist_rec = self.env['cn.outsourcing.blacklist'].search(domain, limit=1)
                if blacklist_rec:
                    raise ValidationError(
                        f"Compliance Violation: Worker {employee.name} is on the Enterprise Blacklist! "
                        f"Reason: {blacklist_rec.reason}. Assignment is strictly rejected."
                    )
```

- [ ] **Step 2: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/models/cn_outsourcing_assignment.py`
```bash
git add cn_payroll_outsourcing/models/cn_outsourcing_assignment.py
git commit -m "feat: enforce active multi-dimensional blacklist checks during worker assignments"
```

---

### Task 3: Unit Testing Worker Blacklists

**Files:**
- Modify: `cn_payroll_outsourcing/tests/test_outsourcing.py`

- [ ] **Step 1: Write Blacklist Verification Tests**

Append this test case method to `TestOutsourcing`:
```python
    def test_worker_blacklist_multi_dimensional_blocking(self):
        """Verify that blacklisted workers are blocked from assignments by Barcode or ID Card"""
        from odoo.exceptions import ValidationError
        
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Operational Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
        })
        
        # Add a record to corporate blacklist
        self.env['cn.outsourcing.blacklist'].create({
            'name': 'Bad Worker',
            'barcode': '9009',
            'id_card_num': '110101199003071234',
            'reason': 'Theft of warehouse assets',
        })
        
        # 1. Block by Barcode match
        employee_barcode = self.env['hr.employee'].create({
            'name': 'John Doe',
            'barcode': '9009',
        })
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract.id,
                'employee_id': employee_barcode.id,
                'date_start': '2026-03-01',
            })
            
        # 2. Block by National ID Card match
        employee_id_card = self.env['hr.employee'].create({
            'name': 'Jane Doe',
            'identification_id': '110101199003071234',
        })
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract.id,
                'employee_id': employee_id_card.id,
                'date_start': '2026-03-01',
            })
```

- [ ] **Step 2: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/tests/test_outsourcing.py`
```bash
git add cn_payroll_outsourcing/tests/test_outsourcing.py
git commit -m "test: add TDD unit tests for multi-dimensional corporate blacklist blocking"
```
