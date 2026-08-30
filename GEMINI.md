# 🌌 Odoo 17 China Localization & Payroll Compliance (cn_odoo) Master Protocol

Welcome to the `cn_odoo` repository context guide. This document serves as the absolute single source of truth for repository architecture, module specifications, build instructions, and engineering standards.

---

## 1. Project Overview

The `cn_odoo` workspace is a modular, production-grade suite of Odoo 17 (Community & Enterprise compatible) addons designed to provide comprehensive Chinese business localization and full regulatory HR, payroll, tax, and social welfare compliance. It covers financial reporting, local accounting charts, governmental tax catalogs, next-generation electronic invoicing, administrative city directories, social security and housing fund (SIHF) management, and a complete PRC Individual Income Tax (IIT) & labor outsourcing suite.

### Core Technology Stack
* **Server-side Core:** Python 3.10+ / Odoo 17 ORM Active Record framework.
* **Database Layer:** PostgreSQL 15+.
* **Front-end View Architecture:** Odoo OWL (Odoo Web Library) v2, XML templates, and QWeb reports.
* **External Integration Libraries:** `addressparser` (for EDI geographic mapping), `cn2an` (for financial Chinese word representation), `xlsxwriter` (for precise Excel accounting export), and `pytz` (for timezone audits).

---

## 2. Workspace Modular Architecture

This repository strictly enforces downward-flowing, single-direction dependencies. Modularity limits coupling across functional pillars and prevents circular references between independent business domains (e.g. LIMS, IoT, Payroll, and Social Welfare).

### Modular Dependency Flow (ASCII Flowchart)

```
                     ┌─────────────────────────────────────────────────────────┐
                     │                        Odoo Core                        │
                     │  (base, account, stock, hr_expense, sale, purchase, etc) │
                     └────────────────────────────┬────────────────────────────┘
                                                  │
                       ┌──────────────────────────┼──────────────────────────┐
                       ▼                          ▼                          ▼
                ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
                │   l10n_cn    │           │ l10n_cn_data │           │ l10n_cn_tax  │
                │ (Accounting) │           │ (Master Data)│           │ (Tax Catalog)│
                └──────┬───────┘           └──────────────┘           └──────┬───────┘
                       │                                                     │
                       ▼                                                     ▼
                ┌──────────────┐                                      ┌──────────────┐
                │ l10n_cn_city │                                      │account_edi_..│
                │ (City Data)  │                                      │ (CN E-Invoice│
                └──────────────┘                                      │    EDI)      │
                                                                      └──────────────┘
                       │
                       ▼
                ┌──────────────┐ ◄─────────────────────────────────────┐
                │   mi_core    │                                       │
                │ (SIHF Policy)│ ◄────────────────────────┐            │
                └──────┬───────┘                          │            │
                       │                                  │            │
                       ▼                                  │            │
                ┌──────────────┐                          │            │
                │cn_payroll_core◄────────────────────┐    │            │
                │(Attendance/W)│                     │    │            │
                └──────┬───────┘                     │    │            │
                       │                             │    │            │
                       ▼                             │    │            │
                ┌──────────────┐                     │    │            │
                │cn_payroll_tax│                     │    │            │
                │(IIT/YTD Ledg)│                     │    │            │
                └──────────────┘                     │    │            │
                                                     │    │            │
              ┌───────────────────┐                  │    │            │
              │ financial_reports │                  │    │            │
              │ (Dynamic Statement│                  │    │            │
              └───────────────────┘                  │    │            │
                                                     ▼    │            │
                ┌─────────────────────────────────────────┴────┴────────┐
                │                cn_payroll_outsourcing                 │
                │   (Hourly/Dispatch Labor Billing, Portal, Blacklist)  │
                └───────────────────────────────────────────────────────┘
```

---

## 3. Comprehensive Module Registry

### 3.1. `l10n_cn` (China Accounting Chart & Invoicing)
* **Purpose:** Out-of-the-box Chinese fiscal localization, including customized chart of accounts (CoA) templates for Small Enterprises (小企业会计准则) and Large/Common Enterprises.
* **Key Enhancements:** 
  * Financial voucher printing layout with automatic conversion of numerical figures to financial Chinese word-amount notation (via `cn2an`).
  * Explicit constraint checking validation for 8-digit standard Fapiao numbers on invoices.

### 3.2. `l10n_cn_city` (China Provincial Administrative Regions)
* **Purpose:** Extensive regional master address records mapped to Chinese provinces and cities.
* **Dependencies:** Extends base localization models using Odoo's `base_address_extended` layout to enable structured shipping/billing address input.

### 3.3. `l10n_cn_data` (Chinese Enterprise Master Data Templates)
* **Purpose:** Preconfigured, standard Chinese business master data templates including:
  * **Product Categories:** Raw materials, Semi-finished goods, Finished products.
  * **Landed Costs:** Custom duties, international freights, port expenses.
  * **Storage Categories & Package Types:** High-frequency large pallets, small boxes, wooden crates.
  * **Expenses & Payment Terms:** Standard local travel/meal allowances, and localized Net-30/45/60 payment terms.

### 3.4. `l10n_cn_tax` (China Tax Catalog Taxonomy)
* **Purpose:** Registers VAT catalog configurations representing tax rates required by Chinese tax bureaus.
* **Design:** Provides the base catalog structures used by downstream Electronic Invoicing systems.

### 3.5. `account_edi_cn_etax` (China E-Tax "数电发票" EDI)
* **Purpose:** Full integration of China's Fully Digitalized Electronic Invoicing (数电发票) XML parser.
* **Key Mechanisms:** Decodes incoming government E-Invoice XML nodes into system invoice lines. Integrates `addressparser` to extract structured seller/buyer company location elements from unstructured strings.

### 3.6. `mi_core`, `mi_compliance`, `mi_connector` (Social Insurance & Housing Fund)
* **Purpose:** End-to-end management of Chinese Multi-Base Social Insurance and Housing Fund (五险一金) policies and employee enrollments.
* **Key Enhancements:** 
  * **Multi-Base Line Mode (Approach B):** Enforces separate declared calculation bases for pension, medical, and housing fund lines, falling back to a main base if specific line bases are not declared.
  * **Audit Trails & SHA-256 Hashes:** `mi_compliance` scans active employee databases to identify underpaid risks, computes 0.05% daily late fees, and generates anti-tamper PDF audit evidence hashes.
  * **API Log Adapters:** `mi_connector` manages queue-based, asynchronous, SHA-256-signed communications with Chinese government SSB portals.

### 3.7. `cn_payroll_core` & `cn_payroll_tax` (Chinese Localized Payroll & IIT Engines)
* **Purpose:** Independent payroll calculation suite for China, fully decoupled from Odoo's standard payroll module.
* **Key Enhancements:**
  * **Hierarchical Policy Tree Resolution:** Resolves active attendance policies by recursively climbing the Odoo HR department tree (Employee > Department > Parent Department > Company), supporting complete policy overrides.
  * **Overtime Accounting:** Automates Chinese Labor Law overtime pay metrics (工作日平时 1.5x, 双休日 2.0x, 法定节假日 3.0x) and expected rosters by intersecting resource calendars with public holiday lists.
  * **PRC Cumulative Withholding Engine:** `cn_payroll_tax` maintains a monthly YTD tax ledger (`cn.tax.ytd.record`) to calculate progressive monthly tax withholding, separate year-end bonus separate tax quotient formulas, and severance pay tax-exempt schedules.
  * **Double-Entry Voucher Posting:** Approved payslips automatically trigger balanced accounting vouchers (`account.move`), correctly reversing debits and credits for negative salary lines.

### 3.8. `cn_payroll_outsourcing` (Labor Dispatch & Outsourcing Bridge)
* **Purpose:** Coordinates third-party labor dispatch agencies with a dual-billing settlement engine (Dispatch Mode vs. Hourly Service Rate) and Accounts Payable vendor bill integration.
* **Key Enhancements:**
  * **Chronological Assignment Trackers:** Prevents billing overlaps by splitting active working hours based on mid-month worker transfers.
  * **Qualification & Enterprise Blacklist:** Actively audits age limits, experience years, and blocks blacklisted workers using multi-dimensional OR-matching (Barcode, National ID, Mobile).
  * **Secure Agency Portal:** Employs Odoo's portal structures to restrict login agencies to viewing only their partner-scoped contracts and settlements.

### 3.9. `financial_reports` (Dynamic Custom Financial Statements Viewer)
* **Purpose:** Implements a rich, interactive, real-time financial reporting center (Balance Sheet, Income Statement, Cash Flow) with comparative period analytics.
* **Backend Design:** Employs dynamic expression engines and flexible account type maps to aggregate transactions dynamically.
* **Frontend Design:** Custom OWL v2 actions with drill-down actions, interactive toggles, and direct `xlsxwriter`-powered multi-period Excel exporters.

---

## 4. The 8-Barrier Ultimate Legal Compliance Sentry

To safeguard enterprises against regulatory audit fines, the following active transactional constraints are built directly into Odoo's backend database execution layer:

1. **Local Minimum Wage Earning Supplement:**
   - Injects `MINIMUM_WAGE_MAKEUP` in calculations if net cash pre-wage drops below statutory limits (Default: 2,690.00 RMB, Shanghai rate).
2. **Non-Resident Individual Monthly Exemption:**
   - Detects `non_resident` workers, bypassing YTD cumulations, and applies monthly progressive tax rates on single-month brackets with flat 5,000.00 RMB deductions.
3. **Labor Dispatch 10% Ratio Cap Sentry:**
   - Transactionally blocks creating assignments if active dispatched personnel exceed 10.00% of the entire corporate workforce (Active Employees + Outsourced Workers).
4. **Disability Employment Security Fund (残保金) Accruals:**
   - Computes monthly pre-accounting accruals if the corporate disability hiring quota ($1.5\%$ of workforce) is not met, enabling CFOs to proactively accrue the annual levy.
5. **PRC 7 Special Additional Tax Deductions Limit & Exclusion Audit:**
   - Validates individual deductions against statutory caps and enforces mutual exclusion (e.g. Housing Rental and Housing Loan Interest deductions cannot both be claimed).
6. **Statutory Overtime 36-Hour Monthly Warning:**
   - Automatically tracks combined overtime and triggers a `'warning'` status flag if an employee's overtime exceeds the 36-hour monthly legal ceiling.
7. **Probation Period Term & Salary Audit:**
   - Cross-audits contractual terms vs. probation lengths (e.g., maximum 2 months for a 1-year contract), and blocks saving contracts if probation wage is below 80% of regular pay.
8. **Female Employee "Three Periods" Special Protection Lock:**
   - Intercepts deactivation or contract archival (`active = False`) of pregnant, maternity, or breastfeeding female staff, returning a descriptive `ValidationError` to block terminations.

---

## 5. Development Protocols & "Think in Odoo" Guidelines

Every contribution must maintain high cohesion and absolute architectural clean-cut. Do not bring Spring, Django, or custom wrapper-service boilerplate into this repository.

### 5.1. The Active Record Mandate
* Do not introduce abstract "service layers", customized repositories, DTO classes, or generic decoupled event-buses.
* All models must be treated as Active Records.
* Business computation should live strictly within Odoo models, driven by `@api.depends`, compute methods, `@api.constrains`, and `@api.onchange`.

### 5.2. Surgical API Execution & Integrity
* Modifying existing logic must be surgical. **Avoid large sweeping replacements.**
* When overriding standard methods, always invoke `super()` inside the same context.
* Always enforce batch-compatible patterns. Do not write single-record modifications inside loops.
* **Batch Initialization:** Ensure all `create` method overrides support bulk creations with the `@api.model_create_multi` decorator.

### 5.3. Interface and Frontend Integrity (OWL & QWeb)
* Production code must be fully metadata-driven. Never hardcode data rows inside UI components. Relational selection options must query active database contexts dynamically.
* Keep test directories (e.g., QUnit, Python test assertions) isolated from functional production blocks.
* Structure QWeb and custom reports inside standard directories: `views/` for menus and action configurations, `report/` for template views, and `static/src/` for frontend assets.

---

## 6. Installation & Testing Commands

### 6.1. External Python Dependencies Installation
Install critical localized processing libraries on your host or container environment:
```bash
pip install cn2an addressparser xlsxwriter pytz
```

### 6.2. Running Odoo 17 with Local Addons
To execute the server and target this specific repository path, include the folder in your `addons-path`:
```bash
odoo-bin --addons-path="/path/to/odoo/addons,/Users/jeffery/containers/odoo17/addons/cn_odoo" -d your_dev_db
```

### 6.3. Updating/Installing Specific Modules
Always specify correct dependencies to trigger dependency graph updates:
```bash
# Force-update China Tax Catalog, Chinese Payroll, and Chinese Financial Reports modules
odoo-bin -d your_dev_db -u l10n_cn_tax,mi_core,cn_payroll_core,cn_payroll_tax,cn_payroll_outsourcing,financial_reports --stop-after-init
```

### 6.4. Executing Python Test Suites
*(Note: Ensure your database has test/demo data loaded when running test environments)*
```bash
odoo-bin --addons-path="/path/to/odoo/addons,/Users/jeffery/containers/odoo17/addons/cn_odoo" -d your_test_db -i l10n_cn,mi_core,cn_payroll_core,cn_payroll_tax,cn_payroll_outsourcing,financial_reports --test-enable --stop-after-init
```

---

## 7. Personal & Session Memory Guidelines
Any private instructions, credentials, local path overrides, or developer preferences specific to this environment must live strictly in the workspace's private memory index (`MEMORY.md` located at `/Users/jeffery/.gemini/tmp/cn-odoo/memory/MEMORY.md`).
No machine-specific configurations, Docker setups, or local secrets are permitted within this `GEMINI.md` file or to be committed into the git repository.
