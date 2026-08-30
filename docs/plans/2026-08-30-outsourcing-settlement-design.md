# Specification: Dual-Mode Labor Outsourcing Settlement Engine

## 1. Architectural Intent & Portal Division
To support Chinese manufacturing, logistics, and service enterprises, this bridge module (`cn_payroll_outsourcing`) manages financial settlements with third-party labor outsourcing and dispatch agencies. It strictly follows the **Bridge-Based Decoupling Rule**, maintaining the purity of core payroll (`cn_payroll_core`) while connecting it to Odoo's native accounting (`account.move`).

The product architecture is divided into two distinct portals to serve corporate HR and external vendors:
*   **Phase 1: Enterprise Portal (企业端 - Current Phase - Fully Implemented):**
    *   Designed for internal Corporate HR & Finance managers.
    *   Provides contract configuration (`cn.outsourcing.contract`), chronological date-ranged assignments (`cn.outsourcing.assignment`), rapid bulk onboarding wizards (`cn.outsourcing.backfill.wizard`), and monthly settlement billing sheets.
    *   Generates native Odoo Accounts Payable Vendor Bills (`account.move`) upon approval.
*   **Phase 2: Outsourcing Agency Portal (外包端 - Next Phase - Planned):**
    *   Designed for external outsourcing agencies (`res.partner` contacts).
    *   Leverages Odoo's native `portal` engine to provide a secure web-based frontend interface.
    *   Allows agencies to securely log in, review active contracts, download generated monthly settlement spreadsheets, upload matching VAT tax invoices (Fapiao), and track corporate payment milestones.

---

## 2. Model Definitions

### 2.1. `cn.outsourcing.contract` (外包/派遣结算合同)
*   **Description:** Defines the billing mechanics between the enterprise and the outsourcing agency (a `res.partner`).
*   **Fields:**
    *   `name` (`Char`, Required): Contract name (e.g., "2024 Logistics Outsourcing Contract").
    *   `agency_id` (`Many2one`, `res.partner`, Required): The outsourcing company/vendor.
    *   `contract_type` (`Selection`: `dispatch` (劳务派遣/代发), `service_rate` (工时外包)): Core billing engine mode.
    *   `admin_fee_per_head` (`Float`, Default=0): Monthly admin fee per worker. Only visible/used if `contract_type == 'dispatch'`.
    *   `hourly_rate` (`Float`, Default=0): Billing rate per hour. Only visible/used if `contract_type == 'service_rate'`.
    *   `vat_rate` (`Float`, Default=0.06): Value Added Tax rate (e.g., 0.06 for 6%, 0.03 for 3%).
    *   `employee_ids` (`Many2many`, `hr.employee`): The pool of outsourced workers governed by this contract.

### 2.2. `cn.outsourcing.settlement` (外包结算对账单)
*   **Description:** The monthly billing statement generated against an active contract.
*   **Fields:**
    *   `name` (`Char`, Required): Settlement name (e.g., "BILL-2024-03 Logistics").
    *   `contract_id` (`Many2one`, `cn.outsourcing.contract`, Required): Parent contract.
    *   `period` (`Char`, Required): Billing month (e.g., "2024-03").
    *   `state` (`Selection`: `draft` (草稿), `approved` (已审核/锁定)): Settlement state.
    *   `subtotal_amount` (`Float`, Compute): Total before taxes.
    *   `vat_amount` (`Float`, Compute): Total VAT.
    *   `total_amount` (`Float`, Compute): Grand total to be paid to the agency.
    *   `vendor_bill_id` (`Many2one`, `account.move`): The generated Odoo native Vendor Bill.
    *   `line_ids` (`One2many`, `cn.outsourcing.settlement.line`): Individual worker billing lines.

### 2.3. `cn.outsourcing.settlement.line` (结算账单明细行)
*   **Description:** The exact mathematical breakdown of costs per worker per month.
*   **Fields:**
    *   `settlement_id` (`Many2one`, `cn.outsourcing.settlement`, Required, Cascade).
    *   `employee_id` (`Many2one`, `hr.employee`, Required).
    *   `attendance_hours` (`Float`): Sourced from `cn.attendance.summary` (`total_work_hours`).
    *   `gross_salary` (`Float`): Sourced from `cn.payslip` total gross.
    *   `sihf_employer` (`Float`): Sourced from `mi.enrollment`.
    *   `sihf_employee` (`Float`): Sourced from `mi.enrollment`.
    *   `iit_withheld` (`Float`): Sourced from `cn.payslip` IIT line.
    *   `admin_fee` (`Float`): Sourced from parent contract.
    *   `line_subtotal` (`Float`, Compute):
        *   If `dispatch`: `gross_salary + sihf_employer + sihf_employee + iit_withheld + admin_fee`.
        *   If `service_rate`: `attendance_hours * contract.hourly_rate`.

---

## 3. Orchestration & Engine Logic

### 3.1. `action_generate_lines()`
When the HR manager clicks "Generate Lines" on a draft settlement, the engine:
1. Iterates over every `hr.employee` in `contract_id.employee_ids`.
2. Locates the `cn.attendance.summary` for the matching `period`. If `state != 'approved'`, raises a UserError (Attendance must be locked).
3. If `dispatch` mode, locates the `cn.payslip` for the matching `period`. If `state != 'done'`, raises a UserError (Payslips must be locked).
4. Populates the exact mathematical values into a new `cn.outsourcing.settlement.line`.

### 3.2. `action_approve_and_bill()`
When the HR/Finance manager clicks "Approve", the engine:
1. Changes state to `approved` to lock the record.
2. Generates an `account.move` of `move_type = 'in_invoice'` (Vendor Bill).
3. Sets `partner_id = contract_id.agency_id`.
4. Creates a single summary line on the vendor bill reflecting the `subtotal_amount` and attaches native Odoo taxes representing the `vat_rate`.
5. Links `vendor_bill_id` back to the settlement record.
