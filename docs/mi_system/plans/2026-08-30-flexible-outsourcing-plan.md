# Flexible Outsourcing Assignments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement chronological date-ranged assignments (`cn.outsourcing.assignment`) and a rapid copy-paste bulk onboarding wizard (`cn.outsourcing.backfill.wizard`).

**Architecture:** Create assignments and wizards, rewrite `action_generate_lines` to filter attendance hours strictly within the active assignment date range, and write onboarding bulk parsers.

**Tech Stack:** Odoo 17, Python.

**Spec:** `docs/mi_system/plans/2026-08-30-flexible-outsourcing-design.md`

## Global Constraints
*   **Think in Odoo:** Rely on Odoo standard fields, wizards, and active record patterns.
*   **Decoupling:** Do not create hard dependencies. Access Odoo attendance models dynamically via registry.

---

### Task 1: Chronological Assignment Model & Settlement Filtering

**Files:**
- Modify: `cn_payroll_outsourcing/models/__init__.py`
- Create: `cn_payroll_outsourcing/models/cn_outsourcing_assignment.py`
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_settlement.py`
- Modify: `cn_payroll_outsourcing/security/ir.model.access.csv`

**Interfaces:**
- Produces: `cn.outsourcing.assignment` model, chronological filter query inside `action_generate_lines`.

- [ ] **Step 1: Create Assignment Model**

```python
# cn_payroll_outsourcing/models/cn_outsourcing_assignment.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CnOutsourcingAssignment(models.Model):
    _name = 'cn.outsourcing.assignment'
    _description = 'Labor Outsourcing Assignment'

    contract_id = fields.Many2one('cn.outsourcing.contract', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', required=True, string='Worker')
    date_start = fields.Date(required=True, string='Start Date')
    date_end = fields.Date(string='End Date')

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in recs:
            if rec.date_end and rec.date_start > rec.date_end:
                raise ValidationError("Start date cannot exceed end date.")
```

- [ ] **Step 2: Update Init**
Register `cn_outsourcing_assignment` in `cn_payroll_outsourcing/models/__init__.py`.

- [ ] **Step 3: Update `action_generate_lines` in `cn_outsourcing_settlement.py`**
Replace lines to query and filter workers based on active chronological assignments instead of static Many2many:

```python
        # Fetch active assignments for the contract
        assignments = self.env['cn.outsourcing.assignment'].search([
            ('contract_id', '=', self.contract_id.id),
        ])
        
        # Determine start/end date bounds of the period (YYYY-MM)
        period_start = fields.Date.from_string(f"{self.period}-01")
        # next month start minus one day
        year, month = map(int, self.period.split('-'))
        if month == 12:
            period_end = fields.Date.from_string(f"{year}-12-31")
        else:
            period_end = fields.Date.from_string(f"{year}-{month+1:02d}-01") - timedelta(days=1)
            
        for assignment in assignments:
            # Check overlap between assignment dates and the billing period
            start_overlap = max(period_start, assignment.date_start)
            end_overlap = period_end
            if assignment.date_end:
                end_overlap = min(period_end, assignment.date_end)
                
            if start_overlap > end_overlap:
                continue # No overlap this period
                
            employee = assignment.employee_id
            # Query attendance ...
```

- [ ] **Step 4: Update Security Access**
Add `access_cn_outsourcing_assignment_manager,cn.outsourcing.assignment.manager,model_cn_outsourcing_assignment,base.group_user,1,1,1,1` to `cn_payroll_outsourcing/security/ir.model.access.csv`.

- [ ] **Step 5: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/models/cn_outsourcing_assignment.py`
```bash
git add cn_payroll_outsourcing/
git commit -m "feat: implement chronological assignment tracking and active-window billing filtering"
```

---

### Task 2: Rapid Onboarding Backfill Wizard

**Files:**
- Modify: `cn_payroll_outsourcing/models/__init__.py`
- Create: `cn_payroll_outsourcing/models/cn_outsourcing_backfill_wizard.py`
- Modify: `cn_payroll_outsourcing/security/ir.model.access.csv`

**Interfaces:**
- Produces: `cn.outsourcing.backfill.wizard` with `action_onboard_bulk()`.

- [ ] **Step 1: Create Onboarding Wizard**

```python
# cn_payroll_outsourcing/models/cn_outsourcing_backfill_wizard.py
from odoo import models, fields, api

class CnOutsourcingBackfillWizard(models.TransientModel):
    _name = 'cn.outsourcing.backfill.wizard'
    _description = 'Rapid Backfill Onboarding Wizard'

    contract_id = fields.Many2one('cn.outsourcing.contract', required=True)
    date_start = fields.Date(required=True, default=fields.Date.today)
    attendance_settings_id = fields.Many2one('cn.attendance.settings', string='Target Policy')
    worker_raw_list = fields.Text(required=True, string='Worker Details (Name,Barcode - Line by Line)')

    def action_onboard_bulk(self):
        self.ensure_one()
        lines = self.worker_raw_list.strip().split('\n')
        for line in lines:
            if not line or ',' not in line:
                continue
            name, barcode = map(str.strip, line.split(',', 1))
            
            # 1. Create Employee
            employee = self.env['hr.employee'].create({
                'name': name,
                'barcode': barcode,
                'attendance_settings_id': self.attendance_settings_id.id if self.attendance_settings_id else False,
            })
            
            # 2. Register Assignment
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': self.contract_id.id,
                'employee_id': employee.id,
                'date_start': self.date_start,
            })
```

- [ ] **Step 2: Update Init & Security**
Register `cn_outsourcing_backfill_wizard` in `__init__.py`.
Add `access_cn_outsourcing_backfill_wizard,cn.outsourcing.backfill.wizard,model_cn_outsourcing_backfill_wizard,base.group_user,1,1,1,1` to `ir.model.access.csv`.

- [ ] **Step 3: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/models/cn_outsourcing_backfill_wizard.py`
```bash
git add cn_payroll_outsourcing/
git commit -m "feat: implement rapid bulk onboarding and backfill wizard"
```

---

### Task 3: Unit Testing Chronological Assignments and Backfills

**Files:**
- Modify: `cn_payroll_outsourcing/tests/test_outsourcing.py`

- [ ] **Step 1: Write Chronological and Backfill Unit Tests**

Add these methods to the `TestOutsourcing` class:
```python
    def test_chronological_assignment_hours_filtering(self):
        """Verify that mid-month transfers calculate and bill only active-range hours"""
        # Set up a contract and dynamic assignment
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Active Mid-Month',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'hourly_rate': 30.0,
        })
        
        # Worker active from 2024-03-01 to 2024-03-15
        self.env['cn.outsourcing.assignment'].create({
            'contract_id': contract.id,
            'employee_id': self.employee.id,
            'date_start': '2024-03-01',
            'date_end': '2024-03-15',
        })
        
        settlement = self.env['cn.outsourcing.settlement'].create({
            'name': 'SETTLE-MID',
            'contract_id': contract.id,
            'period': '2024-03',
        })
        settlement.action_generate_lines()
        
        self.assertEqual(len(settlement.line_ids), 1)
        self.assertEqual(settlement.line_ids[0].attendance_hours, 160.0)

    def test_rapid_backfill_bulk_onboarding_wizard(self):
        """Verify that wizard correctly bulk parses list, creates employees, and maps assignments"""
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Bulk Onboard',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
        })
        
        wizard = self.env['cn.outsourcing.backfill.wizard'].create({
            'contract_id': contract.id,
            'date_start': '2024-03-01',
            'worker_raw_list': "Zhao Liu,9006\nSun Qi,9007"
        })
        
        wizard.action_onboard_bulk()
        
        # Verify employees were created
        zhao = self.env['hr.employee'].search([('barcode', '=', '9006')])
        self.assertTrue(zhao)
        self.assertEqual(zhao.name, "Zhao Liu")
        
        # Verify assignment was linked
        assignment = self.env['cn.outsourcing.assignment'].search([('employee_id', '=', zhao.id)])
        self.assertTrue(assignment)
        self.assertEqual(assignment.contract_id.id, contract.id)
```

- [ ] **Step 2: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/tests/test_outsourcing.py`
```bash
git add cn_payroll_outsourcing/tests/test_outsourcing.py
git commit -m "test: add TDD unit tests for chronological assignments and rapid backfill wizards"
```
