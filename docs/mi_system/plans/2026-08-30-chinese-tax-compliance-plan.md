# Chinese Tax Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Year-end Bonus Separate Taxation and Severance Pay Exemption & Taxation rules on `cn.payslip` inside the `cn_payroll_tax` module, and write verification tests.

**Architecture:** Extend `cn.payslip` fields, update `_get_eval_context()` and introduce tax calculation helpers, and update `test_payroll_tax.py` with comprehensive assertions.

**Tech Stack:** Odoo 17, Python.

**Spec:** `docs/mi_system/plans/2026-08-30-chinese-tax-compliance-design.md`

## Global Constraints
*   **Think in Odoo:** Extend the existing safe_eval evaluation context in `cn_payroll_tax` cleanly to preserve standard formula-based payslip calculation behaviors.

---

### Task 1: Model Fields, Tax Formulas, and Context Overrides

**Files:**
- Modify: `cn_payroll_tax/models/cn_payslip_tax_override.py`

**Interfaces:**
- Produces: `payslip_type` and `severance_exemption_limit` columns, bonus and severance tax math.

- [ ] **Step 1: Add Fields and Formula Helpers to `cn_payslip_tax_override.py`**
Modify `CnPayslip` to declare the selection fields and the math formulas:

```python
    payslip_type = fields.Selection([
        ('salary', 'Regular Salary'),
        ('bonus', 'Year-end Bonus'),
        ('severance', 'Severance Pay')
    ], default='salary', string='Payslip Type', required=True)

    severance_exemption_limit = fields.Float(
        string='Severance Exemption Limit (3x Local Avg)',
        default=300000.0,
        help="Severance pay up to this limit is tax-free under PRC law. Excess is taxed separately."
    )

    def _calculate_monthly_bracket_tax(self, total_bonus):
        m_amount = total_bonus / 12.0
        if m_amount <= 3000:
            rate, quick_ded = 0.03, 0
        elif m_amount <= 12000:
            rate, quick_ded = 0.10, 210
        elif m_amount <= 25000:
            rate, quick_ded = 0.20, 1410
        elif m_amount <= 35000:
            rate, quick_ded = 0.25, 2660
        elif m_amount <= 55000:
            rate, quick_ded = 0.30, 4410
        elif m_amount <= 80000:
            rate, quick_ded = 0.35, 7160
        else:
            rate, quick_ded = 0.45, 15160
        return round(total_bonus * rate - quick_ded, 2)

    def _calculate_severance_tax(self, total_severance, exemption_limit):
        taxable_excess = max(0.0, total_severance - exemption_limit)
        if taxable_excess <= 0:
            return 0.0
        
        m_amount = taxable_excess / 3.0
        if m_amount <= 3000:
            rate, quick_ded = 0.03, 0
        elif m_amount <= 12000:
            rate, quick_ded = 0.10, 210
        elif m_amount <= 25000:
            rate, quick_ded = 0.20, 1410
        elif m_amount <= 35000:
            rate, quick_ded = 0.25, 2660
        elif m_amount <= 55000:
            rate, quick_ded = 0.30, 4410
        elif m_amount <= 80000:
            rate, quick_ded = 0.35, 7160
        else:
            rate, quick_ded = 0.45, 15160
            
        tax_part = m_amount * rate - quick_ded
        return round(tax_part * 3.0, 2)
```

- [ ] **Step 2: Update `_get_eval_context()`**
Update `_get_eval_context()` to switch between standard salary, bonus, and severance tax computations:

```python
    def _get_eval_context(self):
        res = super(CnPayslip, self)._get_eval_context()

        if self.payslip_type == 'bonus':
            iit_amount = self._calculate_monthly_bracket_tax(self.base_wage_amount)
        elif self.payslip_type == 'severance':
            iit_amount = self._calculate_severance_tax(self.base_wage_amount, self.severance_exemption_limit)
        else:
            # Regular cumulative salary taxation
            if '-' in self.period:
                year = int(self.period.split('-')[0])
                month = int(self.period.split('-')[1])
            else:
                year = fields.Date.today().year
                month = fields.Date.today().month

            ytd_ledger = self.env['cn.tax.ytd.record'].search([
                ('employee_id', '=', self.employee_id.id),
                ('year', '=', year)
            ], limit=1)
            if not ytd_ledger:
                ytd_ledger = self.env['cn.tax.ytd.record'].create({
                    'employee_id': self.employee_id.id,
                    'year': year
                })

            sihf_personal = res.get('SIHF_PERSONAL', 0.0)
            iit_amount = ytd_ledger.compute_monthly_iit(
                month=month,
                current_income=self.base_wage_amount,
                current_sihf=sihf_personal,
                current_special_add=self.special_additional_deduction,
                cumulative_paid_before=self.cumulative_paid_before
            )

        res.update({
            'IIT_AMOUNT': iit_amount,
        })
        return res
```

- [ ] **Step 3: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_tax/models/cn_payslip_tax_override.py`
```bash
git add cn_payroll_tax/
git commit -m "feat: implement year-end bonus separate tax and severance pay tax-exempt rules in tax override"
```

---

### Task 2: Write Verification Unit Tests

**Files:**
- Modify: `cn_payroll_tax/tests/test_payroll_tax.py`

**Interfaces:**
- Produces: `test_year_end_bonus_separate_tax_calculation` and `test_severance_pay_exemption_and_taxation`.

- [ ] **Step 1: Append Unit Tests**
Add the new tests to `TestPayrollTax`:

```python
    def test_year_end_bonus_separate_tax_calculation(self):
        """Verify standard Chinese Year-end Bonus separate tax algorithm and brackets"""
        # Create year-end bonus slip of 60000.0 RMB
        struct = self.env['cn.salary.structure'].create({
            'name': 'Bonus Structure',
            'item_ids': [],
        })
        payslip = self.env['cn.payslip'].create({
            'employee_id': self.employee.id,
            'structure_id': struct.id,
            'period': '2024-12',
            'base_wage_amount': 60000.0,
            'payslip_type': 'bonus',
        })
        eval_ctx = payslip._get_eval_context()
        # 60000 / 12 = 5000 quotient. Falls into 10% rate, 210 quick deduction.
        # Tax = 60000 * 10% - 210 = 5790.0
        self.assertEqual(eval_ctx.get('IIT_AMOUNT'), 5790.0)

    def test_severance_pay_exemption_and_taxation(self):
        """Verify PRC Labor Contract severance exemption thresholds (3x local avg) and 3-year amortization tax lookup"""
        struct = self.env['cn.salary.structure'].create({
            'name': 'Severance Structure',
            'item_ids': [],
        })
        
        # 1. Under exemption threshold (250,000 <= 300,000 limit)
        payslip_exempt = self.env['cn.payslip'].create({
            'employee_id': self.employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 250000.0,
            'payslip_type': 'severance',
            'severance_exemption_limit': 300000.0,
        })
        eval_ctx_exempt = payslip_exempt._get_eval_context()
        self.assertEqual(eval_ctx_exempt.get('IIT_AMOUNT'), 0.0)
        
        # 2. Exceeds exemption threshold (440,000 > 300,000 limit)
        # Taxable excess = 140000.0
        # 140000 / 3 = 46666.67 quotient. Falls into 30% rate, 4410 quick deduction.
        # Tax part = 46666.67 * 30% - 4410 = 14000.00 - 4410 = 9590.00.
        # Total Tax = 9590.00 * 3 = 28770.0
        payslip_taxable = self.env['cn.payslip'].create({
            'employee_id': self.employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 440000.0,
            'payslip_type': 'severance',
            'severance_exemption_limit': 300000.0,
        })
        eval_ctx_taxable = payslip_taxable._get_eval_context()
        self.assertEqual(eval_ctx_taxable.get('IIT_AMOUNT'), 28770.0)
```

- [ ] **Step 2: Syntax Check & Commit**
Run: `python3 -m py_compile cn_payroll_tax/tests/test_payroll_tax.py`
```bash
git add cn_payroll_tax/tests/test_payroll_tax.py
git commit -m "test: add tax compliance unit tests for separate bonus tax and severance pay amortization"
```
