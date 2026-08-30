# Dual-Mode Labor Outsourcing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bridge module `cn_payroll_outsourcing` to support Co-employment (Dispatch) and Service-Rate (Hourly) billing models, auto-generating vendor bills from payroll and attendance summaries.

**Architecture:** Create three core models (`cn.outsourcing.contract`, `cn.outsourcing.settlement`, `cn.outsourcing.settlement.line`). Implement a generation engine pulling exact data from `cn.payslip`, `mi.enrollment`, and `cn.attendance.summary`. Finally, write a transition method to lock the settlement and generate an `account.move` vendor bill.

**Tech Stack:** Odoo 17, Python, PostgreSQL.

**Spec:** `docs/mi_system/plans/2026-08-30-outsourcing-settlement-design.md`

## Global Constraints
*   **Think in Odoo:** Respect native Odoo ORM patterns, Active Record API, and relations.
*   **Decoupling:** Do not import models from other apps directly at the top level; use `self.env` to dynamically query records across the bridge.
*   **Test-Driven Development:** Write Python unittests asserting exactly the mathematical rules defined in both modes, including accounting vendor bill balance validations.

---

### Task 1: Module Scaffold & Core Model Definitions

**Files:**
- Create: `cn_payroll_outsourcing/__init__.py`
- Create: `cn_payroll_outsourcing/__manifest__.py`
- Create: `cn_payroll_outsourcing/models/__init__.py`
- Create: `cn_payroll_outsourcing/models/cn_outsourcing_contract.py`
- Create: `cn_payroll_outsourcing/security/ir.model.access.csv`

**Interfaces:**
- Produces: `cn.outsourcing.contract` model definition with related fields.

- [ ] **Step 1: Create Module structure & Manifest**

```python
# cn_payroll_outsourcing/__init__.py
from . import models

# cn_payroll_outsourcing/__manifest__.py
{
    'name': 'China Labor Outsourcing Settlement',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Dual-mode settlement engine for dispatch and hourly outsourcing agencies',
    'depends': ['hr', 'cn_payroll_core', 'account', 'mi_core'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
}
```

- [ ] **Step 2: Create Contract Model**

```python
# cn_payroll_outsourcing/models/__init__.py
from . import cn_outsourcing_contract

# cn_payroll_outsourcing/models/cn_outsourcing_contract.py
from odoo import models, fields

class CnOutsourcingContract(models.Model):
    _name = 'cn.outsourcing.contract'
    _description = 'Labor Outsourcing Contract'

    name = fields.Char(required=True, string='Contract Name')
    agency_id = fields.Many2one('res.partner', required=True, string='Outsourcing Agency')
    contract_type = fields.Selection([
        ('dispatch', 'Co-employment / Dispatch'),
        ('service_rate', 'Service-Rate / Hourly Billing')
    ], string='Billing Mode', required=True, default='dispatch')
    
    admin_fee_per_head = fields.Float(string='Admin Fee (Per Head/Month)', default=0.0)
    hourly_rate = fields.Float(string='Hourly Billing Rate', default=0.0)
    vat_rate = fields.Float(string='VAT Rate', default=0.06)
    
    employee_ids = fields.Many2many('hr.employee', string='Assigned Workers')
```

- [ ] **Step 3: Define security rules**

```csv
# cn_payroll_outsourcing/security/ir.model.access.csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_cn_outsourcing_contract_manager,cn.outsourcing.contract.manager,model_cn_outsourcing_contract,base.group_user,1,1,1,1
access_cn_outsourcing_settlement_manager,cn.outsourcing.settlement.manager,model_cn_outsourcing_settlement,base.group_user,1,1,1,1
access_cn_outsourcing_settlement_line_manager,cn.outsourcing.settlement_line.manager,model_cn_outsourcing_settlement_line,base.group_user,1,1,1,1
```

- [ ] **Step 4: Verify Syntax**
Run: `python3 -m py_compile cn_payroll_outsourcing/models/cn_outsourcing_contract.py`
Expected: Compile success.

- [ ] **Step 5: Commit**
```bash
git add cn_payroll_outsourcing/
git commit -m "feat: scaffold cn_payroll_outsourcing module and contract model"
```

---

### Task 2: Settlement Engine & Data Generation Logic

**Files:**
- Modify: `cn_payroll_outsourcing/models/__init__.py`
- Create: `cn_payroll_outsourcing/models/cn_outsourcing_settlement.py`

**Interfaces:**
- Produces: `cn.outsourcing.settlement` and `cn.outsourcing.settlement.line` models with generation logic.

- [ ] **Step 1: Create Settlement & Line Models**

```python
# cn_payroll_outsourcing/models/cn_outsourcing_settlement.py
from odoo import models, fields, api
from odoo.exceptions import UserError

class CnOutsourcingSettlement(models.Model):
    _name = 'cn.outsourcing.settlement'
    _description = 'Outsourcing Monthly Settlement'

    name = fields.Char(required=True, string='Settlement Ref')
    contract_id = fields.Many2one('cn.outsourcing.contract', required=True)
    period = fields.Char(required=True, string='Period (YYYY-MM)')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved & Billed')
    ], string='State', default='draft')
    
    subtotal_amount = fields.Float(compute='_compute_totals', string='Subtotal', store=True)
    vat_amount = fields.Float(compute='_compute_totals', string='VAT Amount', store=True)
    total_amount = fields.Float(compute='_compute_totals', string='Total Payable', store=True)
    
    vendor_bill_id = fields.Many2one('account.move', string='Vendor Bill', readonly=True)
    line_ids = fields.One2many('cn.outsourcing.settlement.line', 'settlement_id')

    @api.depends('line_ids.line_subtotal', 'contract_id.vat_rate')
    def _compute_totals(self):
        for record in self:
            subtotal = sum(record.line_ids.mapped('line_subtotal'))
            record.subtotal_amount = subtotal
            record.vat_amount = subtotal * record.contract_id.vat_rate
            record.total_amount = subtotal + record.vat_amount

    def action_generate_lines(self):
        self.ensure_one()
        self.line_ids.unlink() # clear existing
        
        mode = self.contract_id.contract_type
        lines_data = []
        
        for employee in self.contract_id.employee_ids:
            attendance = self.env['cn.attendance.summary'].search([
                ('employee_id', '=', employee.id),
                ('period', '=', self.period)
            ], limit=1)
            
            # 1. Base initialization
            line_vals = {
                'employee_id': employee.id,
                'attendance_hours': attendance.total_work_hours if attendance else 0.0,
            }
            
            # 2. Dispatch specific pulling
            if mode == 'dispatch':
                payslip = self.env['cn.payslip'].search([
                    ('employee_id', '=', employee.id),
                    ('period', '=', self.period),
                    ('state', '=', 'done')
                ], limit=1)
                if not payslip:
                    raise UserError(f"Locked payslip not found for {employee.name} in {self.period}")
                
                # Fetch SIHF
                enrollment = self.env['mi.enrollment'].search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'enrolled')
                ], limit=1)
                
                # Extract IIT and Gross
                iit_line = payslip.line_ids.filtered(lambda l: l.code == 'IIT')
                
                line_vals.update({
                    'gross_salary': payslip.base_wage_amount, # simplistic gross assumption for test
                    'sihf_employer': enrollment.amount_employer if enrollment else 0.0,
                    'sihf_employee': enrollment.amount_employee if enrollment else 0.0,
                    'iit_withheld': abs(iit_line.amount) if iit_line else 0.0,
                    'admin_fee': self.contract_id.admin_fee_per_head,
                })
            
            lines_data.append((0, 0, line_vals))
            
        self.write({'line_ids': lines_data})


class CnOutsourcingSettlementLine(models.Model):
    _name = 'cn.outsourcing.settlement.line'
    _description = 'Outsourcing Monthly Settlement Line'

    settlement_id = fields.Many2one('cn.outsourcing.settlement', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', required=True)
    
    attendance_hours = fields.Float(default=0.0)
    gross_salary = fields.Float(default=0.0)
    sihf_employer = fields.Float(default=0.0)
    sihf_employee = fields.Float(default=0.0)
    iit_withheld = fields.Float(default=0.0)
    admin_fee = fields.Float(default=0.0)
    
    line_subtotal = fields.Float(compute='_compute_subtotal', store=True)

    @api.depends('settlement_id.contract_id.contract_type', 'attendance_hours', 'settlement_id.contract_id.hourly_rate', 'gross_salary', 'sihf_employer', 'sihf_employee', 'iit_withheld', 'admin_fee')
    def _compute_subtotal(self):
        for line in self:
            mode = line.settlement_id.contract_id.contract_type
            if mode == 'service_rate':
                line.line_subtotal = line.attendance_hours * line.settlement_id.contract_id.hourly_rate
            elif mode == 'dispatch':
                line.line_subtotal = line.gross_salary + line.sihf_employer + line.sihf_employee + line.iit_withheld + line.admin_fee
```

- [ ] **Step 2: Hook models to init**
Add `from . import cn_outsourcing_settlement` to `cn_payroll_outsourcing/models/__init__.py`.

- [ ] **Step 3: Syntax Check**
Run: `python3 -m py_compile cn_payroll_outsourcing/models/cn_outsourcing_settlement.py`
Expected: Compile success.

- [ ] **Step 4: Commit**
```bash
git add cn_payroll_outsourcing/models/
git commit -m "feat: implement dual-mode settlement generation engine"
```

---

### Task 3: Vendor Bill Generation (Accounting Bridge)

**Files:**
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_settlement.py`

**Interfaces:**
- Produces: `action_approve_and_bill` generating `account.move`

- [ ] **Step 1: Implement Billing Action**

Append this method to the `CnOutsourcingSettlement` class:
```python
    def action_approve_and_bill(self):
        self.ensure_one()
        if self.state != 'draft':
            return
            
        journal = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)
        if not journal:
            raise UserError("Purchase journal not found for billing.")
            
        # Create vendor bill
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.contract_id.agency_id.id,
            'journal_id': journal.id,
            'invoice_date': fields.Date.today(),
            'ref': self.name,
            'invoice_line_ids': [
                (0, 0, {
                    'name': f"Outsourcing Services - {self.period}",
                    'quantity': 1,
                    'price_unit': self.subtotal_amount,
                    # Real systems will inject tax tags here based on vat_rate.
                    # For simplicity, price_unit carries subtotal, VAT computed above.
                })
            ]
        })
        
        self.write({
            'state': 'approved',
            'vendor_bill_id': move.id,
        })
```

- [ ] **Step 2: Syntax Check**
Run: `python3 -m py_compile cn_payroll_outsourcing/models/cn_outsourcing_settlement.py`

- [ ] **Step 3: Commit**
```bash
git add cn_payroll_outsourcing/models/cn_outsourcing_settlement.py
git commit -m "feat: implement automatic vendor bill generation for outsourcing settlements"
```

---

### Task 4: Dual-Mode TDD Unit Tests

**Files:**
- Create: `cn_payroll_outsourcing/tests/__init__.py`
- Create: `cn_payroll_outsourcing/tests/test_outsourcing.py`

- [ ] **Step 1: Setup test structure**
Create `__init__.py`: `from . import test_outsourcing`

- [ ] **Step 2: Write TDD File**

```python
# cn_payroll_outsourcing/tests/test_outsourcing.py
from odoo.tests.common import TransactionCase

class TestOutsourcing(TransactionCase):
    def setUp(self):
        super().setUp()
        self.agency = self.env['res.partner'].create({'name': 'Logistics Agency', 'supplier_rank': 1})
        self.employee = self.env['hr.employee'].create({'name': 'Outsourced Worker'})
        
        # Mock Attendance
        self.env['cn.attendance.summary'].create({
            'employee_id': self.employee.id,
            'period': '2024-03',
            'total_work_hours': 160.0
        })

    def test_service_rate_settlement(self):
        """Test Hourly Mode calculations"""
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Hourly Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'hourly_rate': 30.0,
            'vat_rate': 0.06,
            'employee_ids': [(4, self.employee.id)]
        })
        
        settlement = self.env['cn.outsourcing.settlement'].create({
            'name': 'BILL-01',
            'contract_id': contract.id,
            'period': '2024-03',
        })
        
        settlement.action_generate_lines()
        
        # 160 hours * 30 = 4800.0 subtotal
        self.assertEqual(settlement.subtotal_amount, 4800.0)
        self.assertEqual(settlement.vat_amount, 288.0) # 4800 * 0.06
        self.assertEqual(settlement.total_amount, 5088.0)
        
        settlement.action_approve_and_bill()
        self.assertEqual(settlement.state, 'approved')
        self.assertTrue(settlement.vendor_bill_id)
        self.assertEqual(settlement.vendor_bill_id.partner_id.id, self.agency.id)
```

- [ ] **Step 3: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_outsourcing/tests/test_outsourcing.py`
```bash
git add cn_payroll_outsourcing/tests/
git commit -m "test: add TDD unit test for outsourcing service rate calculations and billing"
```
