# Specification: Chinese Tax Compliance (Bonus & Severance)

## 1. Architectural Intent
To achieve 100% legal compliance with the State Taxation Administration of China (国家税务总局) and the PRC Individual Income Tax (IIT) Law, the payroll and tax engines must support advanced tax-minimization calculations for non-salary compensation.

We will implement two critical legal-compliance taxation modules:
1.  **Year-end Bonus Separate Taxation (全年一次性奖金单独计税)**:
    - Under standard tax planning policy, a year-end bonus can be calculated separately from regular monthly salaries to avoid progressive bracket jump.
2.  **Severance Pay Exemption & Taxation (离职补偿金免税与单独计税)**:
    - Under PRC labor contract law, severance pay up to 3 times the local previous year's average annual salary is fully tax-exempt. Excess amounts are taxed separately using a 3-year amortization tax schedule.

---

## 2. Model Extensions on `cn.payslip`

We will add fields to the standard payslip model to support these categories:
*   `payslip_type`: Selection field:
    *   `'salary'` (Regular Salary, default)
    *   `'bonus'` (Year-end Bonus)
    *   `'severance'` (Severance Pay)
*   `severance_exemption_limit`: Float field (Default: 300,000.0 RMB, reflecting the typical Tier-1 city threshold of 3x average salary of approx 100,000 RMB).

---

## 3. Mathematical Formula Formulations

### 3.1. Year-end Bonus Separate Tax
*   Let $B$ be the year-end bonus amount.
*   Divide $B$ by 12 to find the monthly quotient: $Q = B / 12$.
*   Lookup $Q$ in the standard PRC monthly progressive tax bracket table to identify Tax Rate $R$ and Quick Deduction $D$:
    $$\text{Tax}_{\text{Bonus}} = B \times R - D$$

### 3.2. Severance Pay Exemption & Tax
*   Let $S$ be the total severance pay.
*   Let $L$ be the `severance_exemption_limit` (3x local average).
*   The taxable excess is $E = \max(0, S - L)$.
*   Divide $E$ by 3 to amortize it over a 3-year term: $A = E / 3$.
*   Lookup $A$ in the standard monthly tax bracket table to identify Rate $R$ and Quick Deduction $D$:
    $$\text{Tax}_{\text{Severance}} = (A \times R - D) \times 3$$
