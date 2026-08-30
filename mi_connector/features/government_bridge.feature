# l10n: zh_CN
# -*- coding: utf-8 -*-
Feature: Asynchronous Government SSB Declaration Bridge & Batch Excel Export
  As an HR Specialist
  I want to submit medical insurance declarations asynchronously to the State SSB, poll for approvals, and export batch Excel sheets
  So that employee onboarding and municipal compliance reporting are fully automated with zero copy-paste errors

  Background:
    Given a clean active Medical Insurance Policy for "Shanghai" starting "2026-07-01"
    And a standard medical insurance line with base range 5,000.0 to 30,000.0 RMB
    And an active employee named "Declaration Test Worker" with citizen ID "110101199003071234"

  Scenario: Successful Asynchronous Enrollment Declaration and Polling Approval
    Given a pending Medical Insurance Enrollment for "Declaration Test Worker" with base 8,000.0 RMB
    When the HR specialist triggers "Declare to SSB"
    Then the enrollment declaration state transitions to "submitting"
    And a unique transaction receipt "TX-SSB-XXXX" is logged in Odoo
    And a "pending" transaction audit log is created in "mi.api.log"
    When the SSB government polling cron is executed under "test_force_success" mode
    Then the api log state transitions to "success"
    And the enrollment state becomes "enrolled"
    And the enrollment declaration state becomes "enrolled"
    And a registration code starting with "SSB-REG-" is posted to the employee's chatter

  Scenario: Government Rejection and Automated HR Corrective Reversion
    Given a pending Medical Insurance Enrollment for "Declaration Test Worker" with base 8,000.0 RMB
    When the HR specialist triggers "Declare to SSB"
    And the SSB government polling cron is executed under "test_force_fail" mode
    Then the api log state transitions to "failed"
    And the enrollment state reverts to "draft"
    And the enrollment declaration state becomes "rejected"
    And a red-colored warning alert containing the rejection reason is posted to the chatter

  Scenario: Export Monthly Enrollments to Unified SSB Excel Template
    Given a pending Medical Insurance Enrollment for "Declaration Test Worker" with base 7,500.0 RMB starting "2026-08-15"
    When the HR specialist instantiates the Export Wizard for period "2026-08" and state "pending"
    And triggers "Generate Export File"
    Then the wizard export status becomes "done"
    And a binary Excel document "SSB_Unified_Enrollment_2026-08_pending.xlsx" is successfully generated
    And the generated sheet contains columns "员工姓名", "证件号码", "申报缴费基数", and "起保日期"
