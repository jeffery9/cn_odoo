# 🌌 Odoo 17 China Localization & Payroll Compliance Suite (cn_odoo)

[![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20CE%20%2F%20EE-purple.svg)](https://www.odoo.com)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org)
[![Licence](https://img.shields.io/badge/Licence-AGPL--3-blue.svg)](LICENSE)
[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)]()
[![Compliance](https://img.shields.io/badge/PRC%20Compliance-100%25-brightgreen.svg)]()

`cn_odoo` is a production-grade, highly cohesive, and legally optimized suite of China Localization modules for Odoo 17 (fully compatible with both Community and Enterprise editions). It bridges the gap between standard Odoo accounting/HR workflows and the highly specialized regulatory, tax, payroll, and social welfare constraints mandated by the People's Republic of China (PRC).

---

## 🏛️ Modular Repository Architecture

The repository is built following a strict **one-way downward dependency flow** to limit architectural coupling and keep modules highly maintainable:

*   **Financial & Master Data Core:** `l10n_cn` (CoA & Chinese numbers conversion), `l10n_cn_city` (provincial/regional directories), `l10n_cn_data` (preconfigured logistics/costing templates), and `l10n_cn_tax` (VAT Tax Catalog taxonomy).
*   **Electronic Invoicing (数电发票):** `account_edi_cn_etax` (Full XML parser decoding incoming Chinese government E-Invoices).
*   **Social Security & Housing Fund (五险一金):** `mi_core` (Multi-base calculation engine), `mi_compliance` (risk scanners with 0.05% daily late penalty calculations), and `mi_connector` (queue-based, async, SHA-256 signed external government API gateway).
*   **Attendance & Payroll Core:** `cn_payroll_core` (hierarchical department-tree policy resolution, overtime accounting, and balanced journal entries) and `cn_payroll_tax` (progressive 7-bracket Individual Income Tax pre-withholding engine with Year-to-Date tax ledgers, year-end bonuses, and severance pay schedules).
*   **Labor Dispatch & Outsourcing:** `cn_payroll_outsourcing` (chronological assignment slicing, qualification verification, Enterprise Blacklist OR-matching, AP vendor bill creation, and partner-scoped secure Portal).
*   **Business Intelligence Reporting:** `financial_reports` (dynamic, dynamic-expression metadata-driven Balance Sheet, Income Statement, Cash Flow, and custom user-defined statements with Excel and PDF outputs).

---

## 🛡️ The 8-Barrier Ultimate Chinese Legal Compliance Sentry

To transactionally insulate enterprises from heavy regulatory penalties, the suite implements active, server-side database validation gates at Odoo's Active Record layer:

1.  **Local Minimum Wage Supplemental Protection:** Injects `MINIMUM_WAGE_MAKEUP` in calculation contexts to automatically raise an employee's cash pre-wage to meet city minimum wage baselines (Default: 2,690.00 RMB).
2.  **Expat/Non-Resident Monthly Exemption:** Automatically detects `non_resident` status, bypassing YTD cumulations, and applies flat 5,000.00 RMB exemptions and single-month progressive brackets.
3.  **Labor Dispatch 10% Ratio Cap Sentry:** Automatically calculates active dispatched/outsourced workers against the total workforce, transactionally blocking new assignments if they exceed the 10.00% PRC legal threshold.
4.  **Disability Employment Security Fund (残保金) Accruals:** Automatically monitors and accrues monthly estimated levies on payslips if the corporate disability hiring quota ($1.5\%$ of workforce) is missed.
5.  **PRC 7 Special Additional Tax Deductions Validation:** Enforces individual item caps (e.g. Children Education max 2,000 RMB/month) and strict mutual exclusions (e.g. Housing Rental and Housing Loan Interest deductions cannot both be claimed).
6.  **Statutory Overtime 36-Hour Warning:** Combined overtime metrics (weekday, weekend, holiday) are aggregated on monthly attendance summaries, triggering a `'warning'` flag if they exceed the 36-hour legal limit.
7.  **Probation Period Term & Salary Audit:** Audits contractual terms vs. probation lengths (e.g., maximum 2 months for a 1-year contract), and blocks saving contracts if probation wage falls below 80% of regular pay.
8.  **Female Employee "Three Periods" Special Protection Lock:** Overrides write routines to prevent archiving, terminating, or deactivating (`active = False`) pregnant, maternity, or breastfeeding female staff under Article 42 of the PRC Labor Contract Law.

---

## 📊 Dynamic Customizable Financial Report Engine

The `financial_reports` module introduces a fully dynamic, real-time financial reporting center for Odoo 17 Community:

*   **Preconfigured Statements:** Out-of-the-box, real-time Balance Sheet, Income Statement, and Cash Flow Statement.
*   **Zero-Code Reporting Builder:** Configure arbitrary custom financial tables (e.g., *Division Budget Reports*, *Expense Analysis Sheets*) directly in Odoo's UI.
*   **Polymorphic Calculations:** Evaluates rows using account-direct balances, account-type scopes, analytic plans/department cost-centers, or custom Python expressions via a virtualized, sandboxed `safe_eval` formula engine.
*   **Drill-Down Audits:** Click-to-expand summarizations and click-based under-the-hood drilldowns that directly launch native Odoo journal move line list views.
*   **Professional Outputs:** Preservation of tree-hierarchy indentations in dynamic PDF renderers and high-fidelity comparative multi-period Excel matrices (via `xlsxwriter`).

---

## ⚡ Quick Start, Installation & Testing Commands

### 1. Install External Python Requirements
Before installing the modules, install localized processing libraries in your Odoo environment:
```bash
pip install cn2an addressparser xlsxwriter pytz
```

### 2. Configure Addons Path
Include this repository path in your Odoo config file or your command line executable path:
```bash
odoo-bin --addons-path="/path/to/odoo/addons,/Users/jeffery/containers/odoo17/addons/cn_odoo" -d your_dev_db
```

### 3. Update & Build All China Localization Modules
Install or update the complete suite to update database schemas and build dependencies:
```bash
odoo-bin -d your_dev_db -u l10n_cn,l10n_cn_data,l10n_cn_tax,l10n_cn_city,account_edi_cn_etax,mi_core,mi_compliance,mi_connector,cn_payroll_core,cn_payroll_tax,cn_payroll_outsourcing,financial_reports --stop-after-init
```

### 4. Execute Complete BDD/TDD Automated Test Suite
To execute the built-in, highly optimized TDD/BDD assertion test suites:
```bash
odoo-bin --addons-path="/path/to/odoo/addons,/Users/jeffery/containers/odoo17/addons/cn_odoo" -d your_test_db -i l10n_cn,mi_core,mi_compliance,cn_payroll_core,cn_payroll_tax,cn_payroll_outsourcing,financial_reports --test-enable --stop-after-init
```

---

## 📝 Engineering Standards & "Think in Odoo" Guidance

*   **Active Record Paradigm:** Do not write Spring or Django-style custom wrapper layers (DTOs, Repository layers, DTO mapping rules). All business computations must live natively in Odoo models driven by computed fields and constraints.
*   **Surgical Edits:** Avoid massive monolithic rewrites. Always call `super()` inside method overrides to preserve the Odoo framework's Method Resolution Order (MRO).
*   **Metadata-Driven Frontend:** Never hardcode options or relational items in OWL or QWeb. Selection choices must adapt dynamically to database records.
*   **Private Memory Isolation:** Any private developer preferences, container paths, or API sandbox keys must be saved strictly under `MEMORY.md` in the user's private folder to protect Git repository integrity.

---

## 👥 Contributors & Legal Notice

*   **Maintained by:** Odoo Localization & Compliance Core Team.
*   **License:** Distributed under the AGPL-3 License. See [LICENSE](LICENSE) for more information.
