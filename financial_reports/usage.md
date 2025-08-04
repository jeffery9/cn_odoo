# Financial Reports Module Usage Guide

This guide explains how to install, configure, and use the Financial Reports module in Odoo.

## 1. Installation

1.  **Place the Module:** Copy the `financial_reports` folder into your Odoo `addons` path.
2.  **Update Odoo:** Restart your Odoo server.
3.  **Install/Upgrade in Odoo:**
    *   Navigate to `Apps` in your Odoo instance.
    *   Click on `Update Apps List`.
    *   Search for "Financial Reports" (or "财务报告" if your Odoo is in Chinese).
    *   Click the `Install` button. If the module was already installed and you made changes, click `Upgrade`.

## 2. Configuration of Financial Reports

This module leverages Odoo's native `account.report` model, allowing you to define highly customizable financial reports.

1.  **Access Configuration:**
    *   Go to `Accounting` -> `Configuration` -> `Financial Reports`.
    *   Here, you will see a list of existing financial reports (e.g., Balance Sheet, Profit & Loss) and can create new ones.

2.  **Create/Edit a Report:**
    *   Click `Create` to define a new report, or select an existing one to edit.
    *   **Name:** The name of your report (e.g., "My Custom Balance Sheet").
    *   **Report Type:** (Informational, usually `balance_sheet`, `income_statement`, `cash_flow`).
    *   **Report Lines:** This is the core of your report. You define the hierarchical structure of your report here.
        *   For each line, you can define its `Name`, `Sequence`, `Level` (for indentation), and `Action` (for drill-down).
        *   **Expressions:** Within each report line, you define how its value is calculated using expressions. This module supports:
            *   `Account`: Sum of a specific account.
            *   `Account Type`: Sum of accounts belonging to a specific type.
            *   `Account Group`: Sum of accounts belonging to a specific group.
            *   `Tax Tags`: Sum based on tax tags.
            *   `Aggregation`: Sum of other expressions (allows for complex calculations).
            *   `Formula`: Custom Python formula (use with caution due to security implications).
            *   `Analytic Account`: Sum based on a specific analytic account.
            *   `Analytic Plan`: Sum based on accounts linked to a specific analytic plan.

3.  **Preview Report:**
    *   While editing a report, click the `Preview` button in the header to immediately see how your report looks in the viewer.

## 3. Viewing Financial Reports

Once reports are configured, they will appear directly in your Odoo menu.

1.  **Access Reports:**
    *   Go to `Accounting` -> `Reporting` -> `Financial Reports`.
    *   Under this menu, you will find dynamically generated menu items for each `account.report` you have defined.
    *   Click on the desired report (e.g., "Balance Sheet", "Profit and Loss").

2.  **Report Viewer Features:**
    *   **Dynamic Display:** The report will load in a dynamic viewer.
    *   **Multi-Period Comparison:**
        *   You can add multiple periods for comparison using the `Add Period` button.
        *   For each period, specify `From` and `To` dates.
        *   The report will display a column for each selected period.
    *   **Hierarchical View:** Report lines are displayed in a tree-like structure. Click the caret icon (▶/▼) to expand or collapse sub-lines.
    *   **Drill-Down:** Click on any numerical value in the report to drill down and view the underlying `account.move.line` entries.
    *   **Export:**
        *   `Export PDF`: Generates a PDF version of the displayed report, including multi-period columns and indentation.
        *   `Export Excel`: Generates an Excel spreadsheet of the displayed report, including multi-period columns.

## 4. Cash Flow Categories Configuration

This module also introduces a way to categorize cash flow activities, which can be used in your cash flow reports.

1.  **Access Configuration:**
    *   Go to `Accounting` -> `Configuration` -> `Cash Flow Categories`.

2.  **Create/Edit Categories:**
    *   Define categories (e.g., "Cash from Operations", "Cash for Investments").
    *   Assign an `Activity Type` (Operating, Investing, Financing).
    *   Link `Related Accounts` to these categories. This linkage can then be used in your `account.report.expression` definitions for cash flow statements.

