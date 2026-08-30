# Spec: Medical Insurance (MI) System

## 1. Business Objective
To streamline and centralize medical insurance management into a highly cohesive, loosely coupled 3-module architecture (`mi_core`, `mi_compliance`, `mi_connector`). This design eliminates redundant legacy modules, leverages Odoo-native features (e.g., `mail.thread` for audit, `base_import` for batch data), ensures accurate policy calculations, provides robust compliance tracking, and facilitates seamless external API integrations.

---

## 2. Logical Domain Model & Schema Specifications

Following **Option A (Header-Line Model)** for policy rules and **Option A (Attachment + Hash Archive)** for evidence tracking:

### 2.1. `mi_core` Models

#### `mi.policy` (医保政策主表)
*   **Description:** Configures policies for specific regional billing cities with version dates.
*   **Fields:**
    *   `name` (`Char`, Required): Name of the policy (e.g., "北京市 2024 年度职工医保政策").
    *   `region_id` (`Many2one`, `res.country.state` or custom region, Required): Administrative area.
    *   `date_start` (`Date`, Required, Default=Today): Policy commencement threshold.
    *   `state` (`Selection`: `draft` (草稿), `active` (生效中), `expired` (已失效)): Version lifecycle state.
    *   `line_ids` (`One2many`, `mi.policy.line`, `policy_id`): List of associated insurance rates.
*   **SQL Constraints:**
    *   Unique constraint on `(region_id, date_start)` to prevent multiple overlapping policies starting on the same day for the same city.

#### `mi.policy.line` (医保政策明细表)
*   **Description:** Individual insurance configurations mapping specific insurance types (险种).
*   **Fields:**
    *   `policy_id` (`Many2one`, `mi.policy`, OnDelete='cascade', Required): Parent header.
    *   `insurance_type` (`Selection`: `basic` (基本医疗), `illness` (大病互助), `maternity` (生育险)): Insurance type.
    *   `base_min` (`Float`, Required): Underpayment floor.
    *   `base_max` (`Float`, Required): Underpayment ceiling.
    *   `rate_employer` (`Float`, Required): Employer rate percentage (e.g., 9.8).
    *   `rate_employee` (`Float`, Required): Employee rate percentage (e.g., 2.0).

#### `mi.enrollment` (员工参保登记表)
*   **Description:** Tracks personal enrollments, salary bases, and status of in-scope employees.
*   **Inherits:** `mail.thread`, `mail.activity.mixin` (Chatter logging).
*   **Fields:**
    *   `employee_id` (`Many2one`, `hr.employee`, Required, Tracking=True): Target employee.
    *   `policy_id` (`Many2one`, `mi.policy`, Required, Tracking=True): Active policy template.
    *   `base_amount` (`Float`, Required, Tracking=True): Declared base wage.
    *   `state` (`Selection`: `draft` (草稿), `pending` (待申报), `enrolled` (在保), `terminated` (停保), Tracking=True): Operational state.
    *   `start_date` (`Date`, Required, Tracking=True): Date insurance starts.
    *   `end_date` (`Date`, Tracking=True): Date insurance terminates.
    *   `amount_employer` (`Float`, Compute='_compute_contributions', Store=True): Monthly calculated employer expense.
    *   `amount_employee` (`Float`, Compute='_compute_contributions', Store=True): Monthly calculated employee expense.
*   **Compute Logic:**
    ```python
    @api.depends('base_amount', 'policy_id', 'policy_id.line_ids')
    def _compute_contributions(self):
        for rec in self:
            emp_total = 0.0
            p_total = 0.0
            if rec.policy_id:
                for line in rec.policy_id.line_ids:
                    # Actual Base = Max(Min, Min(Salary, Max))
                    actual_base = max(line.base_min, min(rec.base_amount, line.base_max))
                    emp_total += round(actual_base * (line.rate_employer / 100.0), 2)
                    p_total += round(actual_base * (line.rate_employee / 100.0), 2)
            rec.amount_employer = emp_total
            rec.amount_employee = p_total
    ```

---

### 2.2. `mi_compliance` Models

#### `mi.compliance.scan` (深度合规风险扫描主表)
*   **Description:** Performs dynamic organization-wide compliance scanning.
*   **Fields:**
    *   `name` (`Char`, Readonly): Unique reference (e.g., "SCAN/2024/0001").
    *   `scan_date` (`Date`, Default=Today): Execution boundary.
    *   `company_id` (`Many2one`, `res.company`, Required): Bound active company.
    *   `total_penalty_estimate` (`Float`, Compute='_compute_totals'): Aggregated late fee penalty estimation.
    *   `risk_line_ids` (`One2many`, `mi.compliance.risk.line`, `scan_id`): Identified issues.
    *   `state` (`Selection`: `draft` (草稿), `done` (完成)): Scanner status.

#### `mi.compliance.risk.line` (合规风险明细表)
*   **Description:** Extracted anomalies mapping employees to identified risk vectors.
*   **Fields:**
    *   `scan_id` (`Many2one`, `mi.compliance.scan`, Required): Parent scanner.
    *   `employee_id` (`Many2one`, `hr.employee`, Required): Under-review employee.
    *   `risk_type` (`Selection`: `missing` (缺失参保), `low_base` (基数偏低), `break_缴` (历史断缴)): Classification.
    *   `base_declared` (`Float`): Currently declared amount.
    *   `base_expected` (`Float`): Under-policy lower threshold or true wage.
    *   `months_overdue` (`Integer`): Evaluated overdue periods.
    *   `amount_principal` (`Float`): Underpaid principal total.
    *   `amount_penalty` (`Float`): Estimated late-payment penalty (0.05% per day).
    *   `description` (`Text`): Remediation details and text notes.

#### `mi.audit.archive` (合规证据链防篡改归档表)
*   **Description:** Audit registry preserving generation state and SHA-256 validation signatures.
*   **Fields:**
    *   `employee_id` (`Many2one`, `hr.employee`, Required, Readonly): Insured resource.
    *   `archive_date` (`Datetime`, Default=Now, Readonly): Creation timestamp.
    *   `user_id` (`Many2one`, `res.users`, Default=Self, Readonly): Operating auditor.
    *   `attachment_id` (`Many2one`, `ir.attachment`, Required, Readonly): PDF reference document.
    *   `sha256_hash` (`Char`, Size=64, Required, Readonly): Generated secure checksum.

---

### 2.3. `mi_connector` Models

#### `mi.api.log` (API 交互日志表)
*   **Description:** Prevents high-frequency network timeouts from freezing transactional threads.
*   **Fields:**
    *   `name` (`Char`): Transaction ID.
    *   `request_data` (`Text`): Outbound payload records.
    *   `response_data` (`Text`): Return data block.
    *   `state` (`Selection`: `pending`, `success`, `failed`): Communication integrity state.
    *   `res_model` (`Char`): Linked business model (e.g., `mi.enrollment`).
    *   `res_id` (`Integer`): Linked business record ID.

---

## 3. Core Business Calculations & Calculations Engine

### 3.1. Standard Monthly Calculation Formulation
$$\text{Actual Base} = \max\Big(\text{Base}_{\min}, \min\big(\text{Salary}, \text{Base}_{\max}\big)\Big)$$
$$\text{Employer Cost} = \text{Actual Base} \times \text{Rate}_{\text{employer}} \quad [\text{rounded to 2 decimal places}]$$
$$\text{Employee Cost} = \text{Actual Base} \times \text{Rate}_{\text{employee}} \quad [\text{rounded to 2 decimal places}]$$

### 3.2. Late Payment Penalty Calculation (滞纳金)
Under the PRC Social Insurance Law (社会保险法), underpaid contributions accumulate a daily penalty of **0.05%** (万分之五) starting from the date of default:
$$\text{Late Fee}_m = \text{Principal}_m \times 0.0005 \times \text{Days Overdue}_m$$
$$\text{Total Penalty} = \sum \big(\text{Principal}_m + \text{Late Fee}_m\big)$$

---

## 4. Meta-Feature Extensions & Hooks

### 4.1. Overriding `base_import.import` (Epic 2.2)
To achieve zero-overhead excel analysis, `mi_core` overrides Odoo's standard `base_import.import` wizard execution pipeline:
```python
class Import(models.TransientModel):
    _inherit = 'base_import.import'

    def execute_import(self, fields, columns, options, dryrun=False):
        # Triggered only when target model is 'mi.enrollment'
        if self.res_model == 'mi.enrollment':
            # Execute pre-import validations across lines
            self._validate_mi_enrollment_records(fields, columns, options)
        return super(Import, self).execute_import(fields, columns, options, dryrun=dryrun)

    def _validate_mi_enrollment_records(self, fields, columns, options):
        # 1. Read input rows
        # 2. Match region_id rules and base wage limits
        # 3. Raise ValidationError or append warning lines directly into standard import result arrays if dryrun is executed
        pass
```

### 4.2. QWeb Report & SHA-256 Signature Hook
When the auditor requests `mi.audit.archive` generation, the system renders the QWeb layout, converts it to PDF, hashes the binary contents, and updates the view rendering context:
```python
import hashlib

def generate_evidence_chain_pdf(self, employee):
    # 1. Render QWeb template to PDF string
    pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
        'mi_compliance.report_evidence_template', [employee.id]
    )
    # 2. Generate SHA-256 hash checksum
    file_hash = hashlib.sha256(pdf_content).hexdigest()
    
    # 3. Create Attachment
    attachment = self.env['ir.attachment'].create({
        'name': f"{employee.name}_evidence_{fields.Date.today()}.pdf",
        'type': 'binary',
        'raw': pdf_content,
        'res_model': 'hr.employee',
        'res_id': employee.id,
    })
    
    # 4. Record to Audit Archive
    self.env['mi.audit.archive'].create({
        'employee_id': employee.id,
        'attachment_id': attachment.id,
        'sha256_hash': file_hash,
    })
```

---

## 5. View Hierarchies & Actions

*   **`mi_core` UI:** Form & List views for `mi.policy` (Header-Line form mapping), and standard chatter-enabled list/form tracking for `mi.enrollment`.
*   **`mi_compliance` UI:** High-impact status dashboards containing key performance metrics (Compliant rate, overall outstanding late fees, non-enrolled counts) and a wizard for running deep risk scans.
*   **`mi_connector` UI:** Technical log window showing structured API communications payload records.

---

## 6. Chinese Payroll & IIT Tax Engines Specifications (`cn_payroll_core` & `cn_payroll_tax`)

### 6.1. `cn_payroll_core` Models

#### `cn.salary.item` (薪资项目表)
*   **Description:** Defines individual wage elements, deductions, or exempt buckets.
*   **Fields:**
    *   `name` (`Char`, Required): Item display label (e.g. "基本工资", "事假扣款").
    *   `code` (`Char`, Required): Short unique code (e.g. "BASIC", "ABSENT").
    *   `item_type` (`Selection`: `fixed` (固定), `variable` (浮动), `deduction` (扣款), `exempt` (免税)): Item classification.
    *   `is_taxable` (`Boolean`, Default=True): Subject to IIT assessment.
    *   `python_code` (`Text`): Formula string evaluated using safe_eval.
    *   `debit_account_id` (`Many2one`, `account.account`): Expense/Debit account for ledger posting.
    *   `credit_account_id` (`Many2one`, `account.account`): Liability/Credit account for ledger posting.
    *   `journal_id` (`Many2one`, `account.journal`): Accounting journal used for posting.
*   **SQL Constraints:** Unique constraint on `code` to prevent formula code naming collisions.

#### `cn.salary.structure` (薪资账套表)
*   **Description:** Groups specific salary items together for specific cohorts or entities.
*   **Fields:**
    *   `name` (`Char`, Required): Account bundle name.
    *   `item_ids` (`Many2many`, `cn.salary.item`): Mapped wage elements.

#### `cn.attendance.settings` (考勤参数设置表)
*   **Description:** Configures regional or company-level punch schedules, late thresholds, and missing check-out tolerances. Supports multi-cohort hierarchical scoping by attaching policies directly to native HR organization tree nodes (Departments or Employees) with complete recursive tree inheritance.
*   **Fields:**
    *   `name` (`Char`, Required): Label (e.g., "Default Company Attendance Policy").
    *   `company_id` (`Many2one`, `res.company`, Required): Associated company.
    *   `standard_check_in` (`Float`, Default=9.0): Scheduled shift start in hours (e.g. 9.0 represents 09:00).
    *   `standard_check_out` (`Float`, Default=18.0): Scheduled shift end in hours (e.g. 18.0 represents 18:00).
    *   `standard_daily_hours` (`Float`, Default=8.0): Standard working hours limit per day. Exceeding hours are calculated as Weekday Overtime.
    *   `grace_period_late` (`Integer`, Default=0): Permitted late arrival in minutes before penalty accruals.
    *   `missing_checkout_fallback` (`Selection`: `standard` (补满班次), `absent` (按缺勤扣除)): Handles instances where employee lacks a check-out punch.
    *   `holiday_rule_ids` (`One2many`, `cn.attendance.holiday.rule`): Quick holidays & swapped workdays rules.
*   **Recursive HR Tree Resolution:** Active settings are dynamically resolved for any employee by climbing the HR organization tree: `Personal Employee Override` ➔ `Recursive Department Tree (dept.parent_id)` ➔ `Company Fallback` ➔ `Database Default`. The first policy record found in its entirety is adopted.
*   **Tree-Aware Calendar Synchronization:** When created or modified, the policy dynamically crawls all employees and departments mapped under its branch node using database-level `child_of` relationships, retrieves their unique set of native Odoo working calendars (`resource.calendar`), and aligns standard start/end bounds for Mon-Fri schedule lines.

#### `cn.attendance.holiday.rule` (法定节假日与调休规则表)
*   **Description:** Configures Chinese public holidays (放假) and rostered swapped weekends (调休工作日) for a specific attendance settings policy.
*   **Fields:**
    *   `name` (`Char`, Required): Label (e.g., "2024 National Day Rest").
    *   `holiday_type` (`Selection`: `holiday` (法定放假), `workday` (调休上班)): Rule type.
    *   `date` (`Date`, Required): Exception calendar date.
    *   `settings_id` (`Many2one`, `cn.attendance.settings`, On-delete='Cascade'): Parent settings policy.
*   **Tree-Aware Calendar Leaves Sync:** Creating or writing a `holiday` type rule automatically queries all employees and nested departments assigned to the parent policy, resolves their respective calendars (`resource.calendar`), and registers corresponding global leave records in Odoo's native `resource.calendar.leaves`. Deleting or altering the rule automatically sweeps and removes these synced leaves across the tree.

#### `cn.attendance.summary` (考勤月度汇总表)
*   **Description:** Resolves Odoo-native punch records, working calendars, and leave balances into payroll calculation factors, tracking multi-bracket overtime as per Chinese Labor Law.
*   **Fields:**
    *   `employee_id` (`Many2one`, `hr.employee`, Required): Employee.
    *   `period` (`Char`, Required): Target year-month (e.g. "2024-03").
    *   `late_minutes` (`Integer`): Accumulated late punch intervals.
    *   `personal_leave_days` (`Float`): Total approved personal leave.
    *   `sick_leave_days` (`Float`): Total approved sick leave.
    *   `absent_days` (`Float`): Total unauthorized absence.
    *   `overtime_weekday_hours` (`Float`): Workday Overtime Hours (工作日平时加班 - 1.5x pay).
    *   `overtime_weekend_hours` (`Float`): Weekend Overtime Hours (周末休息日加班 - 2.0x pay).
    *   `overtime_holiday_hours` (`Float`): Holiday Overtime Hours (法定节假日加班 - 3.0x pay).
*   **Roster & Overtime Computation Logic:**
    1.  **Roster Construction:** Dynamically queries the employee's active working calendar. It flags standard rostered workdays, subtracts registered `holiday` dates (放假), and appends registered `workday` dates (调休上班) to construct a localized **Expected Working Dates list**.
    2.  **Absence Evaluation:** If an expected date has no attendance record and no approved `hr.leave` covers it, a full-day absence (`absent_days += 1.0`) is registered.
    3.  **Punch & Overtime Math:** For every local date containing an attendance punch:
        -   If the date is a registered `holiday`: All worked hours count as `overtime_holiday_hours`.
        -   If the date is an expected workday:
            -   Calculates late arrival minutes relative to standard check-in.
            -   Hours worked exceeding `standard_daily_hours` (e.g., working 12 hours instead of 8) count as `overtime_weekday_hours`.
        -   If the date is a standard rest day (and not a public holiday or swapped workday): All worked hours count as `overtime_weekend_hours`.

#### `cn.payslip` (工资单)
*   **Description:** Calculates employee monthly wage and net payouts.
*   **Inherits:** `mail.thread` (audit trail).
*   **Fields:**
    *   `employee_id` (`Many2one`, `hr.employee`, Required): Employee.
    *   `structure_id` (`Many2one`, `cn.salary.structure`, Required): Mapped structure.
    *   `period` (`Char`, Required): Target year-month.
    *   `base_wage_amount` (`Float`, Required): Stated base contract pay.
    *   `state` (`Selection`: `draft`, `approved`, `paid`): Life state.
    *   `line_ids` (`One2many`, `cn.payslip.line`, `slip_id`): Mined line items.
    *   `move_id` (`Many2one`, `account.move`, Readonly): Reference to the generated Odoo accounting journal entry.
*   **Integration (with `mi` module):** Query `mi.enrollment` for employee and period. Populate `SIHF_PERSONAL` with `amount_employee` and `SIHF_EMPLOYER` with `amount_employer` to inject into the evaluation context automatically.

---

### 6.2. `cn_payroll_tax` Models

#### `cn.tax.ytd.record` (年度累计个税台账表)
*   **Description:** Maintains the rolling year-to-date income and deduction ledgers for cumulative PRC IIT computations.
*   **Fields:**
    *   `employee_id` (`Many2one`, `hr.employee`, Required): Employee.
    *   `year` (`Integer`, Required): Active assessment fiscal year (e.g. 2024).
*   **Cumulative Calculations Formula:**
    $$\text{YTD Taxable Income} = \text{YTD Income} - \text{YTD Exempt} - \text{YTD Standard}(5000 \times M) - \text{YTD SIHF} - \text{YTD Special Additional}$$
    $$\text{YTD IIT} = \text{YTD Taxable Income} \times \text{Progressive Rate} - \text{Quick Deduction}$$
    $$\text{Current Month IIT} = \text{YTD IIT} - \text{Cumulative IIT Paid Previously}$$

---

## 7. Labor Outsourcing & Dispatch Models (`cn_payroll_outsourcing`)

To manage and bill third-party contractors and labor dispatch suppliers, the bridge module implements custom models fully separated from core payroll logic but dynamically integrated via registry lookups.

### 7.1. Model Specifications

#### `cn.outsourcing.contract` (外包结算合同表)
*   **Description:** Configures billing terms, supplier relationships, and default rates.
*   **Fields:**
    *   `name` (`Char`, Required): Contract reference.
    *   `agency_id` (`Many2one`, `res.partner`, Required): Third-party agency.
    *   `contract_type` (`Selection`: `dispatch` (派遣代发), `service_rate` (工时项目外包)): Billing mode.
    *   `admin_fee_per_head` (`Float`): Per-person monthly administrative fee (Dispatch mode).
    *   `hourly_rate` (`Float`): Flat hourly rate (Service-Rate mode).
    *   `vat_rate` (`Float`): Value-added tax percentage (e.g., 0.06 for 6%).

#### `cn.outsourcing.assignment` (外包工人派驻期表)
*   **Description:** Manages dynamic worker assignments with chronological start and end date ranges.
*   **Fields:**
    *   `contract_id` (`Many2one`, `cn.outsourcing.contract`, Required): Parent contract.
    *   `employee_id` (`Many2one`, `hr.employee`, Required): Worker.
    *   `date_start` (`Date`, Required): Assignment start date.
    *   `date_end` (`Date`, Optional): Assignment end date (null represents active).

#### `cn.outsourcing.settlement` (外包月度结算单)
*   **Description:** Aggregates, calculates, and bills monthly labor cost.
*   **Fields:**
    *   `name` (`Char`, Required): Settlement reference.
    *   `contract_id` (`Many2one`, `cn.outsourcing.contract`, Required): Parent contract.
    *   `period` (`Char`, Required): Target billing period (YYYY-MM).
    *   `state` (`Selection`: `draft`, `approved`, `billed`): Settlement state.
    *   `line_ids` (`One2many`, `cn.outsourcing.settlement.line`): Child billing lines.
    *   `subtotal_amount` (`Float`): Computed tax-exclusive subtotal.
    *   `vat_amount` (`Float`): Computed VAT tax.
    *   `total_amount` (`Float`): Computed grand total (Subtotal + VAT).
    *   `vendor_bill_id` (`Many2one`, `account.move`): Reference to the automatically generated Odoo Accounts Payable Vendor Bill.
*   **Chronological Splitting & Generation Logic:**
    Queries active assignments for the contract, filters and overlaps date ranges with the billing period start and end bounds, queries the matched workers' attendance summaries (`cn.attendance.summary`), and aggregates:
    - **Service-Rate Mode:** $\text{Subtotal} = \text{Attendance Hours} \times \text{Hourly Rate}$.
    - **Dispatch Mode:** $\text{Subtotal} = \text{Gross Salary} + \text{SIHF Employer} + \text{SIHF Employee} + \text{IIT Withheld} + \text{Admin Fee}$.

#### `cn.outsourcing.backfill.wizard` (快速补员向导)
*   **Description:** Transient wizard to rapidly copy-paste and register bulk temporary workers.
*   **Fields:**
    *   `contract_id` (`Many2one`, `cn.outsourcing.contract`, Required): Target contract.
    *   `date_start` (`Date`, Required): Assignment start date.
    *   `attendance_settings_id` (`Many2one`, `cn.attendance.settings`): Target policy assignment.
    *   `worker_raw_list` (`Text`, Required): Bulk copy-paste string (Name,Barcode - line by line).

---

### 7.2. Portal Infrastructure & Access Control

To provide external labor agencies with secure access to check their active contracts and billing sheets, the module implements Odoo Portal Integration.

*   **Multi-Tenant Query Scoping:** Under `OutsourcingPortal` (`CustomerPortal` subclass), all controller lookups automatically resolve `request.env.user.partner_id`. It scopes contracts and settlements strictly to the logged-in partner's ID or its parent agency ID, enforcing strict multi-tenant boundary isolation.

---

## 8. PRC Advanced & Ultimate Legal Compliance Engines

To guarantee bulletproof legal defense under Chinese tax laws, labor contract laws, and social welfare rules, the system integrates active validation sentries and computation engines:

### 8.1. Minimum Wage Earning Supplement Engine
- **Model Field:** `local_minimum_wage` (`Float` on `cn.payslip`, default=2,690.00 RMB).
- **Core Formula:**
  $$\text{MINIMUM\_WAGE\_MAKEUP} = \max(0.0, \text{local\_minimum\_wage} - \text{Net Pre-wage})$$
- **Behavior:** The calculated supplement is dynamically injected as a deduction/wage offset variable in safe_eval, guaranteeing that no employee's cash pre-withholding net falls below the statutory city minimum wage.

### 8.2. Non-Resident Individual Monthly Taxation Model
- **Model Selection:** `resident_status` on `hr.employee` (`['resident', 'non_resident']`).
- **Behavior:** Non-resident expats bypass the cumulative YTD tax engine. Their individual income tax is evaluated strictly per-month on isolated progressive brackets with a flat 5,000.00 RMB standard deduction.

### 8.3. Labor Dispatch 10% Ratio Cap Sentry
- **Model Validation:** `@api.constrains` in `cn.outsourcing.assignment`.
- **Constraint:** Block creation of new active assignments if the total headcount of active outsourced workers exceeds 10% of the company's entire workforce (Active Employees + Active Dispatched Workers):
  $$\text{Ratio} = \frac{\text{Outsourced Count}}{\text{Formal Employees} + \text{Outsourced Count}} \le 10\%$$

### 8.4. Disability Employment Security Fund (残保金) Monthly Pre-accounting Accrual
- **Model Field:** `is_disabled` (`Boolean` on `hr.employee`) and `estimated_disability_security_levy` (`Float` on `cn.payslip`).
- **Core Formula:**
  $$\text{Monthly Accrual} = \max(0.0, \text{Total Employees} \times 1.5\% - \text{Disabled Employees Count}) \times \text{Current Base Wage}$$

### 8.5. PRC 7 Special Additional Tax Deductions Validation
- **Model Fields:** Individual monthly tax deduction inputs on `cn.payslip` (`deduction_child_education`, `deduction_continuing_education`, `deduction_housing_loan`, `deduction_housing_rent`, `deduction_elderly_care`, `deduction_infant_care`).
- **Core Constraints:**
  - **Mutual Exclusion:** `deduction_housing_loan` and `deduction_housing_rent` cannot be claimed simultaneously.
  - **Statutory Limits:** Each item has an active constraint validating it against standard statutory monthly ceilings.

### 8.6. Statutory Overtime 36-Hour Monthly Limit Warning
- **Model Fields:** `overtime_status` (`Selection: ['normal', 'warning']`) and `total_overtime_hours` on `cn.attendance.summary`.
- **Behavior:** Triggers a `'warning'` flag and logs alerts if total combined overtime (weekday, weekend, holiday) exceeds 36.0 hours within a billing period.

### 8.7. Probation Term & Salary Audit Sentry
- **Model Fields:** `contract_term_months`, `probation_term_months`, `wage_regular`, `wage_probation` on `hr.employee`.
- **Core Constraints:**
  - Enforces statutory probation term maximum boundaries based on contractual term length.
  - Enforces that `wage_probation` must be at least 80% of `wage_regular`.

### 8.8. Female Employee "Three Periods" Dismissal Prevention Sentry
- **Model Selection:** `female_protection_state` on `hr.employee` (`['none', 'pregnancy', 'maternity', 'lactation']`).
- **Behavior:** Overrides `write` to block archiving/deactivating (`active = False`) any female employee currently in Pregnancy, Maternity, or Lactation states.

---

## 9. Dynamic & Custom Financial Report Engine

A fully metadata-driven financial report viewer supporting Balance Sheet, Income Statement, Cash Flow Statement, and arbitrary user-defined custom financial reports.

### 9.1. Core Abstract Modeling
- `account.report`: Represents report metadata headers.
- `account.report.line`: Tree hierarchy nodes representing rows (using `parent_id` recursive child lists).
- `account.report.expression`: Evaluation lines defining how values are computed.

### 9.2. Polymorphic Valuation Engine
Evaluates report formulas and rules at run-time:
- **Account Direct (`account`)**: Directly queries matching account move line balances.
- **Account Type (`account_type`)**: Aggregates balances by native account type codes.
- **Aggregation (`aggregation`)**: Intersects and sums multiple child rows.
- **Formula (`formula`)**: Sandboxed python execution via `safe_eval` with strict execution boundaries.
- **Analytic Plan & Account (`analytic_account`/`analytic_plan`)**: Direct management accounting cost center analysis.

### 9.3. High-Fidelity Exports
- **Excel Matrix Engine**: Built with `xlsxwriter`, generating multi-period data arrays, keeping indentation levels matching the visual hierarchy tree.
- **PDF QWeb Template**: Dynamic, mobile-responsive, print-ready financial tabular designs.

---

## 10. PRC Chinese Accounting Localization Specifications (中国会计本地化规范)

To ensure full statutory compliance under the Ministry of Finance (MoF) of the People's Republic of China, the system implements native accounting localizations, compliant report generation, and voucher audit-trail management.

### 10.1. Standardized Chinese Charts of Accounts (中国会计科目表体系)
Supports native Odoo 17 charts of accounts tailored to the specific regulatory requirements of different economic sectors:
- **Standard Enterprise CoA (企业一般会计准则科目表)**: Configures standard unified account code lists (`1001` Cash, `1002` Bank, `2211` Accrued Payroll, `2221` Taxes, etc.).
- **Non-Governmental Non-Profit Organization CoA (民间非营利组织会计制度)**: Localized for NPOs under specialized MoF reporting rules.
- **Government Accounting CoA (政府会计准则)**: Complies with government budget and financial ledger dual-track accounting.
- **Construction & Real Estate CoA (施工建设与房地产会计制度)**: Includes specialized project-level cost tracking codes.
- **Agricultural Cooperatives CoA (农业合作社会计制度)**: Structured for agricultural collective asset accounting.
- **Financial & Securities Institutions CoA (金融证券机构会计制度)**: Standardized for complex financial asset and liability valuations.

### 10.2. CAS-Compliant Financial Reporting Engine (中国企业财务报表)
- **Balance Sheet (资产负债表)**: Standardized CAS (Chinese Accounting Standards) format classifying assets, liabilities, and owners' equity with native account type aggregation.
- **Income Statement (利润表)**: Displays operating revenues, sales taxes, and period expenses in a standard progressive multi-step layout.
- **Cash Flow Statement (现金流量表)**: Utilizing custom cash flow categories (`account.cashflow.category`) configured on journal items to automatically distinguish operating, investing, and financing cash flows.

### 10.3. Localized Accounting Voucher Printing (记账凭证本地化打印)
- **Standard Layout**: Generates professional PDF 记账凭证 (Accounting Voucher) templates formatted in landscape dual-voucher or single-voucher A4/half-A4 layouts.
- **Audit Signature Sentry**: Embeds dedicated rows for statutory sign-offs ensuring full internal control tracking:
  - `制单人` (Prepared By - Auto-resolved from the Odoo creator user).
  - `审核人` (Approved By - Auto-resolved from the post/validation auditor).
  - `记账人` (Bookkeeper - Standard financial roles).
  - `出纳人` (Cashier - Cash/Bank moves validator).
  - `单位负责人` (Authorized Enterprise Representative).
- **Balanced Integrity**: Ensures debit-credit balance checks across multi-currency operations and invoice exchange rate overrides.



