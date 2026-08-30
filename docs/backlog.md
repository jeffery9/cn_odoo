# Backlog: Medical Insurance System (MI System)

| ID | Type | Title | Priority | Odoo Ver | Depends-on | Size | Cross-Module? | Pain Point |
|----|------|-------|----------|----------|------------|------|---------------|------------|
| **EP-1** | **Epic** | **医保政策与规则引擎管理** | **Must** | **17** | — | **L** | **no** | — |
| US-1.1 | Story | As a SysAdmin I want to manage provincial cities and administrative regions so that policies have geo accuracy | Must | 17 | EP-1 | S | no | NO |
| US-1.2 | Story | As a SysAdmin I want to manage policies via Header-Line model (with effective dates) so that calculations are chronologically accurate | Must | 17 | US-1.1 | M | no | NO |
| **EP-2** | **Epic** | **员工参保生命周期与批量管理** | **Must** | **17** | — | **L** | **yes** | — |
| US-2.1 | Story | As an HR I want automatic enrollment validation triggered during employee hiring so that leakages are avoided | Must | 17 | EP-1, EP-2 | S | yes (hr) | YES |
| US-2.2 | Story | As an HR I want to upload batch enrollments via standard Excel templates with policy intercept rules so that data is clean | Must | 17 | EP-1, EP-2 | M | no | YES |
| **EP-3** | **Epic** | **费用核算与申报准备** | **Must** | **17** | — | **M** | **no** | — |
| US-3.1 | Story | As a Payroll/HR manager I want automatic monthly insurance calculations so that employer/employee shares are exact | Must | 17 | EP-1 | M | no | NO |
| US-3.2 | Story | As an HR I want to generate declaration files and reconcile deductions with social security feedback worksheets so that discrepancies are resolved | Must | 17 | EP-3 | M | no | NO |
| **EP-4** | **Epic** | **合规风险扫描与预警** | **Must** | **17** | — | **L** | **yes** | — |
| US-4.1 | Story | As a Compliance Officer I want a real-time compliance dashboard so that overall audit health is transparent | Should | 17 | EP-1, EP-3 | M | no | NO |
| US-4.2 | Story | As a Compliance Officer I want deep risk scanning to estimate late penalties (0.05% daily) so that fiscal exposure is quantified | Must | 17 | EP-4 | L | yes (hr) | YES |
| **EP-5** | **Epic** | **审计留痕与证据链管理** | **Must** | **17** | — | **M** | **yes** | — |
| US-5.1 | Story | As Legal/HR I want operational audits tracking with Odoo's native Chatter so that transaction timelines are bulletproof | Must | 17 | EP-2 | S | yes (mail) | NO |
| US-5.2 | Story | As Legal I want to generate and archive PDF compliance evidence chains printed with SHA-256 hashes so that anti-tamper records are preserved | Must | 17 | EP-5 | M | yes (mail) | YES |

---

## BDD Scenarios Index

| Story ID | Feature File Path | Scenario | Pain Point Driver | Target Module |
|----------|-------------------|----------|-------------------|---------------|
| US-1.2 | `mi_core/features/policy_rules.feature` | 成功配置城市医保政策规则并执行基数截断 | YES — Calculation correctness | `mi_core` |
| US-1.2 | `mi_core/features/policy_rules.feature` | 拦截重叠生效日期的策略版本冲突 | YES — Version stability | `mi_core` |
| US-2.2 | `mi_core/features/batch_import.feature` | 批量导入包含超限基数和在保重复的混合名单 | YES — Onboarding speed | `mi_core` |
| US-4.2 | `mi_compliance/features/compliance_scan.feature` | 深度扫描未保员工和计算每日万分之五利息 | YES — Fine prevention | `mi_compliance` |
| US-5.2 | `mi_compliance/features/audit_trail.feature` | 生成防篡改合规证据链并验证 SHA-256 哈希值 | YES — Audit safety | `mi_compliance` |
| US-6.4 | `cn_payroll_core/features/attendance_settings.feature` | 配置迟到豁免额度并自动处理缺卡异常 | YES — Process adaptivity | `cn_payroll_core` |
| US-6.5 | `cn_payroll_core/features/attendance_settings.feature` | 多级优先考勤组与漏斗解析策略 | YES — Role mapping | `cn_payroll_core` |
| US-6.6 | `cn_payroll_core/features/attendance_settings.feature` | 中国法定公休规则与 Odoo 资源日历叶自动同步 | YES — Holiday compliance | `cn_payroll_core` |
| US-6.7 | `cn_payroll_core/features/attendance_pay.feature` | 12小时工作制、7天排班及三档次国家规定加班审计 | YES — Overtime compliance | `cn_payroll_core` |
| US-8.1 | `cn_payroll_core/features/accounting_integration.feature` | 生成并结平薪资会计凭证过账 | YES — Financial integrity | `cn_payroll_core` |
| US-3.2 | `mi_connector/features/government_bridge.feature` | 异步申报医保在保申报状态与网关状态查询 | YES — Asynchronous submission | `mi_connector` |
| US-3.2 | `mi_connector/features/government_bridge.feature` | 导出月度在保数据到国家局/社保局统一标准 Excel 模板 | YES — Bulk-import speed | `mi_connector` |
| US-12.1 | `l10n_cn/features/accounting_localization.feature` | 成功初始化和加载不同行业特化的中国会计科目表 (CoA) | YES — Fiscal compliance | `l10n_cn` |
| US-12.2 | `l10n_cn/features/accounting_localization.feature` | 自动生成并导出符合中国审计规范的 landscape 记账凭证 PDF | YES — Voucher legality | `l10n_cn` |

---

## Engineering Handoff & Architecture Isolation

### 1. Risk Classification Matrix
*   **High Risk:** `US-1.2` (Policy version calculation), `US-3.1` (Contribution computations), `US-4.2` (Penalty calculation equations).
*   **Medium Risk:** `US-2.1` (Triggering validation off of standard `hr.employee` transitions), `US-2.2` (Injecting validations into transient `base_import.import`), `US-3.2` (Data reconciliation algorithms).
*   **Low Risk:** `US-1.1` (Administrative regions configuration views), `US-5.1` (Chatter log layouts), `US-5.2` (QWeb report printing & hash mapping).

### 2. Bridge-Based Decoupling Rules
*   **Core HR Connection (`mi_core` ↔ `hr`):** Direct coupling is permissible inside `mi_core` using Odoo's standard `_inherit = 'hr.employee'` extension patterns to preserve cohesive active records.
*   **Integrations Isolation (`mi_core` ↔ `mi_connector` ↔ External SSB):** All remote network payloads, asynchronous request polling, and retries belong to `mi_connector`. No raw socket/requests communication may execute directly within primary operational models. Core models must dispatch asynchronous API logs to the queue.

---

### 3. Chinese Payroll & IIT Tax Engines Backlog (`cn_payroll_core` & `cn_payroll_tax`)

| ID | Type | Title | Priority | Odoo Ver | Depends-on | Size | Cross-Module? | Pain Point |
|----|------|-------|----------|----------|------------|------|---------------|------------|
| **EP-6** | **Epic** | **中国薪酬核算与考勤集成** | **Must** | **17** | — | **L** | **yes** | — |
| US-6.1 | Story | As an HR specialist, I want Odoo-native punch card and leave hours summarized into a monthly table so that payroll calculations are automatic | Must | 17 | EP-6 | M | yes (attendance, leave) | YES |
| US-6.2 | Story | As an HR specialist, I want Python-formula wage items to execute in order of structure definitions so that complex Chinese allowances and deductions are exact | Must | 17 | EP-6 | M | no | NO |
| US-6.3 | Story | As an HR specialist, I want employee payslips to consume personal and employer SIHF contributions from the mi system so that deductions and corporate labor costs are correct | Must | 17 | EP-6, EP-2 | S | yes (mi_core) | YES |
| **EP-7** | **Epic** | **中国个税累计预扣预缴管理** | **Must** | **17** | — | **L** | **yes** | — |
| US-7.1 | Story | As an HR specialist, I want year-to-date cumulative taxable income and progressive taxes computed automatically so that monthly withholding is tax-law compliant | Must | 17 | EP-7 | L | yes (cn_payroll_core) | YES |
| US-6.4 | Story | As an HR specialist, I want to configure grace periods and missing check-out tolerances so that standard Odoo attendance calculations adapt to real company rules | Must | 17 | EP-6 | M | no | YES |
| US-6.5 | Story | As an HR specialist, I want different cohorts to follow a hierarchical attendance policy tree (inheriting down the HR department parent_id tree) so that Office, Factory, and Outdoor departments are recursively managed with direct personal overrides | Must | 17 | US-6.4 | M | no | YES |
| US-6.6 | Story | As an HR specialist, I want quick configurations of public holidays that sync automatically with Odoo's native global leaves so that holiday pay is exact | Must | 17 | US-6.4 | S | yes (resource) | YES |
| US-6.7 | Story | As an HR specialist, I want flexible working calendars and multi-bracket Chinese Labor Law overtime calculated so that weekday, weekend, and holiday overtime are compliant | Must | 17 | EP-6 | M | yes (resource) | YES |
| US-6.8 | Story | As an external system developer, I want standard REST JSON sync endpoints for attendance punches and validated leaves so that data flows cleanly into Odoo | Must | 17 | EP-6 | S | no | YES |
| **EP-8** | **Epic** | **财务系统与凭证过账集成** | **Must** | **17** | — | **M** | **yes** | — |
| US-8.1 | Story | As a Finance/HR manager, I want approved monthly payslips to automatically generate corresponding balanced accounting double-entry journal vouchers so that financial records reconcile | Must | 17 | EP-8, EP-6 | M | yes (account) | YES |
| **EP-9** | **Epic** | **劳务外包与双端多租户结算管理** | **Must** | **17** | — | **L** | **yes** | — |
| US-9.1 | Story | As an HR manager, I want to configure contracts for both Hourly Billing and Dispatch Pass-Through structures so that contract terms are digitized | Must | 17 | EP-9 | S | yes (partner) | YES |
| US-9.2 | Story | As an HR manager, I want chronological worker assignments with start/end dates so that mid-month transfers dynamically split worked hours | Must | 17 | EP-9 | M | no | YES |
| US-9.3 | Story | As an HR specialist, I want to copy-paste bulk temporary workers to instantly onboard, map policies, and activate assignments in Odoo | Must | 17 | EP-9 | S | no | YES |
| US-9.4 | Story | As an outsourcing agency contact, I want a secure web portal to log in, view active contracts, and check monthly settlements with absolute multi-tenant data isolation | Must | 17 | EP-9 | M | yes (portal) | YES |
| US-9.5 | Story | As a Finance manager, I want approved monthly settlements to generate corresponding Accounts Payable (AP) Vendor Bills so that supplier invoicing is automatic | Must | 17 | EP-9, EP-8 | M | yes (account) | YES |

---

## BDD Scenarios Index (Updated)

| Story ID | Feature File Path | Scenario | Pain Point Driver | Target Module |
|----------|-------------------|----------|-------------------|---------------|
| US-1.2 | `mi_core/features/policy_rules.feature` | 成功配置城市医保政策规则并执行基数截断 | YES — Calculation correctness | `mi_core` |
| US-1.2 | `mi_core/features/policy_rules.feature` | 拦截重叠生效日期的策略版本冲突 | YES — Version stability | `mi_core` |
| US-2.2 | `mi_core/features/batch_import.feature` | 批量导入包含超限基数和在保重复的混合名单 | YES — Onboarding speed | `mi_core` |
| US-4.2 | `mi_compliance/features/compliance_scan.feature` | 深度扫描未保员工和计算每日万分之五利息 | YES — Fine prevention | `mi_compliance` |
| US-5.2 | `mi_compliance/features/audit_trail.feature` | 生成防篡改合规证据链并验证 SHA-256 哈希值 | YES — Audit safety | `mi_compliance` |
| US-6.4 | `cn_payroll_core/features/attendance_settings.feature` | 配置迟到豁免额度并自动处理缺卡异常 | YES — Process adaptivity | `cn_payroll_core` |
| US-6.5 | `cn_payroll_core/features/attendance_settings.feature` | 多级优先考勤组与漏斗解析策略 | YES — Role mapping | `cn_payroll_core` |
| US-6.6 | `cn_payroll_core/features/attendance_settings.feature` | 中国法定公休规则与 Odoo 资源日历叶自动同步 | YES — Holiday compliance | `cn_payroll_core` |
| US-6.7 | `cn_payroll_core/features/attendance_pay.feature` | 12小时工作制、7天排班及三档次国家规定加班审计 | YES — Overtime compliance | `cn_payroll_core` |
| US-8.1 | `cn_payroll_core/features/accounting_integration.feature` | 生成并结平薪资会计凭证过账 | YES — Financial integrity | `cn_payroll_core` |
| US-9.1 | `cn_payroll_outsourcing/features/outsourcing_settlement.feature` | 工时项目外包模式下的月度工时与增值税结算 | YES — Calculation efficiency | `cn_payroll_outsourcing` |
| US-9.2 | `cn_payroll_outsourcing/features/outsourcing_settlement.feature` | 劳务派遣代发模式下的工资社保个税管理费核算 | YES — Process accuracy | `cn_payroll_outsourcing` |
| US-9.2 | `cn_payroll_outsourcing/features/outsourcing_settlement.feature` | 灵活派驻时间轴重叠自动切割与过滤计算 | YES — Transfer correctness | `cn_payroll_outsourcing` |
| US-9.3 | `cn_payroll_outsourcing/features/outsourcing_settlement.feature` | 快速补员与批量向导导入工人自动建档 | YES — Rapid backfill | `cn_payroll_outsourcing` |
| US-9.4 | `cn_payroll_outsourcing/features/outsourcing_settlement.feature` | 外部劳务商 Portal 安全隔离与数据检索 | YES — Vendor self-service | `cn_payroll_outsourcing` |
| US-10.1 | `cn_payroll_core/features/attendance_pay.feature` | 实发最低工资补差兜底计算验证 | YES — Low wage compliance | `cn_payroll_core` |
| US-10.2 | `cn_payroll_tax/features/cumulative_tax.feature` | 非居民个人单月独立起征点计税计算 | YES — Expat compliance | `cn_payroll_tax` |
| US-10.3 | `cn_payroll_outsourcing/features/outsourcing_settlement.feature` | 劳务派遣用工比例10%红线拦截限制 | YES — Ratio compliance | `cn_payroll_outsourcing` |
| US-10.4 | `cn_payroll_tax/features/cumulative_tax.feature` | 残疾人就业保障金月度预提预估计算 | YES — Accrual planning | `cn_payroll_tax` |
| US-10.5 | `cn_payroll_tax/features/cumulative_tax.feature` | 7大专项附加扣除限额检查与房贷房租互斥校验 | YES — Deductions audits | `cn_payroll_tax` |
| US-10.6 | `cn_payroll_core/features/attendance_pay.feature` | 36小时加班法定上限预警标记生成 | YES — Overtime audit | `cn_payroll_core` |
| US-10.7 | `cn_payroll_outsourcing/features/outsourcing_settlement.feature` | 试用期劳动合同期长限制与80%薪资交叉审计 | YES — Terms audit | `cn_payroll_outsourcing` |
| US-10.8 | `cn_payroll_outsourcing/features/outsourcing_settlement.feature` | 女职工“三期”特保解雇/归档强力拦截校验 | YES — Maternity lock | `cn_payroll_outsourcing` |
| US-11.1 | `financial_reports/features/statement_analysis.feature` | 生成基础财务报表与多期间同比环比比较 | YES — Financial view | `financial_reports` |
| US-11.2 | `financial_reports/features/statement_analysis.feature` | 自定义新型财务管理报表零代码生成与下钻 | YES — Dynamic analysis | `financial_reports` |
| US-3.2 | `mi_connector/features/government_bridge.feature` | 异步申报医保在保申报状态与网关状态查询 | YES — Asynchronous submission | `mi_connector` |
| US-3.2 | `mi_connector/features/government_bridge.feature` | 导出月度在保数据到国家局/社保局统一标准 Excel 模板 | YES — Bulk-import speed | `mi_connector` |
| US-12.1 | `l10n_cn/features/accounting_localization.feature` | 成功初始化和加载不同行业特化的中国会计科目表 (CoA) | YES — Fiscal compliance | `l10n_cn` |
| US-12.2 | `l10n_cn/features/accounting_localization.feature` | 自动生成并导出符合中国审计规范的 landscape 记账凭证 PDF | YES — Voucher legality | `l10n_cn` |

---

### 4. Advanced Compliance & Dynamic Financial Report Backlog (`cn_payroll_core`, `cn_payroll_tax`, `financial_reports`)

| ID | Type | Title | Priority | Odoo Ver | Depends-on | Size | Cross-Module? | Pain Point |
|----|------|-------|----------|----------|------------|------|---------------|------------|
| **EP-10** | **Epic** | **高阶劳动与个税合规性拦截体系** | **Must** | **17** | — | **L** | **yes** | — |
| US-10.1 | Story | As a compliance manager, I want lower-bound minimum wage earnings supplements automatically calculated so that we are protected from wage audits | Must | 17 | EP-6 | S | no | YES |
| US-10.2 | Story | As a tax specialist, I want non-resident individuals taxed on single-month brackets with 5000 RMB exemption so that expat calculations are compliant | Must | 17 | EP-7 | S | no | YES |
| US-10.3 | Story | As an HR director, I want the active dispatched workers ratio capped at 10% under server-side constraints so that we prevent administrative compliance penalties | Must | 17 | EP-9 | M | no | YES |
| US-10.4 | Story | As a CFO, I want the system to calculate monthly pre-accounting disability security fund (残保金) accruals so that fiscal risk is visible | Must | 17 | EP-7 | S | no | NO |
| US-10.5 | Story | As a tax auditor, I want monthly special additional tax deductions audited against 7-project statutory ceilings and housing rental/loan mutual exclusions so that we avoid incorrect tax withholdings | Must | 17 | EP-7 | M | no | YES |
| US-10.6 | Story | As an HR specialist, I want a warning generated when any employee's monthly overtime exceeds the 36-hour legal ceiling so that overtime risk is mitigated | Must | 17 | EP-6 | S | no | YES |
| US-10.7 | Story | As an auditor, I want probation periods and salaries checked against contract terms and 80% thresholds before employee contracts are saved | Must | 17 | EP-9 | M | no | YES |
| US-10.8 | Story | As a legal officer, I want Odoo to prevent dismissing or archiving female employees currently in pregnancy, leave, or lactation phases so that we avoid wrongful termination lawsuits | Must | 17 | EP-9 | S | no | YES |
| **EP-11** | **Epic** | **动态自定义多维财务报表引擎** | **Must** | **17** | — | **L** | **yes** | — |
| US-11.1 | Story | As a CFO, I want standard Balance Sheet, Income Statement, and Cash Flow tables computed and comparative dates aligned so that periods are assessed | Must | 17 | EP-8 | M | yes (account) | YES |
| US-11.2 | Story | As a management accountant, I want to configure any custom financial reports with dynamic hierarchical tree-lines and custom formulas (safe_eval) so that specialized internal reports are generated | Must | 17 | EP-11 | L | yes (account) | YES |
| US-11.3 | Story | As a management accountant, I want to export multi-period reports to Excel and PDF formats preserving parent-child row indentations so that stakeholder reviews are clean | Must | 17 | EP-11 | M | no | YES |
| US-11.4 | Story | As an auditor, I want click-based drilldowns from summary lines directly opening native Odoo account move line list views so that detailed line-audits are rapid | Must | 17 | EP-11 | S | yes (account) | YES |
| **EP-12** | **Epic** | **中国地方政府与行业会计科目表本地化及凭证管理** | **Must** | **17** | — | **M** | **yes** | — |
| US-12.1 | Story | As a finance manager, I want localized Chinese Charts of Accounts (CoA) matching standard Enterprise, Government, NPO, Construction, Agriculture, and Finance rules so that bookkeeping complies with regulatory audits | Must | 17 | EP-8 | M | yes (l10n_cn) | YES |
| US-12.2 | Story | As a bookkeeper, I want native 记账凭证 (Accounting Voucher) PDF layouts with professional signature rows (制单, 审核, 记账, 出纳) so that paper voucher filing is statutory audit-ready | Must | 17 | EP-12 | M | yes (l10n_cn) | YES |
| US-12.3 | Story | As an accountant, I want custom Cash Flow Categories configured on journal entries so that cash flow statements automatically and dynamically reconcile direct cash activities | Should | 17 | EP-11 | S | yes (financial_reports) | YES |



