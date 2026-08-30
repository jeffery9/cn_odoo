# PRC Ultimate Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all four final high-risk Chinese compliance features sequentially and write automated verification tests:
1.  **PRC 7 Special Additional Tax Deductions Validation** (`cn_payroll_tax`).
2.  **Statutory Overtime 36-Hour Monthly Limit Warning** (`cn_payroll_core`).
3.  **Probation Period term and wage audits** (`cn_payroll_core` / `cn_payroll_outsourcing`).
4.  **Female Employee "Three Periods" Dismissal Prevention** (`cn_payroll_core` / `cn_payroll_outsourcing`).

**Tech Stack:** Odoo 17, Python.

**Spec:** `docs/mi_system/plans/2026-08-30-prc-ultimate-compliance-design.md`

---

### Task 1: PRC 7 Special Additional Tax Deductions Validation

**Files:**
- Modify: `cn_payroll_tax/models/cn_payslip_tax_override.py`

- [ ] **Step 1: Declare Fields & Computed Total on `CnPayslip`**
Extend the class with the 7 individual deduction fields, and make `special_additional_deduction` computed:

```python
    deduction_child_education = fields.Float(string="Children Education Deduction", default=0.0)
    deduction_continuing_education = fields.Float(string="Continuing Education Deduction", default=0.0)
    deduction_housing_loan = fields.Float(string="Housing Loan Interest Deduction", default=0.0)
    deduction_housing_rent = fields.Float(string="Housing Rent Deduction", default=0.0)
    deduction_elderly_care = fields.Float(string="Supporting the Elderly Deduction", default=0.0)
    deduction_infant_care = fields.Float(string="Under 3 Infant Care Deduction", default=0.0)

    special_additional_deduction = fields.Float(
        compute='_compute_total_special_additional_deduction',
        store=True,
        string="Total Special Additional Deduction"
    )

    @api.depends(
        'deduction_child_education', 'deduction_continuing_education',
        'deduction_housing_loan', 'deduction_housing_rent',
        'deduction_elderly_care', 'deduction_infant_care'
    )
    def _compute_total_special_additional_deduction(self):
        for rec in self:
            rec.special_additional_deduction = (
                rec.deduction_child_education + rec.deduction_continuing_education +
                rec.deduction_housing_loan + rec.deduction_housing_rent +
                rec.deduction_elderly_care + rec.deduction_infant_care
            )
```

- [ ] **Step 2: Add Constraints Validation**
Add validation for limit caps and mutual exclusion rules:

```python
    @api.constrains(
        'deduction_child_education', 'deduction_continuing_education',
        'deduction_housing_loan', 'deduction_housing_rent',
        'deduction_elderly_care', 'deduction_infant_care'
    )
    def _check_special_deduction_limits(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            # 1. Mutual Exclusion: Housing rent and loan interest cannot both be claimed
            if rec.deduction_housing_loan > 0.0 and rec.deduction_housing_rent > 0.0:
                raise ValidationError(
                    "Compliance Error: Housing Loan Interest and Housing Rent "
                    "deductions cannot be claimed simultaneously under PRC Individual Income Tax Law."
                )
            
            # 2. Limit Cap Verification
            limits = {
                'Children Education': (rec.deduction_child_education, 2000.0),
                'Continuing Education': (rec.deduction_continuing_education, 400.0),
                'Housing Loan Interest': (rec.deduction_housing_loan, 1000.0),
                'Housing Rent': (rec.deduction_housing_rent, 1500.0),
                'Supporting the Elderly': (rec.deduction_elderly_care, 3000.0),
                'Under 3 Infant Care': (rec.deduction_infant_care, 2000.0),
            }
            for name, (val, cap) in limits.items():
                if val > cap:
                    raise ValidationError(
                        f"Compliance Error: {name} deduction of {val} RMB exceeds "
                        f"the maximum statutory monthly limit of {cap} RMB under PRC Tax Law."
                    )
```

- [ ] **Step 3: Add Unit Test**
In `cn_payroll_tax/tests/test_payroll_tax.py`, write `test_special_additional_deductions_limit_and_exclusion_checks`.

---

### Task 2: Statutory Overtime 36-Hour Monthly Limit Warning

**Files:**
- Modify: `cn_payroll_core/models/cn_attendance_summary.py`

- [ ] **Step 1: Declare Warning Fields**
Add `overtime_status` and `total_overtime_hours` fields to `cn.attendance.summary` model:

```python
    overtime_status = fields.Selection([
        ('normal', 'Normal'),
        ('warning', 'Exceeds Statutory 36-Hour Limit')
    ], default='normal', string='Statutory Overtime Compliance')

    total_overtime_hours = fields.Float(compute='_compute_total_overtime', string='Total Overtime Hours', store=True)

    @api.depends('overtime_weekday_hours', 'overtime_weekend_hours', 'overtime_holiday_hours')
    def _compute_total_overtime(self):
        for rec in self:
            rec.total_overtime_hours = (
                rec.overtime_weekday_hours + rec.overtime_weekend_hours + rec.overtime_holiday_hours
            )
            # Raise warning if > 36 hours
            if rec.total_overtime_hours > 36.0:
                rec.overtime_status = 'warning'
                # Log a note on chatter (if available)
                if hasattr(rec, 'message_post'):
                    rec.message_post(
                        body=f"🚨 <b>Statutory Alert:</b> Employee monthly overtime is <b>{rec.total_overtime_hours} hours</b>, "
                             f"exceeding the Chinese Labor Law mandatory legal ceiling of 36 hours!"
                    )
            else:
                rec.overtime_status = 'normal'
```

- [ ] **Step 2: Add Unit Test**
In `cn_payroll_core/tests/test_payroll_core.py`, write `test_monthly_overtime_36_hour_limit_audit_warning`.

---

### Task 3: Probation Term & Salary Audit

**Files:**
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_contract.py` (which contains `HrEmployee` declaration)

- [ ] **Step 1: Declare Fields on `HrEmployee`**
Add the probation audit fields:

```python
    contract_term_months = fields.Integer(string="Contract Term (Months)", default=0)
    probation_term_months = fields.Integer(string="Probation Term (Months)", default=0)
    wage_regular = fields.Float(string="Regular Wage", default=0.0)
    wage_probation = fields.Float(string="Probation Wage", default=0.0)
```

- [ ] **Step 2: Add Probation Constraints**
Add `@api.constrains` checking contract probation limits and minimum 80% wage thresholds:

```python
    @api.constrains('contract_term_months', 'probation_term_months', 'wage_regular', 'wage_probation')
    def _check_probation_compliance(self):
        for rec in self:
            # Skip check if no probation is configured
            if rec.probation_term_months <= 0:
                continue

            # 1. Check Duration Rules under Article 19 of PRC Labor Contract Law
            t_months = rec.contract_term_months
            p_months = rec.probation_term_months
            
            if t_months < 3:
                raise ValidationError(
                    f"Compliance Error: Contract of employee {rec.name} is shorter than 3 months. "
                    f"Under Article 19 of PRC Labor Contract Law, probation period is NOT allowed for terms under 3 months."
                )
            elif t_months >= 3 and t_months < 12:
                if p_months > 1:
                    raise ValidationError(
                        f"Compliance Error: Employee {rec.name} has a contract term of {t_months} months. "
                        f"Under PRC Law, probation period cannot exceed 1 month."
                    )
            elif t_months >= 12 and t_months < 36:
                if p_months > 2:
                    raise ValidationError(
                        f"Compliance Error: Employee {rec.name} has a contract term of {t_months} months. "
                        f"Under PRC Law, probation period cannot exceed 2 months."
                    )
            else: # >= 36 months or open-ended
                if p_months > 6:
                    raise ValidationError(
                        f"Compliance Error: Employee {rec.name} has a contract term of {t_months} months. "
                        f"Under PRC Law, probation period cannot exceed 6 months."
                    )

            # 2. Check Wage Rules under Article 20 of PRC Labor Contract Law (Min 80%)
            if rec.wage_regular > 0.0:
                min_probation_wage = rec.wage_regular * 0.8
                if rec.wage_probation < min_probation_wage:
                    raise ValidationError(
                        f"Compliance Error: Employee {rec.name} probation wage ({rec.wage_probation} RMB) "
                        f"is lower than 80% of trans-regular wage ({rec.wage_regular} RMB). "
                        f"This violates Article 20 of PRC Labor Contract Law."
                    )
```

- [ ] **Step 3: Add Unit Test**
In `cn_payroll_outsourcing/tests/test_outsourcing.py`, write `test_probation_period_compliance_validation`.

---

### Task 4: Female Employee "Three Periods" Dismissal Prevention

**Files:**
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_contract.py` (which contains `HrEmployee` declaration)

- [ ] **Step 1: Declare Protection Field on `HrEmployee`**
Add the selection field tracking "Three Periods" state:

```python
    female_protection_state = fields.Selection([
        ('none', 'None'),
        ('pregnancy', 'Pregnancy (孕期)'),
        ('maternity', 'Maternity Leave (产期)'),
        ('lactation', 'Lactation / Breastfeeding (哺乳期)')
    ], default='none', string="Female Special Protection State")
```

- [ ] **Step 2: Override `write` to block Archiving / Terminating**
In Odoo, employees are deactivated/dismissed by setting `active = False`. Intercept this:

```python
    def write(self, vals):
        # Intercept archival (active = False)
        if 'active' in vals and not vals['active']:
            for rec in self:
                if rec.female_protection_state and rec.female_protection_state != 'none':
                    raise ValidationError(
                        f"Compliance Lock: Employee {rec.name} is currently under special "
                        f"legal protection ({rec.get_female_protection_label()}). "
                        f"Under Article 42 of the PRC Labor Contract Law, "
                        f"dismissing, deactivating, or archiving her contract is strictly prohibited!"
                    )
        return super(HrEmployee, self).write(vals)

    def get_female_protection_label(self):
        state_labels = {
            'pregnancy': 'Pregnancy (孕期)',
            'maternity': 'Maternity (产期)',
            'lactation': 'Lactation (哺乳期)',
        }
        return state_labels.get(self.female_protection_state, 'Unknown')
```

- [ ] **Step 3: Add Unit Test**
In `cn_payroll_outsourcing/tests/test_outsourcing.py`, write `test_female_worker_three_periods_dismissal_blocking`.
