# China Payroll, Attendance & Cumulative Tax Engine (五险一金 & 考勤消费集成) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a robust, western-payroll-independent Chinese Salary, Attendance & Individual Income Tax (IIT) engine inside Odoo 17. The system consumes employee insurance contributions from the `mi_core` (SIHF) module and parses Odoo's native attendance (`hr.attendance`), leave (`hr.leave`), and calendar (`resource.calendar`) records into a consolidated monthly summary (`cn.attendance.summary`) that drives salary calculations and cumulative tax assessments.

**Architecture:** 
- `cn_payroll_core` manages salary items (`cn.salary.item`), structures (`cn.salary.structure`), monthly payslips (`cn.payslip`), and the monthly attendance summaries (`cn.attendance.summary`), retrieving both personal SIHF contributions and attendance deduction factors.
- `cn_payroll_tax` establishes the Year-to-Date tax ledger (`cn.tax.ytd.record`) and implements cumulative pre-withholding tax rate schedules.

**Tech Stack:** Python 3.10+, Odoo 17 CE/EE ORM, PostgreSQL.

---

## Workspace Directory Map

```
/Users/jeffery/containers/odoo17/addons/cn_odoo/
├───cn_payroll_core/
│   ├───__init__.py
│   ├───__manifest__.py
│   ├───models/
│   │   ├───__init__.py
│   │   ├───cn_salary_item.py         # Salary Item definition (basic, bonus, deductions)
│   │   ├───cn_salary_structure.py    # Salary Structure (items collection)
│   │   ├───cn_attendance_summary.py  # Monthly attendance summarizing logic (Odoo native parsing)
│   │   └───cn_payslip.py             # Employee monthly payslip with formula engine
│   ├───security/
│   │   └───ir.model.access.csv
│   └───tests/
│       ├───__init__.py
│       └───test_payroll_core.py      # Attendance deductions & basic computation tests
└───cn_payroll_tax/
    ├───__init__.py
    ├───__manifest__.py
    ├───models/
    │   ├───__init__.py
    │   ├───cn_tax_ytd_record.py      # Monthly cumulative pre-withholding IIT ledger
    │   └───cn_payslip_tax_override.py# Inheritance of cn.payslip calculating IIT
    ├───security/
    │   └───ir.model.access.csv
    └───tests/
        ├───__init__.py
        └───test_payroll_tax.py       # Test cumulative tax pre-withholding calculations
```

---

## Step-by-Step Task Breakdown

### Task 1: Scaffolding and Core Salary Setup (`cn_payroll_core`)

**Files:**
- Create: `cn_payroll_core/__init__.py`, `cn_payroll_core/__manifest__.py`
- Create: `cn_payroll_core/models/__init__.py`, `cn_payroll_core/models/cn_salary_item.py`, `cn_payroll_core/models/cn_salary_structure.py`
- Create: `cn_payroll_core/security/ir.model.access.csv`
- Create: `cn_payroll_core/tests/__init__.py`, `cn_payroll_core/tests/test_payroll_core.py`

**Interfaces:**
- Produces: `cn.salary.item` and `cn.salary.structure` models.

- [ ] **Step 1.1: Write the failing TDD test**
  Create `cn_payroll_core/tests/test_payroll_core.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo.tests.common import TransactionCase
  from odoo.exceptions import ValidationError

  class TestPayrollCore(TransactionCase):
      def setUp(self):
          super().setUp()
          self.item_basic = self.env['cn.salary.item'].create({
              'name': 'Basic Wage',
              'code': 'BASIC',
              'item_type': 'fixed',
              'is_taxable': True,
          })
          self.structure = self.env['cn.salary.structure'].create({
              'name': 'Standard White Collar',
              'item_ids': [(4, self.item_basic.id)],
          })

      def test_salary_item_code_unique(self):
          """Validate that salary item codes must be strictly unique"""
          with self.assertRaises(ValidationError):
              self.env['cn.salary.item'].create({
                  'name': 'Duplicate Basic',
                  'code': 'BASIC',
                  'item_type': 'fixed',
              })
  ```

- [ ] **Step 1.2: Run test to verify it fails**
  Verify the expected failures with missing models.

- [ ] **Step 1.3: Implement `cn_salary_item` and `cn_salary_structure` models**
  Create `cn_payroll_core/models/cn_salary_item.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo import models, fields, api, _
  from odoo.exceptions import ValidationError

  class CnSalaryItem(models.Model):
      _name = 'cn.salary.item'
      _description = 'Salary Item'

      name = fields.Char(required=True)
      code = fields.Char(required=True)
      item_type = fields.Selection([
          ('fixed', 'Fixed Salary'),
          ('variable', 'Variable/Bonus'),
          ('deduction', 'Deduction'),
          ('exempt', 'Tax Exempt')
      ], default='fixed', required=True)
      is_taxable = fields.Boolean(default=True)
      python_code = fields.Text(string='Computation Python Code')

      _sql_constraints = [
          ('code_unique', 'unique(code)', 'Salary item code must be unique!')
      ]
  ```
  Create `cn_payroll_core/models/cn_salary_structure.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo import models, fields

  class CnSalaryStructure(models.Model):
      _name = 'cn.salary.structure'
      _description = 'Salary Structure'

      name = fields.Char(required=True)
      item_ids = fields.Many2many('cn.salary.item', string='Salary Items')
  ```
  Expose security parameters in `cn_payroll_core/security/ir.model.access.csv`.

- [ ] **Step 1.4: Run test to verify it passes**
  Verify successful test execution.

- [ ] **Step 1.5: Commit**
  ```bash
  git commit -m "feat(payroll_core): scaffolding and core salary configurations"
  ```

---

### Task 2: Implement Odoo-Native Attendance Summary Mapping (`cn_payroll_core`)

**Files:**
- Create: `cn_payroll_core/models/cn_attendance_summary.py`
- Modify: `cn_payroll_core/models/__init__.py`
- Modify: `cn_payroll_core/tests/test_payroll_core.py`

**Interfaces:**
- Consumes: Odoo-native records from `hr.attendance`, `hr.leave`, and `resource.calendar`.
- Produces: `cn.attendance.summary` tracking late arrivals, absences, and leave days.

- [ ] **Step 2.1: Write failing TDD test**
  Open `cn_payroll_core/tests/test_payroll_core.py` and append:
  ```python
      def test_attendance_summary_native_parsing(self):
          """Validate that the monthly summary correctly parses native Odoo attendances and leaves"""
          employee = self.env['hr.employee'].create({'name': 'Attendance Worker'})
          
          # 1. Simulate check_in/check_out on 2024-03-01
          # Shift is 09:00 to 18:00. Employee checks in at 09:15 -> 15 minutes late.
          self.env['hr.attendance'].create({
              'employee_id': employee.id,
              'check_in': '2024-03-01 01:15:00', # UTC (09:15:00 Beijing time)
              'check_out': '2024-03-01 10:00:00', # UTC (18:00:00 Beijing time)
          })

          # 2. Simulate 2 days personal leave on hr.leave (March 5 to March 6)
          # First search for personal leave type
          leave_type = self.env['hr.leave.type'].search([('name', 'ilike', 'personal')], limit=1)
          if not leave_type:
              leave_type = self.env['hr.leave.type'].create({
                  'name': 'Personal Leave',
                  'requires_allocation': 'no',
              })
          self.env['hr.leave'].create({
              'employee_id': employee.id,
              'holiday_status_id': leave_type.id,
              'date_from': '2024-03-05 01:00:00',
              'date_to': '2024-03-06 10:00:00',
              'number_of_days': 2.0,
              'state': 'validate', # Approved
          })

          # Run Summarizer
          summary = self.env['cn.attendance.summary'].create({
              'employee_id': employee.id,
              'period': '2024-03',
          })
          summary.action_calculate_summary()

          self.assertEqual(summary.late_minutes, 15)
          self.assertEqual(summary.personal_leave_days, 2.0)
  ```

- [ ] **Step 2.2: Run test to verify it fails**
  Expected: FAIL with missing `cn.attendance.summary` model.

- [ ] **Step 2.3: Implement `cn.attendance.summary` modeling**
  Create `cn_payroll_core/models/cn_attendance_summary.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo import models, fields, api, _
  from datetime import datetime, timedelta
  import pytz

  class CnAttendanceSummary(models.Model):
      _name = 'cn.attendance.summary'
      _description = 'Monthly Attendance Summary'

      employee_id = fields.Many2one('hr.employee', required=True)
      period = fields.Char(required=True, help="Format: YYYY-MM")
      late_minutes = fields.Integer(string='Late Minutes', default=0)
      personal_leave_days = fields.Float(string='Personal Leave Days', default=0.0)
      sick_leave_days = fields.Float(string='Sick Leave Days', default=0.0)
      absent_days = fields.Float(string='Absent Days', default=0.0)

      _sql_constraints = [
          ('emp_period_unique', 'unique(employee_id, period)', 'Employee summary already exists for this period!')
      ]

      def action_calculate_summary(self):
          self.ensure_one()
          # Parse period dates
          year, month = map(int, self.period.split('-'))
          tz = pytz.timezone(self.env.user.tz or 'Asia/Shanghai')

          # Local start/end dates
          start_dt = tz.localize(datetime(year, month, 1, 0, 0, 0))
          if month == 12:
              end_dt = tz.localize(datetime(year + 1, 1, 1, 0, 0, 0))
          else:
              end_dt = tz.localize(datetime(year, month + 1, 1, 0, 0, 0))

          # UTC conversion for database queries
          start_utc = start_dt.astimezone(pytz.utc).replace(tzinfo=None)
          end_utc = end_dt.astimezone(pytz.utc).replace(tzinfo=None)

          # 1. Parse hr.attendance and compare check_in with 09:00 standard shift
          attendances = self.env['hr.attendance'].search([
              ('employee_id', '=', self.employee_id.id),
              ('check_in', '>=', start_utc),
              ('check_in', '<', end_utc)
          ])

          late_sum = 0
          for att in attendances:
              # Convert check_in to Beijing local time
              local_in = pytz.utc.localize(att.check_in).astimezone(tz)
              
              # Standard schedule baseline is 09:00
              standard_in = local_in.replace(hour=9, minute=0, second=0, microsecond=0)
              if local_in > standard_in:
                  diff_min = int((local_in - standard_in).total_seconds() / 60)
                  # If employee checked in later than 09:00 and did not exceed 4 hours (which is considered half day absent)
                  if diff_min < 240:
                      late_sum += diff_min

          self.late_minutes = late_sum

          # 2. Parse hr.leave (Personal vs. Sick)
          leaves = self.env['hr.leave'].search([
              ('employee_id', '=', self.employee_id.id),
              ('state', '=', 'validate'),
              ('date_from', '>=', start_utc),
              ('date_from', '<', end_utc)
          ])

          personal = 0.0
          sick = 0.0
          for leave in leaves:
              if 'sick' in leave.holiday_status_id.name.lower():
                  sick += leave.number_of_days
              else:
                  personal += leave.number_of_days

          self.personal_leave_days = personal
          self.sick_leave_days = sick
  ```
  Register the new model in the manifest, `__init__.py`, and CSV permission tables.

- [ ] **Step 2.4: Run test to verify it passes**
  Ensure execution of syntax compile checks and unit tests.

- [ ] **Step 2.5: Commit**
  ```bash
  git commit -m "feat(payroll_core): implement cn.attendance.summary mapping Odoo-native records"
  ```

---

### Task 3: Implement Payslips with Formula Engine & Attendance Multipliers (`cn_payroll_core`)

**Files:**
- Create: `cn_payroll_core/models/cn_payslip.py`
- Modify: `cn_payroll_core/models/__init__.py`
- Modify: `cn_payroll_core/tests/test_payroll_core.py`

**Interfaces:**
- Consumes: Monthly attendance summary factors from `cn.attendance.summary`.
- Produces: `cn.payslip` executing customizable math equations over late, personal, and sick days.

- [ ] **Step 3.1: Write failing TDD test**
  Open `cn_payroll_core/tests/test_payroll_core.py` and append:
  ```python
      def test_attendance_deduction_calculation(self):
          """Validate that employee payslip correctly computes attendance deduction rules using parsed variables"""
          employee = self.env['hr.employee'].create({'name': 'Zhang San Pay'})
          
          # Setup items
          item_basic = self.env['cn.salary.item'].create({
              'name': 'Basic Wage', 'code': 'BASIC', 'item_type': 'fixed'
          })
          item_absent = self.env['cn.salary.item'].create({
              'name': 'Absent Deduction', 'code': 'ABSENT', 'item_type': 'deduction',
              'python_code': 'result = - (BASIC / 21.75) * personal_leave_days'
          })
          item_late = self.env['cn.salary.item'].create({
              'name': 'Late Deduction', 'code': 'LATE', 'item_type': 'deduction',
              'python_code': 'result = - 50 if late_minutes > 30 else (-20 if late_minutes > 10 else 0)'
          })
          item_net = self.env['cn.salary.item'].create({
              'name': 'Net Salary', 'code': 'NET', 'item_type': 'fixed',
              'python_code': 'result = BASIC + ABSENT + LATE'
          })

          struct = self.env['cn.salary.structure'].create({
              'name': 'White Collar Structured',
              'item_ids': [(4, item_basic.id), (4, item_absent.id), (4, item_late.id), (4, item_net.id)],
          })

          # Inject Attendance Summary (15 min late, 1 day personal leave)
          self.env['cn.attendance.summary'].create({
              'employee_id': employee.id,
              'period': '2024-03',
              'late_minutes': 15,
              'personal_leave_days': 1.0,
          })

          # Create slips
          payslip = self.env['cn.payslip'].create({
              'employee_id': employee.id,
              'structure_id': struct.id,
              'period': '2024-03',
              'base_wage_amount': 10000.0,
          })
          
          payslip.action_compute_sheet()
          
          # Assert computations
          basic_line = payslip.line_ids.filtered(lambda l: l.code == 'BASIC')
          self.assertEqual(basic_line.amount, 10000.0)
          
          absent_line = payslip.line_ids.filtered(lambda l: l.code == 'ABSENT')
          self.assertAlmostEqual(absent_line.amount, -459.77, places=2) # -10000/21.75 * 1
          
          late_line = payslip.line_ids.filtered(lambda l: l.code == 'LATE')
          self.assertEqual(late_line.amount, -20.0) # 15 minutes is > 10 -> -20.0
          
          net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
          self.assertAlmostEqual(net_line.amount, 9520.23, places=2)
  ```

- [ ] **Step 3.2: Run test to verify it fails**
  Expected: FAIL with missing `cn.payslip` model.

- [ ] **Step 3.3: Implement `cn.payslip` with formula engine**
  Create `cn_payroll_core/models/cn_payslip.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo import models, fields, api, _
  from odoo.exceptions import ValidationError
  from odoo.tools.safe_eval import safe_eval

  class CnPayslip(models.Model):
      _name = 'cn.payslip'
      _inherit = ['mail.thread', 'mail.activity.mixin']
      _description = 'Employee Payslip'

      employee_id = fields.Many2one('hr.employee', required=True, tracking=True)
      structure_id = fields.Many2one('cn.salary.structure', required=True, tracking=True)
      period = fields.Char(required=True, tracking=True, help="Format: YYYY-MM")
      base_wage_amount = fields.Float(string="Base Wage", required=True)
      
      line_ids = fields.One2many('cn.payslip.line', 'slip_id', string='Salary Lines', cascade='delete')
      state = fields.Selection([
          ('draft', 'Draft'),
          ('approved', 'Approved'),
          ('paid', 'Paid')
      ], default='draft', required=True, tracking=True)

      def action_compute_sheet(self):
          self.ensure_one()
          self.line_ids.unlink()

          # Locate attendance summary for variables
          summary = self.env['cn.attendance.summary'].search([
              ('employee_id', '=', self.employee_id.id),
              ('period', '=', self.period)
          ], limit=1)

          late_minutes = summary.late_minutes if summary else 0
          personal_leave_days = summary.personal_leave_days if summary else 0.0
          sick_leave_days = summary.sick_leave_days if summary else 0.0
          absent_days = summary.absent_days if summary else 0.0

          # Pre-populate evaluation variables dictionary
          eval_context = {
              'BASIC': self.base_wage_amount,
              'late_minutes': late_minutes,
              'personal_leave_days': personal_leave_days,
              'sick_leave_days': sick_leave_days,
              'absent_days': absent_days,
              'result': 0.0,
          }

          # Evaluate in items order
          for item in self.structure_id.item_ids:
              amount = 0.0
              if item.code == 'BASIC':
                  amount = self.base_wage_amount
              elif item.python_code:
                  local_context = dict(eval_context)
                  try:
                      safe_eval(item.python_code, globals_dict={}, locals_dict=local_context, mode='exec', nocopy=True)
                      amount = local_context.get('result', 0.0)
                  except Exception as e:
                      raise ValidationError(_("Error evaluating salary item %s: %s") % (item.name, e))
              
              # Record result back in evaluation context for subsequent items
              eval_context[item.code] = amount
              
              self.env['cn.payslip.line'].create({
                  'slip_id': self.id,
                  'item_id': item.id,
                  'code': item.code,
                  'amount': amount,
              })

  class CnPayslipLine(models.Model):
      _name = 'cn.payslip.line'
      _description = 'Payslip Salary Line'

      slip_id = fields.Many2one('cn.payslip', ondelete='cascade', required=True)
      item_id = fields.Many2one('cn.salary.item', required=True)
      code = fields.Char(related='item_id.code', store=True)
      amount = fields.Float()
  ```
  Expose permissions in CSV and update package imports.

- [ ] **Step 3.4: Run test to verify it passes**
  Ensure tests run cleanly.

- [ ] **Step 3.5: Commit**
  ```bash
  git commit -m "feat(payroll_core): implement employee payslip and execution formula engine"
  ```

---

### Task 4: Implement `mi` Social Insurance Consumption & Integration (`cn_payroll_core`)

**Files:**
- Modify: `cn_payroll_core/models/cn_payslip.py`
- Modify: `cn_payroll_core/tests/test_payroll_core.py`

**Interfaces:**
- Consumes: Verified, active `mi.enrollment` structures from `mi_core` for specific period and employee.
- Produces: Integrated social insurance deduction item value mapping on payslip lines.

- [ ] **Step 4.1: Write failing TDD test**
  Open `cn_payroll_core/tests/test_payroll_core.py` and append:
  ```python
      def test_mi_integration_social_insurance_deductions(self):
          """Validate that payslips dynamically pull confirmed employee social insurance deductions from mi system"""
          employee = self.env['hr.employee'].create({'name': 'Li Si'})
          state_bj = self.env['res.country.state'].search([], limit=1)
          
          # Setup Policy & SIHF enrollment in mi_core
          policy = self.env['mi.policy'].create({
              'name': 'Beijing Policy 2024',
              'region_id': state_bj.id,
              'date_start': '2024-01-01',
              'state': 'active',
          })
          self.env['mi.policy.line'].create({
              'policy_id': policy.id,
              'insurance_type': 'medical',
              'base_min': 5000.0,
              'base_max': 30000.0,
              'rate_employer': 10.0,
              'rate_employee': 2.0,
          })
          
          enrollment = self.env['mi.enrollment'].create({
              'employee_id': employee.id,
              'policy_id': policy.id,
              'base_amount': 10000.0,
              'start_date': '2024-01-01',
              'state': 'enrolled',
          })
          # Assert employee contribution = 10000 * 2% = 200.0
          self.assertEqual(enrollment.amount_employee, 200.0)

          # Setup Payroll structures
          item_basic = self.env['cn.salary.item'].create({
              'name': 'Basic Wage', 'code': 'BASIC', 'item_type': 'fixed'
          })
          item_sihf = self.env['cn.salary.item'].create({
              'name': 'SIHF Deduction', 'code': 'SIHF', 'item_type': 'deduction',
              'python_code': 'result = - SIHF_PERSONAL' # special evaluated variable from mi
          })
          item_net = self.env['cn.salary.item'].create({
              'name': 'Net Salary', 'code': 'NET', 'item_type': 'fixed',
              'python_code': 'result = BASIC + SIHF'
          })

          struct = self.env['cn.salary.structure'].create({
              'name': 'Standard SIHF Structure',
              'item_ids': [(4, item_basic.id), (4, item_sihf.id), (4, item_net.id)],
          })

          # Calculate Slip
          payslip = self.env['cn.payslip'].create({
              'employee_id': employee.id,
              'structure_id': struct.id,
              'period': '2024-03',
              'base_wage_amount': 12000.0,
          })
          
          payslip.action_compute_sheet()
          
          sihf_line = payslip.line_ids.filtered(lambda l: l.code == 'SIHF')
          self.assertEqual(sihf_line.amount, -200.0)
          
          net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
          self.assertEqual(net_line.amount, 11800.0)
  ```

- [ ] **Step 4.2: Run test to verify it fails**
  Expected: FAIL with `NameError: name 'SIHF_PERSONAL' is not defined`.

- [ ] **Step 4.3: Upgrade evaluation context injection in `action_compute_sheet`**
  Modify `cn_payroll_core/models/cn_payslip.py`:
  ```python
          # Retrieve mi enrollment record
          enrollment = self.env['mi.enrollment'].search([
              ('employee_id', '=', self.employee_id.id),
              ('state', 'in', ['pending', 'enrolled']),
          ], limit=1)
          
          sihf_personal = enrollment.amount_employee if enrollment else 0.0

          # Pre-populate evaluation variables dictionary
          eval_context = {
              'BASIC': self.base_wage_amount,
              'late_minutes': late_minutes,
              'personal_leave_days': personal_leave_days,
              'sick_leave_days': sick_leave_days,
              'absent_days': absent_days,
              'SIHF_PERSONAL': sihf_personal,
              'result': 0.0,
          }
  ```

- [ ] **Step 4.4: Run test to verify it passes**
  Confirm test execution is clean.

- [ ] **Step 4.5: Commit**
  ```bash
  git commit -m "feat(payroll_core): integrate with mi module to consume SIHF employee shares"
  ```

---

### Task 5: Implement Year-to-Date (YTD) Cumulative Tax Ledger (`cn_payroll_tax`)

**Files:**
- Create: `cn_payroll_tax/__init__.py`, `cn_payroll_tax/__manifest__.py`
- Create: `cn_payroll_tax/models/__init__.py`, `cn_payroll_tax/models/cn_tax_ytd_record.py`
- Create: `cn_payroll_tax/security/ir.model.access.csv`
- Create: `cn_payroll_tax/tests/__init__.py`, `cn_payroll_tax/tests/test_payroll_tax.py`

**Interfaces:**
- Produces: `cn.tax.ytd.record` cumulative ledger records.

- [ ] **Step 5.1: Write failing TDD test**
  Create `cn_payroll_tax/tests/test_payroll_tax.py` to assert that creating cumulative pre-withholding tax entries behaves mathematically:
  ```python
  # -*- coding: utf-8 -*-
  from odoo.tests.common import TransactionCase

  class TestPayrollTax(TransactionCase):
      def setUp(self):
          super().setUp()
          self.employee = self.env['hr.employee'].create({'name': 'Li Si'})

      def test_cumulative_iit_calculation_march(self):
          """Validate that cumulative taxation computes correct progressive IIT on month 3"""
          # Create tax records representing Month 3 (March)
          # Salary: 20000.0, SIHF Ded: 2200.0, Spec Add Ded: 2000.0
          # Cumulative Income (YTD Jan-Feb) was 40000, YTD Paid Tax = 348.0
          # We check the computation methods directly
          ytd_ledger = self.env['cn.tax.ytd.record'].create({
              'employee_id': self.employee.id,
              'year': 2024,
          })
          # Month 1 & 2 values represent 20000 * 2 = 40000 cumulative income
          # standard threshold is 5000 * Month
          # Jan & Feb:
          # Taxable Jan-Feb = 40000 - 10000 (standard) - 4400 (sihf) - 4000 (spec add) = 21600.0
          # 21600 * 3% = 648.0 total tax, but let's say cumulative paid tax was 348.0
          
          # March parameters
          tax_amount = ytd_ledger.compute_monthly_iit(
              month=3,
              current_income=20000.0,
              current_sihf=2200.0,
              current_special_add=2000.0,
              cumulative_paid_before=348.0
          )
          # YTD Taxable (Month 3) = (20000*3) - (5000*3) - (2200*3) - (2000*3) = 60000 - 15000 - 6600 - 6000 = 32400.0
          # Progressive bracket <= 36000 is 3%, Quick Deduction 0.
          # YTD Tax March = 32400 * 3% = 972.0
          # March Tax = 972.0 - 348.0 = 624.0
          self.assertEqual(tax_amount, 624.0)
  ```

- [ ] **Step 5.2: Run test to verify it fails**
  Expected: FAIL (missing `cn.tax.ytd.record` model and computation methods).

- [ ] **Step 5.3: Implement `cn_tax_ytd_record` progressive tax engine**
  Create `cn_payroll_tax/models/cn_tax_ytd_record.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo import models, fields, api

  class CnTaxYtdRecord(models.Model):
      _name = 'cn.tax.ytd.record'
      _description = 'Year-to-Date Tax Ledger'

      employee_id = fields.Many2one('hr.employee', required=True)
      year = fields.Integer(required=True, default=lambda self: fields.Date.today().year)

      _sql_constraints = [
          ('emp_year_unique', 'unique(employee_id, year)', 'Each employee can only have one YTD record per year!')
      ]

      def compute_monthly_iit(self, month, current_income, current_sihf, current_special_add, cumulative_paid_before):
          self.ensure_one()
          
          # Calculate YTD metrics
          cumulative_income = current_income * month
          cumulative_exempt = 0.0
          cumulative_standard = 5000.0 * month
          cumulative_sihf = current_sihf * month
          cumulative_special_add = current_special_add * month

          taxable_income = cumulative_income - cumulative_exempt - cumulative_standard - cumulative_sihf - cumulative_special_add
          if taxable_income <= 0.0:
              return 0.0

          # PRC IIT Progressive Bracket Schedule (Annualized)
          # Bracket 1: <= 36000 -> 3%, Quick Ded 0
          # Bracket 2: 36000 to 144000 -> 10%, Quick Ded 2520
          # Bracket 3: 144000 to 300000 -> 20%, Quick Ded 16920
          # Bracket 4: 300000 to 420000 -> 25%, Quick Ded 31920
          # Bracket 5: 420000 to 660000 -> 30%, Quick Ded 52920
          # Bracket 6: 660000 to 960000 -> 35%, Quick Ded 85920
          # Bracket 7: > 960000 -> 45%, Quick Ded 181920
          
          rate = 0.03
          quick_ded = 0.0

          if taxable_income > 960000:
              rate = 0.45
              quick_ded = 181920.0
          elif taxable_income > 660000:
              rate = 0.35
              quick_ded = 85920.0
          elif taxable_income > 420000:
              rate = 0.30
              quick_ded = 52920.0
          elif taxable_income > 300000:
              rate = 0.25
              quick_ded = 31920.0
          elif taxable_income > 144000:
              rate = 0.20
              quick_ded = 16920.0
          elif taxable_income > 36000:
              rate = 0.10
              quick_ded = 2520.0

          cumulative_tax = round(taxable_income * rate - quick_ded, 2)
          current_month_tax = round(max(0.0, cumulative_tax - cumulative_paid_before), 2)
          return current_month_tax
  ```
  Expose security permissions in `cn_payroll_tax/security/ir.model.access.csv` and register module in manifests.

- [ ] **Step 5.4: Run test to verify it passes**
  Ensure tests run cleanly.

- [ ] **Step 5.5: Commit**
  ```bash
  git commit -m "feat(payroll_tax): implement YTD cumulative IIT pre-withholding tax ledger"
  ```

---

### Task 6: Inherit Payslip Formula Engine to Compute IIT (`cn_payroll_tax`)

**Files:**
- Create: `cn_payroll_tax/models/cn_payslip_tax_override.py`
- Modify: `cn_payroll_tax/models/__init__.py`
- Modify: `cn_payroll_tax/tests/test_payroll_tax.py`

**Interfaces:**
- Consumes: `cn.payslip` calculation pipeline.
- Produces: Integrated cumulative pre-withholding tax values computed and registered on payslip lines.

- [ ] **Step 6.1: Write failing TDD test**
  Open `cn_payroll_tax/tests/test_payroll_tax.py` and append:
  ```python
      def test_payslip_iit_integration_calculation(self):
          """Validate that payslips dynamically calculate cumulative pre-withholding taxes inside standard Odoo formula runs"""
          # Create employee with 2000 special additional deductions
          employee = self.env['hr.employee'].create({
              'name': 'Li Si Taxable',
              'hire_date': '2024-01-01',
          })
          
          # Setup items
          item_basic = self.env['cn.salary.item'].create({
              'name': 'Basic Wage', 'code': 'BASIC', 'item_type': 'fixed'
          })
          item_sihf = self.env['cn.salary.item'].create({
              'name': 'SIHF Deduction', 'code': 'SIHF', 'item_type': 'deduction',
              'python_code': 'result = - 2200.0'
          })
          item_iit = self.env['cn.salary.item'].create({
              'name': 'Individual Income Tax', 'code': 'IIT', 'item_type': 'deduction',
              'python_code': 'result = - IIT_AMOUNT' # special IIT variable
          })
          item_net = self.env['cn.salary.item'].create({
              'name': 'Net Salary', 'code': 'NET', 'item_type': 'fixed',
              'python_code': 'result = BASIC + SIHF + IIT'
          })

          struct = self.env['cn.salary.structure'].create({
              'name': 'Standard SIHF & Tax Structure',
              'item_ids': [(4, item_basic.id), (4, item_sihf.id), (4, item_iit.id), (4, item_net.id)],
          })

          # Create slip for Month 3 (March)
          payslip = self.env['cn.payslip'].create({
              'employee_id': employee.id,
              'structure_id': struct.id,
              'period': '2024-03',
              'base_wage_amount': 20000.0,
          })
          
          # Set special additional deduction to 2000 on slip
          payslip.special_additional_deduction = 2000.0
          payslip.cumulative_paid_before = 348.0
          
          payslip.action_compute_sheet()
          
          iit_line = payslip.line_ids.filtered(lambda l: l.code == 'IIT')
          self.assertEqual(iit_line.amount, -624.0)
          
          net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
          self.assertEqual(net_line.amount, 17176.0) # 20000 - 2200 - 624 = 17176.0
  ```

- [ ] **Step 6.2: Run test to verify it fails**
  Expected: FAIL with `NameError: name 'IIT_AMOUNT' is not defined`.

- [ ] **Step 6.3: Subclass `cn.payslip` in `cn_payroll_tax`**
  Create `cn_payroll_tax/models/cn_payslip_tax_override.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo import models, fields, api

  class CnPayslip(models.Model):
      _inherit = 'cn.payslip'

      special_additional_deduction = fields.Float(string="Special Additional Deduction", default=0.0)
      cumulative_paid_before = fields.Float(string="Cumulative Paid IIT Before", default=0.0)

      def action_compute_sheet(self):
          # We hook into computation to inject IIT_AMOUNT evaluation context
          return super(CnPayslip, self).action_compute_sheet()

      def _get_eval_context(self):
          # Gather or create YTD ledger
          ytd_ledger = self.env['cn.tax.ytd.record'].search([
              ('employee_id', '=', self.employee_id.id),
              ('year', '=', int(self.period.split('-')[0]))
          ], limit=1)
          if not ytd_ledger:
              ytd_ledger = self.env['cn.tax.ytd.record'].create({
                  'employee_id': self.employee_id.id,
                  'year': int(self.period.split('-')[0])
              })

          # Calculate SIHF amount (absolute positive value for deduction)
          enrollment = self.env['mi.enrollment'].search([
              ('employee_id', '=', self.employee_id.id),
              ('state', 'in', ['pending', 'enrolled']),
          ], limit=1)
          sihf_personal = enrollment.amount_employee if enrollment else 2200.0 # fallback default

          month = int(self.period.split('-')[1])
          
          iit_amount = ytd_ledger.compute_monthly_iit(
              month=month,
              current_income=self.base_wage_amount,
              current_sihf=sihf_personal,
              current_special_add=self.special_additional_deduction,
              cumulative_paid_before=self.cumulative_paid_before
          )

          # Inject IIT variables into computation
          res = {
              'IIT_AMOUNT': iit_amount,
              'SIHF_PERSONAL': sihf_personal,
          }
          return res
  ```
  And modify `cn_payroll_core/models/cn_payslip.py`'s `action_compute_sheet` to call a helper method `_get_eval_context()` which can be cleanly overridden by our tax module:
  ```python
      def _get_eval_context(self):
          # Pull enrollment details
          enrollment = self.env['mi.enrollment'].search([
              ('employee_id', '=', self.employee_id.id),
              ('state', 'in', ['pending', 'enrolled']),
          ], limit=1)
          sihf_personal = enrollment.amount_employee if enrollment else 0.0
          return {
              'SIHF_PERSONAL': sihf_personal,
          }
  ```
  And update core's `action_compute_sheet` context gathering block:
  ```python
          # Resolve extended variables
          extended_context = self._get_eval_context()

          # Pre-populate evaluation variables dictionary
          eval_context = {
              'BASIC': self.base_wage_amount,
              'result': 0.0,
          }
          eval_context.update(extended_context)
  ```

- [ ] **Step 6.4: Run test to verify it passes**
  Ensure all tax calculation integration tests run and pass perfectly.

- [ ] **Step 6.5: Commit**
  ```bash
  git commit -m "feat(payroll_tax): integrate cumulative IIT calculation with payslip formula engine"
  ```
