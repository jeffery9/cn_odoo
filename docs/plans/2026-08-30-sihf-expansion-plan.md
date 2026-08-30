# China SIHF (五险一金) Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the newly implemented Medical Insurance system to support all of China's Social Security and Housing Fund systems (known as "五险一金" - Five Insurances and One Fund, plus supplementary benefits) under Option B (Multi-Base Line Mode).

**Architecture:** Extend existing active record models in `mi_core` to include specific `mi.enrollment.line` records allowing custom wage bases per insurance group (社保基数 vs. 公积金基数) with a seamless fallback to the primary enrollment base. Expand `mi_compliance` to execute risk scanning across all five insurances and housing funds, assessing 0.05% daily overdue interest penalties comprehensively.

**Tech Stack:** Python 3.10+, Odoo 17 ORM Active Record, PostgreSQL.

**Spec:** `docs/mi_system/specs.md`

## Global Constraints
- **Odoo Version Floor:** 17.0
- **Primary Dependencies:** `base`, `hr`, `mail`, `base_import`, `mi_core`, `mi_compliance`, `mi_connector`
- **Naming Rule:** Prefix all tables with `mi.` (e.g., `mi.enrollment.line`)
- **Coding Style:** Strictly follow PEP8; always apply `@api.model_create_multi` on creations; never introduce service/repository abstractions.

---

## Workspace Directory Map

```
/Users/jeffery/containers/odoo17/addons/cn_odoo/
├───mi_core/
│   ├───models/
│   │   ├───mi_policy.py              # Expanded: insurance_type Selection
│   │   ├───mi_enrollment.py          # Expanded: mi.enrollment.line models & fallback-safe compute math
│   │   └───base_import_override.py   # Expanded: Multi-base dry-run import validations
│   └───tests/
│       └───test_mi_core.py           # Expanded: Multi-base TDD calculations & constraints
└───mi_compliance/
    ├───models/
    │   ├───mi_compliance_scan.py     # Expanded: Multi-insurance risk scanning & penalty math
    └───tests/
        └───test_mi_compliance.py     # Expanded: Multi-insurance scans TDD verification
```

---

## Step-by-Step Task Breakdown

### Task 1: Expand Policy Lines to Support 五险一金 (`mi_core`)

**Files:**
- Modify: `mi_core/models/mi_policy.py`
- Modify: `mi_core/tests/test_mi_core.py`

**Interfaces:**
- Produces: Expanded `insurance_type` Selection on `mi.policy.line` model.

- [ ] **Step 1.1: Write the failing test**
  Open `mi_core/tests/test_mi_core.py` and append test cases validating that policy lines can be created for all five insurances and housing funds, and checking overlap behaviors.
  ```python
      def test_policy_full_sihf_creation(self):
          """Validate that policy lines can be registered for all 五险一金 classes"""
          state_bj = self.env['res.country.state'].search([], limit=1)
          policy = self.env['mi.policy'].create({
              'name': 'Beijing Full SIHF 2024',
              'region_id': state_bj.id,
              'date_start': '2024-07-01',
          })
          # Verify the model accepts all the new selection categories
          for category in ['pension', 'medical', 'unemployment', 'injury', 'maternity', 'housing_fund', 'supp_housing_fund']:
              line = self.env['mi.policy.line'].create({
                  'policy_id': policy.id,
                  'insurance_type': category,
                  'base_min': 5000.0,
                  'base_max': 30000.0,
                  'rate_employer': 8.0 if category == 'pension' else 1.0,
                  'rate_employee': 4.0 if category == 'pension' else 0.5,
              })
              self.assertEqual(line.insurance_type, category)
  ```

- [ ] **Step 1.2: Run test to verify it fails**
  Run:
  ```bash
  python3 -m unittest mi_core/tests/test_mi_core.py
  ```
  Expected: FAIL with ValueError (selection values not recognized).

- [ ] **Step 1.3: Expand Selection in `mi_policy.py`**
  Modify the `insurance_type` selection field in `mi_core/models/mi_policy.py`:
  ```python
      insurance_type = fields.Selection([
          ('pension', 'Pension (养老保险)'),
          ('medical', 'Medical Insurance (医疗保险)'),
          ('unemployment', 'Unemployment (失业保险)'),
          ('injury', 'Injury (工伤保险)'),
          ('maternity', 'Maternity (生育保险)'),
          ('housing_fund', 'Housing Provident Fund (住房公积金)'),
          ('supp_housing_fund', 'Supplementary Housing Fund (补充公积金)'),
          ('supp_medical', 'Supplementary Medical (补充医疗)'),
          ('care', 'Long-term Care (长期护理险)')
      ], default='medical', required=True)
  ```

- [ ] **Step 1.4: Run test to verify it passes**
  Run syntax compile check and verify tests pass.

- [ ] **Step 1.5: Commit**
  ```bash
  git commit -m "feat(mi_core): expand policy lines selection to support full 五险一金"
  ```

---

### Task 2: Implement `mi.enrollment.line` and Fallback-Safe Math (`mi_core`)

**Files:**
- Modify: `mi_core/models/mi_enrollment.py`
- Modify: `mi_core/tests/test_mi_core.py`
- Modify: `mi_core/security/ir.model.access.csv`

**Interfaces:**
- Consumes: Expanded `mi.policy.line` record types.
- Produces: `mi.enrollment.line` Active Records and fallback-safe wage bracket calculations in `mi.enrollment`.

- [ ] **Step 2.1: Write failing TDD tests**
  Open `mi_core/tests/test_mi_core.py` and append:
  ```python
      def test_multibase_calculations_and_fallback(self):
          """Validate that contributions correctly use customized bases (social_security vs housing_fund) or fallback to main base"""
          # Setup Policy
          state_bj = self.env['res.country.state'].search([], limit=1)
          policy = self.env['mi.policy'].create({
              'name': 'Beijing Multi-Base Policy',
              'region_id': state_bj.id,
              'date_start': '2024-01-01',
              'state': 'active',
          })
          # Pension line: base_min 5000, base_max 25000, rates: 8% employer, 4% employee
          self.env['mi.policy.line'].create({
              'policy_id': policy.id,
              'insurance_type': 'pension',
              'base_min': 5000.0,
              'base_max': 25000.0,
              'rate_employer': 8.0,
              'rate_employee': 4.0,
          })
          # Housing Fund line: base_min 3000, base_max 30000, rates: 12% employer, 12% employee
          self.env['mi.policy.line'].create({
              'policy_id': policy.id,
              'insurance_type': 'housing_fund',
              'base_min': 3000.0,
              'base_max': 30000.0,
              'rate_employer': 12.0,
              'rate_employee': 12.0,
          })

          # Create Enrollment with base_amount = 6000
          enrollment = self.env['mi.enrollment'].create({
              'employee_id': self.env['hr.employee'].create({'name': 'Wang Wu'}).id,
              'policy_id': policy.id,
              'base_amount': 6000.0,
              'start_date': '2024-01-01',
          })

          # Scenario A: Fallback mode (no enrollment lines)
          # Pension base is 6000 -> 6000 * 8% = 480, 6000 * 4% = 240
          # Housing base is 6000 -> 6000 * 12% = 720, 6000 * 12% = 720
          # Employer total = 480 + 720 = 1200
          # Employee total = 240 + 720 = 960
          self.assertEqual(enrollment.amount_employer, 1200.0)
          self.assertEqual(enrollment.amount_employee, 960.0)

          # Scenario B: Custom line bases
          # Add custom line for housing_fund base = 4000 (different from pension/social security base)
          self.env['mi.enrollment.line'].create({
              'enrollment_id': enrollment.id,
              'insurance_type_group': 'housing_fund',
              'base_amount': 4000.0,
          })
          
          # Re-compute
          enrollment._compute_contributions()
          # Pension base still falls back to 6000 -> 6000 * 8% = 480 / 240
          # Housing base now uses 4000 -> 4000 * 12% = 480 / 480
          # Employer total = 480 + 480 = 960
          # Employee total = 240 + 480 = 720
          self.assertEqual(enrollment.amount_employer, 960.0)
          self.assertEqual(enrollment.amount_employee, 720.0)
  ```

- [ ] **Step 2.2: Run test to verify it fails**
  Verify failure with missing `mi.enrollment.line` model and fallback calculations.

- [ ] **Step 2.3: Implement `mi.enrollment.line` and fallback math**
  In `mi_core/models/mi_enrollment.py`, declare `MiEnrollmentLine`:
  ```python
  class MiEnrollmentLine(models.Model):
      _name = 'mi.enrollment.line'
      _description = 'Employee Multi-Base Insurance Line'

      enrollment_id = fields.Many2one('mi.enrollment', ondelete='cascade', required=True)
      insurance_type_group = fields.Selection([
          ('social_security', 'Social Security Unified Base (社保统一基数)'),
          ('housing_fund', 'Housing Fund Unified Base (公积金统一基数)'),
          ('pension', 'Pension Separate Base (养老单独基数)'),
          ('medical', 'Medical Separate Base (医疗单独基数)'),
          ('housing_fund_sep', 'Housing Fund Separate Base (公积金单独基数)')
      ], required=True, default='social_security')
      base_amount = fields.Float(required=True)
  ```
  Add relation to `mi.enrollment`:
  ```python
      line_ids = fields.One2many('mi.enrollment.line', 'enrollment_id', string='Custom Base Lines')
  ```
  Rewrite `_compute_contributions` inside `mi.enrollment`:
  ```python
      @api.depends('base_amount', 'policy_id', 'policy_id.line_ids', 'line_ids', 'line_ids.base_amount')
      def _compute_contributions(self):
          for rec in self:
              emp_total = 0.0
              p_total = 0.0
              if rec.policy_id:
                  # Map out customized bases from line_ids
                  custom_bases = {line.insurance_type_group: line.base_amount for line in rec.line_ids}
                  
                  for line in rec.policy_id.line_ids:
                      # Determine the applicable base following fallback rules:
                      # Specific Type Base -> Group Base -> Core Base
                      applicable_base = rec.base_amount
                      
                      if line.insurance_type == 'pension' and 'pension' in custom_bases:
                          applicable_base = custom_bases['pension']
                      elif line.insurance_type == 'medical' and 'medical' in custom_bases:
                          applicable_base = custom_bases['medical']
                      elif line.insurance_type in ['housing_fund', 'supp_housing_fund'] and 'housing_fund_sep' in custom_bases:
                          applicable_base = custom_bases['housing_fund_sep']
                      elif line.insurance_type in ['pension', 'medical', 'unemployment', 'injury', 'maternity'] and 'social_security' in custom_bases:
                          applicable_base = custom_bases['social_security']
                      elif line.insurance_type in ['housing_fund', 'supp_housing_fund'] and 'housing_fund' in custom_bases:
                          applicable_base = custom_bases['housing_fund']

                      actual_base = max(line.base_min, min(applicable_base, line.base_max))
                      emp_total += round(actual_base * (line.rate_employer / 100.0), 2)
                      p_total += round(actual_base * (line.rate_employee / 100.0), 2)
              rec.amount_employer = emp_total
              rec.amount_employee = p_total
  ```
  Expose security parameters inside `mi_core/security/ir.model.access.csv`:
  ```csv
  access_mi_enrollment_line,mi.enrollment.line,model_mi_enrollment_line,base.group_user,1,1,1,1
  ```

- [ ] **Step 2.4: Run test to verify it passes**
  Ensure all tests compile and execute cleanly.

- [ ] **Step 2.5: Commit**
  ```bash
  git commit -m "feat(mi_core): implement multi-base lines and contribution computation logic"
  ```

---

### Task 3: Expand Dry-Run Excel Import Validations (`mi_core`)

**Files:**
- Modify: `mi_core/models/base_import_override.py`
- Modify: `mi_core/tests/test_mi_core.py`

**Interfaces:**
- Consumes: File uploads targeting `mi.enrollment` records.
- Produces: Intercepted Excel validations against multi-base configurations.

- [ ] **Step 3.1: Write failing TDD tests**
  Open `mi_core/tests/test_mi_core.py` and append verification tests checks for custom line import bounds validation.

- [ ] **Step 3.2: Run test to verify it fails**
  Expected: FAIL (only main base validated, sub-lines ignored during excel dry-runs).

- [ ] **Step 3.3: Upgrade `_validate_mi_enrollments_pre_import` logic**
  Modify `mi_core/models/base_import_override.py` to loop through custom lines inside the imported stream if mapped or check boundaries dynamically for fallback bases of pension, housing funds, etc., making sure warning metrics flag correctly.

- [ ] **Step 3.4: Run test to verify it passes**
  Verify compilation and tests.

- [ ] **Step 3.5: Commit**
  ```bash
  git commit -m "feat(mi_core): support multi-base bounds validations in import override"
  ```

---

### Task 4: Expand Compliance Scanning Engine (`mi_compliance`)

**Files:**
- Modify: `mi_compliance/models/mi_compliance_scan.py`
- Modify: `mi_compliance/tests/test_mi_compliance.py`

**Interfaces:**
- Consumes: Complete active policies and enrollment structures from `mi_core`.
- Produces: Comprehensive五险一金 risk scanning results.

- [ ] **Step 4.1: Write failing TDD test**
  Modify `mi_compliance/tests/test_mi_compliance.py` to check that the risk engine identifies low-base risks for pension and housing funds and sums them in compliance totals correctly.

- [ ] **Step 4.2: Run test to verify it fails**
  Expected: FAIL.

- [ ] **Step 4.3: Upgrade Scanning Engine**
  Update `mi_compliance/models/mi_compliance_scan.py` to scan across all available active `policy.line_ids` (pension, unemployment, injury, housing_fund) instead of just basic medical insurance.
  Compute wage difference based on applicable custom or fallback enrollment bases.

- [ ] **Step 4.4: Run test to verify it passes**
  Verify compliance test suite execution.

- [ ] **Step 4.5: Commit**
  ```bash
  git commit -m "feat(mi_compliance): support full 五险一金 compliance risk scanning"
  ```
