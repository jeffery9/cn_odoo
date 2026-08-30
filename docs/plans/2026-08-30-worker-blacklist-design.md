# Specification: Enterprise Outsourcing Blacklist

## 1. Architectural Intent
To safeguard corporate property, operational discipline, and workspace safety, enterprises must enforce a strict **Blacklist Verification Sandbox** for outsourced and dispatch workers.

If a worker is blacklisted (due to safety violations, fraud, or code-of-conduct breaches), the system must block them from being assigned to any active outsourcing contract or onboarding wizard. 

Identity matching must support **multi-dimensional checks** (Odoo Barcode, ID Card Number / Identification ID, and Mobile Phone) to prevent workers from circumventing blocks by changing their worker ID.

---

## 2. Model Definitions

### 2.1. `cn.outsourcing.blacklist` (企业外包黑名单表)
*   **Description:** Stores blacklisted outsourced personnel details.
*   **Fields:**
    *   `name` (`Char`, Required): Worker's name.
    *   `id_card_num` (`Char`): Identity Card Number (身份证号 - primary national ID).
    *   `barcode` (`Char`): Barcode or past employee card number.
    *   `mobile` (`Char`): Mobile phone number.
    *   `reason` (`Text`, Required): Cause for blacklisting (e.g., safety protocol breach).
    *   `active` (`Boolean`, Default=True): Enables soft archiving.

---

## 3. Server-Side Enforcement Rules

### 3.1. `cn.outsourcing.assignment` Block Checks
*   Inside `_check_worker_qualifications` constraint, query `cn.outsourcing.blacklist` where `active = True`:
    *   Match target `hr.employee`'s `barcode`, Odoo standard `identification_id`, or `mobile_phone` against the blacklist registry.
    *   If any dimension matches, raise a `ValidationError` blocking the transaction and displaying the specific blacklisting reason.

### 3.2. Wizard Atomic Rollback
*   If an HR specialist attempts to bulk-import a list containing a blacklisted worker via `cn.outsourcing.backfill.wizard`, Odoo's SQL transaction savepoint will automatically rollback the entire import operation, alerting the operator to the compliance breach.
