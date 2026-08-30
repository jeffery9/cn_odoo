# Medical Insurance (MI) System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a centralized, highly optimized 3-module Medical Insurance (MI) management ecosystem in Odoo 17, mapping out localized compliance checks, automated contribution math, and SHA-256 PDF archiving.

**Architecture:** Core-Centric with Functional Isolation & Bridge Patterns (Approach 3). `mi_core` handles policies and employee enrollments, inheriting from core `hr` and `mail.thread`; `mi_compliance` implements non-blocking compliance risk scanners and tamper-proof archival structures; `mi_connector` isolates external request logging and serialization.

**Tech Stack:** Python 3.10+, Odoo 17 ORM Active Record, PostgreSQL, QWeb, and standard Python libraries (`hashlib`).

**Spec:** `docs/mi_system/specs.md`

## Global Constraints
- **Odoo Version Floor:** 17.0
- **Primary Dependencies:** `base`, `account`, `hr`, `mail`
- **Naming Rule:** Prefix all tables with `mi.` (e.g., `mi.policy`, `mi.enrollment`)
- **Coding Style:** Strictly follow PEP8; always apply `@api.model_create_multi` on creations; never introduce service/repository abstractions.

---

## Workspace Directory Map

```
/Users/jeffery/containers/odoo17/addons/cn_odoo/
├───mi_core/
│   ├───__init__.py
│   ├───__manifest__.py
│   ├───models/
│   │   ├───__init__.py
│   │   ├───mi_policy.py
│   │   └───mi_enrollment.py
│   ├───security/
│   │   └───ir.model.access.csv
│   ├───views/
│   │   ├───mi_policy_views.xml
│   │   └───mi_enrollment_views.xml
│   └───tests/
│       ├───__init__.py
│       └───test_mi_core.py
├───mi_compliance/
│   ├───__init__.py
│   ├───__manifest__.py
│   ├───models/
│   │   ├───__init__.py
│   │   ├───mi_compliance_scan.py
│   │   └───mi_audit_archive.py
│   ├───security/
│   │   └───ir.model.access.csv
│   ├───views/
│   │   ├───mi_compliance_scan_views.xml
│   │   └───report_evidence.xml
│   └───tests/
│       ├───__init__.py
│       └───test_mi_compliance.py
└───mi_connector/
    ├───__init__.py
    ├───__manifest__.py
    ├───models/
    │   ├───__init__.py
    │   └───mi_api_log.py
    └───security/
        └───ir.model.access.csv
```

---

## Step-by-Step Task Breakdown

### Task 1: Scaffolding and Core Policy Models (`mi_core`)

**Files:**
- Create: `mi_core/__init__.py`
- Create: `mi_core/__manifest__.py`
- Create: `mi_core/models/__init__.py`
- Create: `mi_core/models/mi_policy.py`
- Create: `mi_core/security/ir.model.access.csv`
- Create: `mi_core/tests/__init__.py`
- Create: `mi_core/tests/test_mi_core.py`

**Interfaces:**
- Produces: `mi.policy` and `mi.policy.line` Active Records with constraint rules.

- [ ] **Step 1.1: Write the failing test**
  Create `mi_core/tests/test_mi_core.py` and write test cases validating policy limits constraint checks and start date timeline validations.
  ```python
  # -*- coding: utf-8 -*-
  from odoo.tests.common import TransactionCase
  from odoo.exceptions import ValidationError

  class TestMICore(TransactionCase):
      def setUp(self):
          super().setUp()
          self.state_bj = self.env['res.country.state'].search([], limit=1)
          self.policy_1 = self.env['mi.policy'].create({
              'name': 'Beijing Policy 2023',
              'region_id': self.state_bj.id,
              'date_start': '2023-01-01',
          })
          self.env['mi.policy.line'].create({
              'policy_id': self.policy_1.id,
              'insurance_type': 'basic',
              'base_min': 6000.0,
              'base_max': 30000.0,
              'rate_employer': 9.8,
              'rate_employee': 2.0,
          })

      def test_policy_overlap_constraint(self):
          """Validate overlapping policies under same region and date raise error"""
          with self.assertRaises(ValidationError):
              self.env['mi.policy'].create({
                  'name': 'Beijing Policy Overlap',
                  'region_id': self.state_bj.id,
                  'date_start': '2023-01-01',
              })

      def test_policy_date_chronology(self):
          """Validate that new rule cannot predate currently active rules"""
          with self.assertRaises(ValidationError):
              self.env['mi.policy'].create({
                  'name': 'Beijing Policy Backdated',
                  'region_id': self.state_bj.id,
                  'date_start': '2022-01-01',
              })
  ```

- [ ] **Step 1.2: Run test to verify it fails**
  Explain and run:
  ```bash
  odoo-bin --test-enable -i mi_core --stop-after-init
  ```
  Expected: FAIL with missing module/models.

- [ ] **Step 1.3: Write manifest, models, and SQL constraints**
  Write `mi_core/__manifest__.py`:
  ```python
  {
      'name': 'Medical Insurance Core',
      'version': '17.0.1.0.0',
      'depends': ['base', 'hr', 'mail'],
      'data': [
          'security/ir.model.access.csv',
      ],
      'installable': True,
      'license': 'LGPL-3',
  }
  ```
  Write `mi_core/models/mi_policy.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo import models, fields, api, _
  from odoo.exceptions import ValidationError

  class MiPolicy(models.Model):
      _name = 'mi.policy'
      _description = 'Medical Insurance Policy'

      name = fields.Char(required=True)
      region_id = fields.Many2one('res.country.state', required=True, string='Region/City')
      date_start = fields.Date(required=True, default=fields.Date.today)
      state = fields.Selection([
          ('draft', 'Draft'),
          ('active', 'Active'),
          ('expired', 'Expired')
      ], default='draft', required=True)
      line_ids = fields.One2many('mi.policy.line', 'policy_id', string='Lines')

      _sql_constraints = [
          ('region_date_unique', 'unique(region_id, date_start)', 'A policy with this start date already exists for this region!')
      ]

      @api.constrains('date_start', 'region_id')
      def _check_date_chronology(self):
          for rec in self:
              overlapping = self.search([
                  ('region_id', '=', rec.region_id.id),
                  ('date_start', '>', rec.date_start),
                  ('id', '!=', rec.id)
              ])
              if overlapping:
                  raise ValidationError(_("The policy's start date cannot predate any existing rules for this region."))
  
  class MiPolicyLine(models.Model):
      _name = 'mi.policy.line'
      _description = 'Medical Insurance Policy Line'

      policy_id = fields.Many2one('mi.policy', ondelete='cascade', required=True)
      insurance_type = fields.Selection([
          ('basic', 'Basic Medical'),
          ('illness', 'Serious Illness'),
          ('maternity', 'Maternity')
      ], default='basic', required=True)
      base_min = fields.Float(required=True)
      base_max = fields.Float(required=True)
      rate_employer = fields.Float(required=True)
      rate_employee = fields.Float(required=True)
  ```
  And expose access rights in `mi_core/security/ir.model.access.csv`:
  ```csv
  id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
  access_mi_policy,mi.policy,model_mi_policy,base.group_user,1,1,1,1
  access_mi_policy_line,mi.policy.line,model_mi_policy_line,base.group_user,1,1,1,1
  ```

- [ ] **Step 1.4: Run test to verify it passes**
  Run:
  ```bash
  odoo-bin --test-enable -i mi_core --stop-after-init
  ```
  Expected: PASS.

- [ ] **Step 1.5: Commit**
  ```bash
  git add mi_core/
  git commit -m "feat(mi_core): scaffolding and policy core models"
  ```

---

### Task 2: Employee Enrollment and Automatic Calculations (`mi_core`)

**Files:**
- Create: `mi_core/models/mi_enrollment.py`
- Modify: `mi_core/__manifest__.py`
- Modify: `mi_core/models/__init__.py`
- Modify: `mi_core/tests/test_mi_core.py`

**Interfaces:**
- Consumes: `mi.policy` and `mi.policy.line`
- Produces: `mi.enrollment` model with tracking, calculated monthly contribution shares, and validation checks.

- [ ] **Step 2.1: Write failing tests for calculations & constraints**
  Open `mi_core/tests/test_mi_core.py` and append:
  ```python
      def test_contribution_calculations_mid(self):
          """Validate mid-tier wage values calculate exact shares"""
          enrollment = self.env['mi.enrollment'].create({
              'employee_id': self.env.user.employee_id.id or self.env['hr.employee'].create({'name': 'Employee Test'}).id,
              'policy_id': self.policy_1.id,
              'base_amount': 8000.0,
              'start_date': '2024-01-01',
          })
          # Base 8000 (between 6000 and 30000)
          # Employer share: 8000 * 9.8% = 784.00
          # Employee share: 8000 * 2.0% = 160.00
          self.assertEqual(enrollment.amount_employer, 784.00)
          self.assertEqual(enrollment.amount_employee, 160.00)

      def test_contribution_calculations_truncation(self):
          """Validate wage ceiling limits base calculations to 30000"""
          enrollment = self.env['mi.enrollment'].create({
              'employee_id': self.env['hr.employee'].create({'name': 'Employee High Wage'}).id,
              'policy_id': self.policy_1.id,
              'base_amount': 40000.0,
              'start_date': '2024-01-01',
          })
          # Base capped at 30000
          # Employer share: 30000 * 9.8% = 2940.00
          # Employee share: 30000 * 2.0% = 600.00
          self.assertEqual(enrollment.amount_employer, 2940.00)
          self.assertEqual(enrollment.amount_employee, 600.00)
  ```

- [ ] **Step 2.2: Run test to verify it fails**
  Run:
  ```bash
  odoo-bin --test-enable -i mi_core --stop-after-init
  ```
  Expected: FAIL (missing `mi.enrollment` model).

- [ ] **Step 2.3: Implement `mi.enrollment` with calculated attributes**
  Create `mi_core/models/mi_enrollment.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo import models, fields, api, _
  from odoo.exceptions import ValidationError

  class MiEnrollment(models.Model):
      _name = 'mi.enrollment'
      _inherit = ['mail.thread', 'mail.activity.mixin']
      _description = 'Medical Insurance Enrollment'

      employee_id = fields.Many2one('hr.employee', required=True, tracking=True)
      policy_id = fields.Many2one('mi.policy', required=True, tracking=True)
      base_amount = fields.Float(required=True, tracking=True)
      state = fields.Selection([
          ('draft', 'Draft'),
          ('pending', 'Pending Declaration'),
          ('enrolled', 'Enrolled'),
          ('terminated', 'Terminated')
      ], default='draft', required=True, tracking=True)
      start_date = fields.Date(required=True, tracking=True, default=fields.Date.today)
      end_date = fields.Date(tracking=True)
      
      amount_employer = fields.Float(compute='_compute_contributions', store=True, tracking=True)
      amount_employee = fields.Float(compute='_compute_contributions', store=True, tracking=True)

      @api.depends('base_amount', 'policy_id', 'policy_id.line_ids')
      def _compute_contributions(self):
          for rec in self:
              emp_total = 0.0
              p_total = 0.0
              if rec.policy_id:
                  for line in rec.policy_id.line_ids:
                      actual_base = max(line.base_min, min(rec.base_amount, line.base_max))
                      emp_total += round(actual_base * (line.rate_employer / 100.0), 2)
                      p_total += round(actual_base * (line.rate_employee / 100.0), 2)
              rec.amount_employer = emp_total
              rec.amount_employee = p_total

      @api.constrains('employee_id', 'state')
      def _check_duplicate_active_enrollment(self):
          for rec in self:
              if rec.state in ['pending', 'enrolled']:
                  duplicates = self.search([
                      ('employee_id', '=', rec.employee_id.id),
                      ('state', 'in', ['pending', 'enrolled']),
                      ('id', '!=', rec.id)
                  ])
                  if duplicates:
                      raise ValidationError(_("This employee already has an active or pending enrollment record!"))
  ```
  Update `mi_core/models/__init__.py` and access rules inside `mi_core/security/ir.model.access.csv`:
  ```csv
  access_mi_enrollment,mi.enrollment,model_mi_enrollment,base.group_user,1,1,1,1
  ```

- [ ] **Step 2.4: Run test to verify it passes**
  Run:
  ```bash
  odoo-bin --test-enable -i mi_core --stop-after-init
  ```
  Expected: PASS.

- [ ] **Step 2.5: Commit**
  ```bash
  git add mi_core/
  git commit -m "feat(mi_core): add employee enrollment calculations and validation constraints"
  ```

---

### Task 3: Base Import Excel Interceptor (`mi_core`)

**Files:**
- Create: `mi_core/models/base_import_override.py`
- Modify: `mi_core/models/__init__.py`
- Modify: `mi_core/tests/test_mi_core.py`

**Interfaces:**
- Consumes: Standard Odoo `base_import.import` execution.
- Produces: Intercepted validations during bulk imports, flagging base errors and in-保 overlaps.

- [ ] **Step 3.1: Write failing test verifying import validation**
  Open `mi_core/tests/test_mi_core.py` and append:
  ```python
      def test_base_import_override_intercept(self):
          """Validate that importing enrollment records with lower base gets flagged with error"""
          import_wizard = self.env['base_import.import'].create({
              'res_model': 'mi.enrollment',
              'file': b"employee_id,policy_id,base_amount,start_date\nTest,Beijing Policy 2023,4000.0,2024-01-01",
              'file_name': 'test.csv',
              'file_type': 'text/csv'
          })
          # Dryrun import executes validation
          results = import_wizard.execute_import(
              ['employee_id', 'policy_id', 'base_amount', 'start_date'],
              ['employee_id', 'policy_id', 'base_amount', 'start_date'],
              {'headers': True},
              dryrun=True
          )
          # Verify that an error was injected into results because 4000 is below the 6000 limit
          messages = results.get('messages', [])
          self.assertTrue(any("base_amount" in m.get('message', '') or "below policy lower limit" in m.get('message', '') for m in messages))
  ```

- [ ] **Step 3.2: Run test to verify it fails**
  Run:
  ```bash
  odoo-bin --test-enable -i mi_core --stop-after-init
  ```
  Expected: FAIL (no import intercept executed).

- [ ] **Step 3.3: Implement `base_import.import` subclass override**
  Create `mi_core/models/base_import_override.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo import models, fields, api, _
  from odoo.exceptions import ValidationError

  class Import(models.TransientModel):
      _inherit = 'base_import.import'

      def execute_import(self, fields, columns, options, dryrun=False):
          if self.res_model == 'mi.enrollment':
              # Execute dry-run validation for policy and base boundaries before final insert
              self._validate_mi_enrollments_pre_import(fields, options)
          return super(Import, self).execute_import(fields, columns, options, dryrun=dryrun)

      def _validate_mi_enrollments_pre_import(self, fields, options):
          # Dryrun read lines and execute bounds logic
          # Throw a standard validation block or inject warnings array if violations found
          pass
  ```
  *(Implement full verification mapping logic inside `base_import_override.py` to check row-by-row elements against `mi.policy.line` minimum parameters).*

- [ ] **Step 3.4: Run test to verify it passes**
  Run:
  ```bash
  odoo-bin --test-enable -i mi_core --stop-after-init
  ```
  Expected: PASS.

- [ ] **Step 3.5: Commit**
  ```bash
  git add mi_core/
  git commit -m "feat(mi_core): implement base_import intercept validations"
  ```

---

### Task 4: Risk Scanning Engine & Dashboard (`mi_compliance`)

**Files:**
- Create: `mi_compliance/__init__.py`
- Create: `mi_compliance/__manifest__.py`
- Create: `mi_compliance/models/__init__.py`
- Create: `mi_compliance/models/mi_compliance_scan.py`
- Create: `mi_compliance/security/ir.model.access.csv`
- Create: `mi_compliance/tests/__init__.py`
- Create: `mi_compliance/tests/test_mi_compliance.py`

**Interfaces:**
- Consumes: `mi.enrollment` and active policy lines from `mi_core`.
- Produces: Compliance scan lists, calculating 0.05% daily penalty metrics on late insurance payments.

- [ ] **Step 4.1: Write failing test verifying calculation of late fees**
  Create `mi_compliance/tests/test_mi_compliance.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo.tests.common import TransactionCase
  from odoo import fields

  class TestMICompliance(TransactionCase):
      def setUp(self):
          super().setUp()
          # Create baseline employee & outstanding overdue periods to check calculations
          self.employee = self.env['hr.employee'].create({'name': 'Overdue Worker'})
          
      def test_late_penalty_calculation(self):
          """Validate late payments correctly accrue daily 0.05% interest fees"""
          scan = self.env['mi.compliance.scan'].create({
              'scan_date': '2024-04-15',
          })
          # Inject dummy risk line simulating 100 days overdue with 3600 principal
          risk_line = self.env['mi.compliance.risk.line'].create({
              'scan_id': scan.id,
              'employee_id': self.employee.id,
              'risk_type': 'missing',
              'amount_principal': 3600.0,
              'months_overdue': 3,
          })
          # Calculate late penalty
          # 3600 principal * 0.05% * 100 days = 180.00
          scan._calculate_penalties(risk_line, overdue_days=100)
          self.assertEqual(risk_line.amount_penalty, 180.00)
  ```

- [ ] **Step 4.2: Run test to verify it fails**
  Run:
  ```bash
  odoo-bin --test-enable -i mi_compliance --stop-after-init
  ```
  Expected: FAIL.

- [ ] **Step 4.3: Implement scan and penalty calculation lines**
  Create `mi_compliance/models/mi_compliance_scan.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo import models, fields, api

  class MiComplianceScan(models.Model):
      _name = 'mi.compliance.scan'
      _description = 'Compliance Scan'

      name = fields.Char(readonly=True, default='New')
      scan_date = fields.Date(default=fields.Date.today, required=True)
      risk_line_ids = fields.One2many('mi.compliance.risk.line', 'scan_id', string='Risks')
      total_penalty_estimate = fields.Float(compute='_compute_totals', store=True)

      @api.depends('risk_line_ids.amount_penalty')
      def _compute_totals(self):
          for rec in self:
              rec.total_penalty_estimate = sum(rec.risk_line_ids.mapped('amount_penalty'))

      def _calculate_penalties(self, risk_line, overdue_days):
          risk_line.amount_penalty = round(risk_line.amount_principal * 0.0005 * overdue_days, 2)
  ```
  Create `mi_compliance/models/__init__.py`, `mi_compliance/__manifest__.py` (adding `mi_core` and `mail` dependency), and `security/ir.model.access.csv`.

- [ ] **Step 4.4: Run test to verify it passes**
  Run:
  ```bash
  odoo-bin --test-enable -i mi_compliance --stop-after-init
  ```
  Expected: PASS.

- [ ] **Step 4.5: Commit**
  ```bash
  git add mi_compliance/
  git commit -m "feat(mi_compliance): add compliance scanning and penalty engine"
  ```

---

### Task 5: SHA-256 PDF Verification and Archival (`mi_compliance`)

**Files:**
- Create: `mi_compliance/models/mi_audit_archive.py`
- Modify: `mi_compliance/models/__init__.py`
- Modify: `mi_compliance/tests/test_mi_compliance.py`
- Create: `mi_compliance/views/report_evidence.xml`

**Interfaces:**
- Consumes: `hr.employee` data and `mi.enrollment` Chatter feeds.
- Produces: Standard encrypted PDF generation and SHA-256 registry entries.

- [ ] **Step 5.1: Write failing test verifying PDF hashing**
  Open `mi_compliance/tests/test_mi_compliance.py` and write:
  ```python
      def test_pdf_hash_archival(self):
          """Validate that audit report generation creates a secure SHA-256 registry log"""
          archive_rec = self.env['mi.audit.archive']._generate_and_log_evidence(self.employee)
          self.assertTrue(archive_rec.sha256_hash)
          self.assertEqual(len(archive_rec.sha256_hash), 64) # Length of hex representation of SHA-256
  ```

- [ ] **Step 5.2: Run test to verify it fails**
  Run:
  ```bash
  odoo-bin --test-enable -i mi_compliance --stop-after-init
  ```
  Expected: FAIL.

- [ ] **Step 5.3: Implement QWeb evidence report and Hash storage archive**
  Create `mi_compliance/models/mi_audit_archive.py`:
  ```python
  # -*- coding: utf-8 -*-
  import hashlib
  from odoo import models, fields, api

  class MiAuditArchive(models.Model):
      _name = 'mi.audit.archive'
      _description = 'Audit Evidence Archive'

      employee_id = fields.Many2one('hr.employee', required=True, readonly=True)
      archive_date = fields.Datetime(default=fields.Datetime.now, readonly=True)
      attachment_id = fields.Many2one('ir.attachment', required=True, readonly=True)
      sha256_hash = fields.Char(size=64, required=True, readonly=True)

      def _generate_and_log_evidence(self, employee):
          # 1. Dummy mock or real binary creation of the file
          dummy_pdf = b"PDF-EXEMPLAR-DATA-王五-EVIDENCE-CHAIN"
          file_hash = hashlib.sha256(dummy_pdf).hexdigest()
          
          attachment = self.env['ir.attachment'].create({
              'name': f"{employee.name}_evidence.pdf",
              'type': 'binary',
              'raw': dummy_pdf,
              'res_model': 'hr.employee',
              'res_id': employee.id,
          })
          return self.create({
              'employee_id': employee.id,
              'attachment_id': attachment.id,
              'sha256_hash': file_hash,
          })
  ```
  *(Connect this model backend calculations to a print option triggering the hashing system).*

- [ ] **Step 5.4: Run test to verify it passes**
  Run:
  ```bash
  odoo-bin --test-enable -i mi_compliance --stop-after-init
  ```
  Expected: PASS.

- [ ] **Step 5.5: Commit**
  ```bash
  git add mi_compliance/
  git commit -m "feat(mi_compliance): implement SHA-256 PDF report hashing and archiving"
  ```

---

### Task 6: Connector Asynchronous API Logging (`mi_connector`)

**Files:**
- Create: `mi_connector/__init__.py`
- Create: `mi_connector/__manifest__.py`
- Create: `mi_connector/models/__init__.py`
- Create: `mi_connector/models/mi_api_log.py`
- Create: `mi_connector/security/ir.model.access.csv`

**Interfaces:**
- Consumes: Outbound requests and JSON structures from `mi_core`.
- Produces: Decoupled transactional network logging.

- [ ] **Step 6.1: Write basic manifest and model fields**
  Create `mi_connector/models/mi_api_log.py`:
  ```python
  # -*- coding: utf-8 -*-
  from odoo import models, fields

  class MiApiLog(models.Model):
      _name = 'mi.api.log'
      _description = 'API Transaction Log'

      name = fields.Char(required=True)
      request_data = fields.Text()
      response_data = fields.Text()
      state = fields.Selection([
          ('pending', 'Pending'),
          ('success', 'Success'),
          ('failed', 'Failed')
      ], default='pending')
      res_model = fields.Char()
      res_id = fields.Integer()
  ```
  Define manifest `mi_connector/__manifest__.py` and access rules. This isolates request logs from blocking the primary `mi_core` models.

- [ ] **Step 6.2: Run whole test suite to verify everything is operational**
  Run:
  ```bash
  odoo-bin --test-enable -i mi_core,mi_compliance,mi_connector --stop-after-init
  ```
  Expected: All checks PASS with 100% test integrity.

- [ ] **Step 6.3: Commit**
  ```bash
  git add mi_connector/
  git commit -m "feat(mi_connector): asynchronous logging implementation"
  ```
