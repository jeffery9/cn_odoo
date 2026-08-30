# Specification: Enterprise Multi-Company Data Isolation

## 1. Architectural Intent
Large manufacturing and logistics enterprises in China operate as conglomerate groups with multiple legal entities (subsidiaries, regional branches, and different business divisions).

To support this natively, the `cn_payroll_outsourcing` module must enforce **Strict Multi-Company Data Isolation (多公司隔离)**. 

Corporate users logged into Company A must never cross-read, modify, or bill contracts and settlements belonging to Company B, unless they have multi-company toggles active in their profile. 

At the same time, the **Blacklist Registry** must support both **Company-Specific** and **Global (cross-subsidiary) blacklisting** to prevent shared-risk leakage across legal entities.

---

## 2. Model Extensions

### 2.1. `company_id` Field Integration

We will add a Many2one `company_id` field to all major models:
1.  **`cn.outsourcing.contract`**:
    *   `company_id` (`Many2one`, `res.company`, Required): Mapped to active legal entity. Defaults to the active company context.
2.  **`cn.outsourcing.assignment`**:
    *   `company_id` (`Many2one`, `res.company`, Required, Store=True, Related='contract_id.company_id'): Auto-inherited from the associated contract for query optimization and record-rule indexing.
3.  **`cn.outsourcing.settlement`**:
    *   `company_id` (`Many2one`, `res.company`, Required): Defaulting to `self.env.company`.
4.  **`cn.outsourcing.blacklist`**:
    *   `company_id` (`Many2one`, `res.company`, Optional): If populated, the blacklist rule applies only to that subsidiary. If left blank, it acts as a **Global Group Blacklist** matching across all subsidiaries.

---

## 3. Odoo Record Rules (`ir.rule`)

We will define native multi-company security rules in a new file `security/multi_company_security.xml`:
*   Standard multi-company filter pattern:
    `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`
*   This ensures that standard ORM lookups automatically filter out records belonging to other companies.
