# Master TDD Plan: Advanced PRC HR & Tax Compliance

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all four high-risk Chinese compliance features sequentially:
1.  **Priority 1**: Minimum Wage Supplement (`MINIMUM_WAGE_MAKEUP` engine).
2.  **Priority 2**: Non-Resident Taxpayer Separate Bracket Taxation.
3.  **Priority 3**: Labor Dispatch 10% Ratio Cap Active Enforcement Constraint.
4.  **Priority 4**: Disability Employment Security Fund (残保金) Monthly Pre-accounting Accrual.

**Tech Stack:** Odoo 17, Python.

---

### Task 1: Minimum Wage Earning Supplement Engine (Priority 1)

**Files:**
- Modify: `cn_payroll_core/models/cn_payslip.py`

- [ ] **Step 1: Add Local Minimum Wage Parameter to Payslip**
Add `local_minimum_wage = fields.Float(string='Local Monthly Minimum Wage', default=2690.0)` to `CnPayslip`.

- [ ] **Step 2: Inject Minimum Wage Makeup into context**
Update `_get_eval_context()` in `cn_payroll_core/models/cn_payslip.py` to calculate net wage before tax and automatically inject `MINIMUM_WAGE_MAKEUP`:

```python
        # Estimate net wage (Wage - Deductions before makeup)
        # 1. Base Wage
        base_val = self.base_wage_amount
        # 2. Estimate other deductions (e.g. attendance deductions)
        # To avoid circularity in safe_eval, we can compute regular earnings/deductions
        # or perform a safe pre-evaluation. If we simulate standard Odoo behavior:
        # Net before makeup is base_wage - standard SIHF - tax.
        # If this net is lower than the minimum wage, we inject a makeup amount.
        sihf_personal = res.get('SIHF_PERSONAL', 0.0)
        iit_amount = res.get('IIT_AMOUNT', 0.0)
        
        pre_net = base_val - sihf_personal - iit_amount
        makeup = max(0.0, self.local_minimum_wage - pre_net)
        
        res.update({
            'MINIMUM_WAGE_MAKEUP': makeup,
        })
```

- [ ] **Step 3: Add Unit Test**
Modify `cn_payroll_core/tests/test_payroll_core.py` to assert that if basic wage minus SIHF drops below 2690.0 RMB, `MINIMUM_WAGE_MAKEUP` is correctly computed.

---

### Task 2: Non-Resident Taxpayer Separate Amortized/Single-Month Calculation (Priority 2)

**Files:**
- Modify: `hr.employee` / `cn_payroll_tax/models/cn_payslip_tax_override.py`

- [ ] **Step 1: Add Resident Status to Employee and Payslip**
In `cn_payroll_tax/models/cn_payslip_tax_override.py`:
Extend `hr.employee` to add `resident_status` and map it to `CnPayslip`:

```python
class HrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    resident_status = fields.Selection([
        ('resident', 'Resident Individual'),
        ('non_resident', 'Non-Resident Individual')
    ], default='resident', string='Resident Status', required=True)
```

On `CnPayslip`:
```python
    resident_status = fields.Selection(
        related='employee_id.resident_status',
        store=True,
        string='Resident Status',
        readonly=True
    )
```

- [ ] **Step 2: Enforce Monthly Bracket Tax for Non-Residents**
Update `_get_eval_context()` inside `cn_payroll_tax/models/cn_payslip_tax_override.py` to branch if `resident_status == 'non_resident'`:

```python
        if self.resident_status == 'non_resident':
            # Non-residents are taxed per-month individually with 5,000 RMB exemption
            taxable_income = max(0.0, self.base_wage_amount - 5000.0)
            iit_amount = self._calculate_monthly_bracket_tax(taxable_income)
```

- [ ] **Step 3: Add Unit Test**
In `cn_payroll_tax/tests/test_payroll_tax.py`, write `test_non_resident_individual_monthly_tax_calculation`.

---

### Task 3: Labor Dispatch 10% Ratio Cap Active Enforcement Constraint (Priority 3)

**Files:**
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_assignment.py`

- [ ] **Step 1: Enforce 10% Cap Active Check on Assignment Creation**
Add validation checking ratio threshold inside `cn_payroll_outsourcing/models/cn_outsourcing_assignment.py`:

```python
    @api.constrains('employee_id', 'contract_id', 'date_start', 'date_end')
    def _check_dispatch_ratio_limit(self):
        from odoo.exceptions import ValidationError
        
        for rec in self:
            # Only count if the assignment is active
            if rec.date_end and rec.date_end < fields.Date.today():
                continue
                
            # Total Formal Employees (non-outsourced)
            total_formal = self.env['hr.employee'].search_count([
                ('id', 'not in', self.env['cn.outsourcing.assignment'].search([
                    ('date_start', '<=', fields.Date.today()),
                    '|', ('date_end', '=', False), ('date_end', '>=', fields.Date.today())
                ]).mapped('employee_id.id'))
            ])
            
            # Total Active Outsourced
            total_active_outsourced = self.env['cn.outsourcing.assignment'].search_count([
                ('date_start', '<=', fields.Date.today()),
                '|', ('date_end', '=', False), ('date_end', '>=', fields.Date.today())
            ])
            
            # Prevent DivisionByZero and check 10% threshold
            total_workforce = total_formal + total_active_outsourced
            if total_workforce > 0:
                ratio = (total_active_outsourced / total_workforce) * 100.0
                if ratio > 10.0:
                    raise ValidationError(
                        f"Compliance Breach: Total labor dispatch workforce ratio is {ratio:.2f}%, "
                        f"which exceeds the Chinese Labor Law mandatory legal limit of 10.00%. "
                        f"Assignment of worker {rec.employee_id.name} is blocked to avoid audit fines."
                    )
```

- [ ] **Step 2: Add Unit Test**
In `cn_payroll_outsourcing/tests/test_outsourcing.py`, write `test_dispatch_ratio_10_percent_compliance_blocking`.

---

### Task 4: Disability Employment Security Fund Monthly Pre-accounting Accrual (Priority 4)

**Files:**
- Modify: `cn_payroll_outsourcing/models/cn_outsourcing_contract.py` (inherits `hr.employee`)
- Modify: `cn_payroll_tax/models/cn_payslip_tax_override.py` (accrues on payslip)

- [ ] **Step 1: Add Disability Flags**
On `hr.employee` in `cn_payroll_outsourcing/models/cn_outsourcing_contract.py`:
```python
    is_disabled = fields.Boolean(default=False, string='Has Disability Certification')
```

- [ ] **Step 2: Add Disability Pre-accounting Estimation**
Add `estimated_disability_security_levy = fields.Float(compute='_compute_disability_levy', string='Est Disability Levy Accrual', store=True)` to `CnPayslip` in `cn_payroll_tax/models/cn_payslip_tax_override.py`:

```python
    estimated_disability_security_levy = fields.Float(compute='_compute_disability_levy', string='Est Disability Levy Accrual', store=True)

    @api.depends('base_wage_amount', 'company_id')
    def _compute_disability_levy(self):
        for rec in self:
            # 1. Total formal employees in the same company
            total_employees = self.env['hr.employee'].search_count([
                ('company_id', '=', rec.company_id.id)
            ]) or 1
            
            # 2. Total disabled employees in the same company
            disabled_count = self.env['hr.employee'].search_count([
                ('company_id', '=', rec.company_id.id),
                ('is_disabled', '=', True)
            ])
            
            # PRC target: 1.5% of workforce
            target_count = total_employees * 0.015
            deficit = max(0.0, target_count - disabled_count)
            
            # Monthly levy = deficit * company monthly average wage (using current base wage as projection)
            rec.estimated_disability_security_levy = round(deficit * rec.base_wage_amount, 2)
```

- [ ] **Step 3: Add Unit Test**
In `cn_payroll_tax/tests/test_payroll_tax.py`, write `test_disability_security_levy_monthly_accrual`.
