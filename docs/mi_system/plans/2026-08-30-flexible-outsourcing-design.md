# Specification: Flexible Worker Assignments & Rapid Labor Backfills

## 1. Architectural Intent
During peak logistics seasons or production shortages (e.g., Double 11, Chinese New Year peak), enterprises need to:
1.  **Flexibly Adjust Worker Assignments (灵活调整工人安排):** Reallocate outsourced workers mid-month across different contracts, agencies, or departments, billing their hours chronologically.
2.  **Rapidly Backfill Labor Shortages (快速补充劳动力):** Instantly onboard dozens of temporary workers, register their barcodes/contracts, and assign them to standard working calendars.

To achieve this cleanly, we will expand `cn_payroll_outsourcing` with a dynamic **chronological assignment registry** and a **rapid onboarding wizard**.

---

## 2. Model Definitions

### 2.1. `cn.outsourcing.assignment` (外包工人派驻期表)
*   **Description:** Replaces static Many2many worker links with chronological date-ranged assignments. If a worker is transferred from Agency A to Agency B mid-month, their billing hours are split based on active dates.
*   **Fields:**
    *   `contract_id` (`Many2one`, `cn.outsourcing.contract`, Required, On-delete='Cascade'): The target contract.
    *   `employee_id` (`Many2one`, `hr.employee`, Required): The assigned worker.
    *   `date_start` (`Date`, Required): Assignment start date.
    *   `date_end` (`Date`, Optional): Assignment end date (null represents currently active).
*   **Chronological Splitting Logic:**
    When generating monthly lines, the settlement engine will intersect the worker's active `cn.outsourcing.assignment` dates with the settlement billing period, calculating and allocating only the attendance hours worked during that active window.

### 2.2. `cn.outsourcing.backfill.wizard` (快速补员与批量派驻向导)
*   **Description:** A transient wizard allowing HR specialists to copy-paste names or import barcodes to rapidly onboard and assign bulk backfill workers.
*   **Fields:**
    *   `contract_id` (`Many2one`, `cn.outsourcing.contract`, Required): The target contract.
    *   `date_start` (`Date`, Required, Default=Today): Assignment start date.
    *   `attendance_settings_id` (`Many2one`, `cn.attendance.settings`): The attendance policy/calendar to assign them to.
    *   `worker_raw_list` (`Text`, Required): Bulk text payload (e.g. "Zhang San,9001\nLi Si,9002" representing `Name,Barcode`).
*   **Onboarding Engine Logic:**
    When executed, the wizard performs the following in a single transaction savepoint:
    1. Parses each line of `worker_raw_list`.
    2. Creates the `hr.employee` record (setting `barcode` and active status).
    3. Links the new employee to the specified `attendance_settings_id` (supporting tree-based policy resolution).
    4. Creates a `cn.outsourcing.assignment` starting at `date_start`.
