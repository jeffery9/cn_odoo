# Specification: PRC Ultimate Labor & Tax Compliance Protection

## 1. Architectural Intent
To deliver the most complete, bulletproof enterprise legal compliance suite for Chinese labor and individual income tax laws. This module implements the "ultimate four" legal-compliance constraints:
1.  **PRC 7 Special Additional Tax Deductions Validation**:
    - Ensures employees' monthly individual tax deductions do not exceed legal ceilings and blocks dual claiming of housing loans and housing rents.
2.  **Statutory Overtime 36-Hour Monthly Limit Warning**:
    - Automatically audits and raises compliance warning flags if total monthly overtime exceeds the 36-hour statutory ceiling.
3.  **Probation Period statutory term and wage audit constraints**:
    - Ensures probation durations do not violate Labor Contract Law boundaries based on contract length and checks that probation pay is at least 80% of trans-regular wages.
4.  **Female Employee "Three Periods" Labor Protection Sentry**:
    - Transactionally blocks archiving or dismissing female workers currently in Pregnancy, Maternity, or Lactation states.

---

## 2. Model Extensions

### 2.1. PRC 7 Special Additional Tax Deductions (`cn.payslip`)
*   `deduction_child_education`: Children's Education (Max 2,000 RMB/month)
*   `deduction_continuing_education`: Continuing Education (Max 400 RMB/month)
*   `deduction_housing_loan`: Housing Loan Interest (Max 1,000 RMB/month)
*   `deduction_housing_rent`: Housing Rent (Max 1,500 RMB/month)
*   `deduction_elderly_care`: Supporting the Elderly (Max 3,000 RMB/month)
*   `deduction_infant_care`: Under 3 Infant Care (Max 2,000 RMB/month)
*   `special_additional_deduction`: Computed stored float (sum of above).

**Validation rules:**
- `deduction_housing_loan > 0` and `deduction_housing_rent > 0` must trigger `ValidationError` (Mutual Exclusion).
- Individual project caps are strictly enforced on each field.

### 2.2. Overtime Audit (`cn.attendance.summary`)
*   `overtime_status`: Selection: `['normal', 'warning']` (Default: `'normal'`)
*   `total_overtime_hours`: Float.
*   If `total_overtime_hours > 36.0`, `overtime_status` is automatically set to `'warning'` and logged in Odoo Chatter.

### 2.3. Probation Term & Salary Audit (`hr.employee`)
*   `contract_term_months`: Integer
*   `probation_term_months`: Integer
*   `wage_regular`: Float
*   `wage_probation`: Float

**Validation rules:**
- Term checks:
  - If contract < 3 months: probation = 0.
  - If contract 3 months $\le$ term < 12 months: probation $\le$ 1.
  - If contract 12 months $\le$ term < 36 months: probation $\le$ 2.
  - If contract $\ge$ 36 months: probation $\le$ 6.
- Wage check:
  - `wage_probation >= 0.8 * wage_regular`.

### 2.4. Female "Three Periods" sentry (`hr.employee`)
*   `female_protection_state`: Selection: `['none', 'pregnancy', 'maternity', 'lactation']` (Default: `'none'`)
*   If `active` is changed from `True` to `False` (Archived/Dismissed) and `female_protection_state != 'none'`:
    - Raise `ValidationError` and block transaction.
