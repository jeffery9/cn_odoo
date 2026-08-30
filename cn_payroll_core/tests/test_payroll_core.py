# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo import fields

class TestPayrollCore(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env.user.write({'tz': 'Asia/Shanghai'})
        self.env.flush_all()
        # Clean up existing salary item with BASIC code to avoid unique violations
        existing = self.env['cn.salary.item'].search([('code', '=', 'BASIC')])
        if existing:
            existing.unlink()
        # Clean up all existing calendar leaves to prevent overlap validation errors
        self.env['resource.calendar.leaves'].search([]).unlink()

        # Create a dedicated clean calendar for this test transaction to avoid any cache/state contamination
        calendar = self.env['resource.calendar'].create({
            'name': 'Test Default Calendar',
            'company_id': self.env.company.id,
        })
        calendar.attendance_ids.unlink()
        self.env.company.resource_calendar_id = calendar.id
        self.test_calendar = calendar

        self.item_basic = self.env['cn.salary.item'].create({
            'name': 'Basic Wage',
            'code': 'BASIC',
            'item_type': 'fixed',
            'is_taxable': True,
        })
        self.structure = self.env['cn.salary.structure'].create({
            'name': 'Standard White Collar',
            'item_ids': [(4, self.item_basic.id)],
        })
        self.env.flush_all()
        self.env.invalidate_all()

    def test_salary_item_code_unique(self):
        """Validate that salary item codes must be strictly unique"""
        from psycopg2 import IntegrityError
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env['cn.salary.item'].create({
                    'name': 'Duplicate Basic',
                    'code': 'BASIC',
                    'item_type': 'fixed',
                })
                self.env['cn.salary.item'].flush_model()

    def test_attendance_summary_native_parsing(self):
        """Validate that the monthly summary correctly parses native Odoo attendances and leaves"""
        settings = self.env['cn.attendance.settings'].create({
            'name': 'Standard Office Settings',
            'company_id': self.env.company.id,
            'standard_check_in': 9.0,
            'standard_check_out': 18.0,
        })
        employee = self.env['hr.employee'].create({
            'name': 'Attendance Worker',
            'attendance_settings_id': settings.id,
            'resource_calendar_id': self.test_calendar.id,
        })
        
        # Create workday holiday rules to target only specific dates for evaluation
        self.env['cn.attendance.holiday.rule'].create({
            'name': 'Test Workday 1',
            'holiday_type': 'workday',
            'date': '2024-03-01',
            'settings_id': settings.id,
        })
        self.env['cn.attendance.holiday.rule'].create({
            'name': 'Test Workday 2',
            'holiday_type': 'workday',
            'date': '2024-03-05',
            'settings_id': settings.id,
        })
        self.env['cn.attendance.holiday.rule'].create({
            'name': 'Test Workday 3',
            'holiday_type': 'workday',
            'date': '2024-03-06',
            'settings_id': settings.id,
        })
        
        # 1. Simulate check_in/check_out on 2024-03-01
        # Shift standard in is 09:00 AM. Employee checks in at 09:15 -> 15 minutes late.
        self.env['hr.attendance'].create({
            'employee_id': employee.id,
            'check_in': '2024-03-01 01:15:00', # UTC (09:15:00 Beijing time)
            'check_out': '2024-03-01 10:00:00', # UTC (18:00:00 Beijing time)
        })

        # 2. Simulate 2 days personal leave on hr.leave (March 5 to March 6)
        leave_type = self.env['hr.leave.type'].search([('name', 'ilike', 'personal')], limit=1)
        if not leave_type:
            leave_type = self.env['hr.leave.type'].create({
                'name': 'Personal Leave',
                'requires_allocation': 'no',
            })
        leave = self.env['hr.leave'].create({
            'employee_id': employee.id,
            'holiday_status_id': leave_type.id,
            'date_from': '2024-03-05 01:00:00',
            'date_to': '2024-03-06 10:00:00',
            'number_of_days': 2.0,
        })
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE hr_leave SET state = 'validate', number_of_days = 2.0, date_from = %s, date_to = %s WHERE id = %s",
            ['2024-03-05 01:00:00', '2024-03-06 10:00:00', leave.id]
        )
        self.env.invalidate_all()

        # Run Summarizer
        summary = self.env['cn.attendance.summary'].create({
            'employee_id': employee.id,
            'period': '2024-03',
        })
        summary.action_calculate_summary()

        self.assertEqual(summary.late_minutes, 15)
        self.assertEqual(summary.personal_leave_days, 2.0)

    def test_attendance_deduction_calculation(self):
        """Validate that employee payslip correctly computes attendance deduction rules using parsed variables"""
        employee = self.env['hr.employee'].create({
            'name': 'Zhang San Pay',
            'resource_calendar_id': self.test_calendar.id,
        })
        
        # Setup items
        item_basic = self.item_basic
        item_absent = self.env['cn.salary.item'].create({
            'name': 'Absent Deduction', 'code': 'ABSENT', 'item_type': 'deduction',
            'python_code': 'result = - (BASIC / 21.75) * personal_leave_days'
        })
        item_late = self.env['cn.salary.item'].create({
            'name': 'Late Deduction', 'code': 'LATE', 'item_type': 'deduction',
            'python_code': 'result = - 50 if late_minutes > 30 else (-20 if late_minutes > 10 else 0)'
        })
        item_net = self.env['cn.salary.item'].create({
            'name': 'Net Salary', 'code': 'NET', 'item_type': 'fixed',
            'python_code': 'result = BASIC + ABSENT + LATE'
        })

        struct = self.env['cn.salary.structure'].create({
            'name': 'White Collar Structured',
            'item_ids': [(4, item_basic.id), (4, item_absent.id), (4, item_late.id), (4, item_net.id)],
        })

        # Inject Attendance Summary (15 min late, 1 day personal leave)
        self.env['cn.attendance.summary'].create({
            'employee_id': employee.id,
            'period': '2024-03',
            'late_minutes': 15,
            'personal_leave_days': 1.0,
        })

        # Create slips
        payslip = self.env['cn.payslip'].create({
            'employee_id': employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 10000.0,
        })
        
        payslip.action_compute_sheet()
        
        # Assert computations
        basic_line = payslip.line_ids.filtered(lambda l: l.code == 'BASIC')
        self.assertEqual(basic_line.amount, 10000.0)
        
        absent_line = payslip.line_ids.filtered(lambda l: l.code == 'ABSENT')
        self.assertAlmostEqual(absent_line.amount, -459.77, places=2) # -10000/21.75 * 1
        
        late_line = payslip.line_ids.filtered(lambda l: l.code == 'LATE')
        self.assertEqual(late_line.amount, -20.0) # 15 minutes is > 10 -> -20.0
        
        net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
        self.assertAlmostEqual(net_line.amount, 9520.23, places=2)

    def test_mi_integration_social_insurance_deductions(self):
        """Validate that payslips dynamically pull confirmed employee social insurance deductions from mi system"""
        employee = self.env['hr.employee'].create({'name': 'Li Si'})
        state_bj = self.env['res.country.state'].search([], limit=1)
        
        # Setup Policy & SIHF enrollment in mi_core
        policy = self.env['mi.policy'].create({
            'name': 'Beijing Policy 2024',
            'region_id': state_bj.id,
            'date_start': '2024-01-01',
            'state': 'active',
        })
        self.env['mi.policy.line'].create({
            'policy_id': policy.id,
            'insurance_type': 'medical',
            'base_min': 5000.0,
            'base_max': 30000.0,
            'rate_employer': 10.0,
            'rate_employee': 2.0,
        })
        
        enrollment = self.env['mi.enrollment'].create({
            'employee_id': employee.id,
            'policy_id': policy.id,
            'base_amount': 10000.0,
            'start_date': '2024-01-01',
            'state': 'enrolled',
        })
        self.assertEqual(enrollment.amount_employee, 200.0)

        # Setup Payroll structures
        item_basic = self.item_basic
        item_sihf = self.env['cn.salary.item'].create({
            'name': 'SIHF Deduction', 'code': 'SIHF', 'item_type': 'deduction',
            'python_code': 'result = - SIHF_PERSONAL'
        })
        item_corp = self.env['cn.salary.item'].create({
            'name': 'Corporate Cost', 'code': 'CORP', 'item_type': 'variable',
            'python_code': 'result = BASIC + SIHF_EMPLOYER'
        })
        item_net = self.env['cn.salary.item'].create({
            'name': 'Net Salary', 'code': 'NET', 'item_type': 'fixed',
            'python_code': 'result = BASIC + SIHF'
        })

        struct = self.env['cn.salary.structure'].create({
            'name': 'Standard SIHF Structure',
            'item_ids': [(4, item_basic.id), (4, item_sihf.id), (4, item_corp.id), (4, item_net.id)],
        })

        # Calculate Slip
        payslip = self.env['cn.payslip'].create({
            'employee_id': employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 12000.0,
        })
        
        payslip.action_compute_sheet()
        
        sihf_line = payslip.line_ids.filtered(lambda l: l.code == 'SIHF')
        self.assertEqual(sihf_line.amount, -200.0)

        # Corporate cost = BASIC (12000) + SIHF_EMPLOYER (10000 * 10% = 1000) = 13000.0
        corp_line = payslip.line_ids.filtered(lambda l: l.code == 'CORP')
        self.assertEqual(corp_line.amount, 13000.0)
        
        net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
        self.assertEqual(net_line.amount, 11800.0)

    def test_attendance_settings_and_missing_checkout_calculations(self):
        """Validate that attendance calculations respect company settings, grace periods, and missing checkout fallbacks"""
        employee = self.env['hr.employee'].create({
            'name': 'Settings Worker',
            'resource_calendar_id': self.test_calendar.id,
        })
        
        # 1. Create company attendance settings
        settings = self.env['cn.attendance.settings'].create({
            'name': 'Checkout Settings',
            'company_id': self.env.company.id,
            'standard_check_in': 9.0, # 09:00 AM
            'grace_period_late': 15,  # 15 mins grace period
            'missing_checkout_fallback': 'absent', # half-day absent for missing check-out
        })
        employee.attendance_settings_id = settings.id

        # Create workday holiday rules to target only specific dates for evaluation
        self.env['cn.attendance.holiday.rule'].create({
            'name': 'Test Workday 1',
            'holiday_type': 'workday',
            'date': '2024-03-01',
            'settings_id': settings.id,
        })
        self.env['cn.attendance.holiday.rule'].create({
            'name': 'Test Workday 2',
            'holiday_type': 'workday',
            'date': '2024-03-04',
            'settings_id': settings.id,
        })

        # 2. Simulate Check-in at 09:12 -> within 15 mins grace period -> late_minutes should be 0.
        # But wait, this record lacks check_out! Under 'absent' fallback policy, absent_days should be 0.5.
        self.env['hr.attendance'].create({
            'employee_id': employee.id,
            'check_in': '2024-03-01 01:12:00', # UTC (09:12 Beijing time)
            'check_out': False,
        })

        # 3. Simulate another day's punch: Check-in at 09:20 -> exceeds 15 mins grace period -> late_minutes is 20.
        # With valid check_out.
        self.env['hr.attendance'].create({
            'employee_id': employee.id,
            'check_in': '2024-03-04 01:20:00', # UTC (09:20 Beijing time)
            'check_out': '2024-03-04 10:00:00', # UTC (18:00 Beijing time)
        })

        # Run Summary
        self.env.flush_all()
        self.env.invalidate_all()
        summary = self.env['cn.attendance.summary'].create({
            'employee_id': employee.id,
            'period': '2024-03',
        })
        summary.action_calculate_summary()

        # Assertions
        # 12 mins late is <= 15 grace, so only the 20 mins late is counted.
        self.assertEqual(summary.late_minutes, 20)
        # Missing check_out triggers fallback policy -> 0.5 absent days
        self.assertEqual(summary.absent_days, 0.5)

    def test_accounting_voucher_posting(self):
        """Validate that approved payslips automatically generate balanced accounting double-entry vouchers"""
        employee = self.env['hr.employee'].create({
            'name': 'Finance Worker',
            'resource_calendar_id': self.test_calendar.id,
        })
        
        # 1. Setup minimal accounting data
        # Accounts
        expense_account = self.env['account.account'].create({
            'name': 'Management Expense - Salary',
            'code': '660101',
            'account_type': 'expense',
        })
        payable_account = self.env['account.account'].create({
            'name': 'Salary Payable',
            'code': '221101',
            'account_type': 'liability_current',
        })
        # Journal
        payroll_journal = self.env['account.journal'].create({
            'name': 'Payroll Journal',
            'code': 'PAY',
            'type': 'general',
        })

        # 2. Update existing salary item with debit/credit mappings and journal
        self.item_basic.write({
            'debit_account_id': expense_account.id,
            'credit_account_id': payable_account.id,
            'journal_id': payroll_journal.id,
        })
        item_basic = self.item_basic
        
        struct = self.env['cn.salary.structure'].create({
            'name': 'Accounting Mapped Structure',
            'item_ids': [(4, item_basic.id)],
        })

        # 3. Create and compute payslip
        payslip = self.env['cn.payslip'].create({
            'employee_id': employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 10000.0,
        })
        payslip.action_compute_sheet()

        # 4. Generate voucher posting
        payslip.action_post_journal_entry()

        # 5. Assertions
        self.assertTrue(payslip.move_id, "Journal entry should be generated")
        self.assertEqual(payslip.state, 'approved', "Payslip state should transition to approved")
        
        # Verify double-entry balances
        self.assertEqual(payslip.move_id.journal_id.id, payroll_journal.id)
        
        debit_total = sum(payslip.move_id.line_ids.mapped('debit'))
        credit_total = sum(payslip.move_id.line_ids.mapped('credit'))
        self.assertEqual(debit_total, 10000.0)
        self.assertEqual(credit_total, 10000.0)
        self.assertEqual(debit_total, credit_total, "Double-entry must be balanced!")

    def test_resource_calendar_synchronization(self):
        """Validate that configuring custom check-in/out hours automatically synchronizes Odoo's native resource calendar"""
        # Create standard Odoo resource calendar for current company if not existing, or update active one
        calendar = self.env.company.resource_calendar_id
        if not calendar:
            calendar = self.env['resource.calendar'].create({
                'name': 'Test Standard 40 Hours',
                'company_id': self.env.company.id,
            })
            self.env.company.resource_calendar_id = calendar.id

        # Setup standard lines on the calendar (Mon to Fri morning & afternoon splits)
        # We delete existing lines first to have deterministic test state
        calendar.attendance_ids.unlink()
        for day in ['0', '1', '2', '3', '4']:
            self.env['resource.calendar.attendance'].create({
                'name': f"Day {day} Morning",
                'dayofweek': day,
                'hour_from': 8.0,
                'hour_to': 12.0,
                'calendar_id': calendar.id,
            })
            self.env['resource.calendar.attendance'].create({
                'name': f"Day {day} Afternoon",
                'dayofweek': day,
                'hour_from': 13.0,
                'hour_to': 17.0,
                'calendar_id': calendar.id,
            })

        # Now, create custom CnAttendanceSettings (Check-in 09:30, Check-out 18:30)
        self.env['cn.attendance.settings'].create({
            'name': 'Custom Settings',
            'company_id': self.env.company.id,
            'standard_check_in': 9.5, # 09:30
            'standard_check_out': 18.5, # 18:30
        })

        # Assertions: first lines of Monday (dayofweek '0') should have hour_from updated to 9.5
        # and last line's hour_to updated to 18.5!
        mon_lines = calendar.attendance_ids.filtered(lambda l: l.dayofweek == '0').sorted(key=lambda l: l.hour_from)
        self.assertEqual(mon_lines[0].hour_from, 9.5)
        self.assertEqual(mon_lines[-1].hour_to, 18.5)

    def test_sync_attendance_api(self):
        """Validate that standard REST sync endpoint correctly registers check_in and check_out records"""
        from odoo.addons.cn_payroll_core.controllers.main import CnPayrollSyncController
        employee = self.env['hr.employee'].create({'name': 'Ding Worker', 'barcode': 'EMP_DING_001'})
        controller = CnPayrollSyncController()

        from unittest.mock import patch, MagicMock
        mock_req = MagicMock()
        mock_req.env = self.env
        mock_req.jsonrequest = {
            'emp_id': 'EMP_DING_001',
            'time': '2024-03-01 09:05:00',
            'type': 'check_in'
        }

        with patch('odoo.addons.cn_payroll_core.controllers.main.request', mock_req):
            res = controller.sync_attendance()
            self.assertEqual(res['status'], 'success')
            self.assertTrue(res['id'])

            # Verify hr.attendance record
            attendance = self.env['hr.attendance'].browse(res['id'])
            self.assertEqual(attendance.employee_id.id, employee.id)
            self.assertEqual(fields.Datetime.to_string(attendance.check_in), '2024-03-01 09:05:00')

        # Simulate check-out payload
        mock_req.jsonrequest = {
            'emp_id': 'EMP_DING_001',
            'time': '2024-03-01 18:05:00',
            'type': 'check_out'
        }
        with patch('odoo.addons.cn_payroll_core.controllers.main.request', mock_req):
            res = controller.sync_attendance()
            self.assertEqual(res['status'], 'success')
            self.assertEqual(fields.Datetime.to_string(attendance.check_out), '2024-03-01 18:05:00')

    def test_sync_leave_api(self):
        """Validate that standard REST sync endpoint correctly registers approved leave records"""
        from odoo.addons.cn_payroll_core.controllers.main import CnPayrollSyncController
        employee = self.env['hr.employee'].create({'name': 'Ding Leave Worker', 'barcode': 'EMP_DING_002'})
        controller = CnPayrollSyncController()

        from unittest.mock import patch, MagicMock
        mock_req = MagicMock()
        mock_req.env = self.env
        mock_req.jsonrequest = {
            'emp_id': 'EMP_DING_002',
            'date_from': '2024-03-05 09:00:00',
            'date_to': '2024-03-06 18:00:00',
            'type': 'personal'
        }

        with patch('odoo.addons.cn_payroll_core.controllers.main.request', mock_req):
            res = controller.sync_leave()
            self.assertEqual(res['status'], 'success')
            self.assertTrue(res['id'])

            # Verify hr.leave record
            leave = self.env['hr.leave'].browse(res['id'])
            self.assertEqual(leave.employee_id.id, employee.id)
            self.assertTrue(leave.date_from)
            self.assertEqual(leave.state, 'validate')

    def test_multi_cohort_attendance_settings(self):
        """Validate that different employee cohorts correctly resolve to their respective priority-based attendance policies and sync dedicated calendars"""
        # Setup dedicated calendars
        calendar_dept = self.env['resource.calendar'].create({
            'name': 'Factory Working Schedule',
            'company_id': self.env.company.id,
        })
        calendar_dept.attendance_ids.unlink()
        for day in ['0', '1', '2', '3', '4']:
            self.env['resource.calendar.attendance'].create({
                'name': f"Factory Mon",
                'dayofweek': day,
                'hour_from': 8.5,
                'hour_to': 17.5,
                'calendar_id': calendar_dept.id,
            })

        calendar_emp = self.env['resource.calendar'].create({
            'name': 'Executive Schedule',
            'company_id': self.env.company.id,
        })
        calendar_emp.attendance_ids.unlink()
        for day in ['0', '1', '2', '3', '4']:
            self.env['resource.calendar.attendance'].create({
                'name': f"Exec Mon",
                'dayofweek': day,
                'hour_from': 9.0,
                'hour_to': 18.0,
                'calendar_id': calendar_emp.id,
            })

        # Setup departments
        dept_factory = self.env['hr.department'].create({
            'name': 'Production Factory',
        })
        
        # Setup employees
        emp_factory = self.env['hr.employee'].create({
            'name': 'Blue-collar Worker',
            'department_id': dept_factory.id,
            'resource_calendar_id': calendar_dept.id,
        })
        emp_office = self.env['hr.employee'].create({
            'name': 'White-collar Worker',
            'resource_calendar_id': self.test_calendar.id,
        })
        emp_executive = self.env['hr.employee'].create({
            'name': 'CEO Worker',
            'resource_calendar_id': calendar_emp.id,
        })

        # Setup 3 policies with hierarchical organization links
        # 1. Company Default Policy (No direct link, serves as fallback)
        policy_company = self.env['cn.attendance.settings'].create({
            'name': 'Company Default (09:00 AM)',
            'company_id': self.env.company.id,
            'standard_check_in': 9.0,
        })

        # 2. Department-Specific Policy
        policy_department = self.env['cn.attendance.settings'].create({
            'name': 'Factory Dedicated (08:00 AM)',
            'company_id': self.env.company.id,
            'standard_check_in': 8.0,
            'standard_check_out': 17.0,
        })
        dept_factory.attendance_settings_id = policy_department.id

        # 3. Employee-Specific Policy
        policy_employee = self.env['cn.attendance.settings'].create({
            'name': 'Executive Dedicated (10:00 AM)',
            'company_id': self.env.company.id,
            'standard_check_in': 10.0,
            'standard_check_out': 19.0,
        })
        emp_executive.attendance_settings_id = policy_employee.id

        # Trigger sync manually since create on policy needs employees assigned to trigger automated calendar sync
        policy_department._sync_to_resource_calendar()
        policy_employee._sync_to_resource_calendar()

        # Run resolution tests
        resolved_factory = self.env['cn.attendance.settings'].get_settings_for_employee(emp_factory)
        self.assertEqual(resolved_factory.id, policy_department.id)
        self.assertEqual(resolved_factory.standard_check_in, 8.0)

        resolved_office = self.env['cn.attendance.settings'].get_settings_for_employee(emp_office)
        self.assertEqual(resolved_office.id, policy_company.id)
        self.assertEqual(resolved_office.standard_check_in, 9.0)

        resolved_executive = self.env['cn.attendance.settings'].get_settings_for_employee(emp_executive)
        self.assertEqual(resolved_executive.id, policy_employee.id)
        self.assertEqual(resolved_executive.standard_check_in, 10.0)

        # Assert dedicated calendar syncs
        # 1. Factory Department Calendar should be synced to 8.0 - 17.0
        mon_factory_lines = calendar_dept.attendance_ids.filtered(lambda l: l.dayofweek == '0').sorted(key=lambda l: l.hour_from)
        self.assertEqual(mon_factory_lines[0].hour_from, 8.0)
        self.assertEqual(mon_factory_lines[-1].hour_to, 17.0)

        # 2. Executive Employee Calendar should be synced to 10.0 - 19.0
        mon_exec_lines = calendar_emp.attendance_ids.filtered(lambda l: l.dayofweek == '0').sorted(key=lambda l: l.hour_from)
        self.assertEqual(mon_exec_lines[0].hour_from, 10.0)
        self.assertEqual(mon_exec_lines[-1].hour_to, 19.0)

    def test_chinese_public_holidays_and_swapped_workdays(self):
        """Validate quick setting for Chinese public holidays and rostered swapped workdays"""
        # Setup calendar and link to company default
        calendar = self.env.company.resource_calendar_id
        if not calendar:
            calendar = self.env['resource.calendar'].create({
                'name': 'Public Holiday Standard Calendar',
                'company_id': self.env.company.id,
            })
            self.env.company.resource_calendar_id = calendar.id
            
        calendar.attendance_ids.unlink()
        self.env.flush_all()
        self.env.invalidate_all()

        employee = self.env['hr.employee'].create({
            'name': 'Holiday Worker',
            'resource_calendar_id': calendar.id,
        })

        # Create settings
        settings = self.env['cn.attendance.settings'].create({
            'name': 'Holiday Settings',
            'company_id': self.env.company.id,
            'standard_check_in': 9.0,
            'standard_check_out': 18.0,
        })
        employee.attendance_settings_id = settings.id

        # 1. Add Holiday on a Monday (2024-03-04) -> Should NOT expect work, and should sync as a Leave interval!
        self.env['cn.attendance.holiday.rule'].create({
            'name': 'National Day Holiday Rest',
            'holiday_type': 'holiday',
            'date': '2024-03-04',
            'settings_id': settings.id,
        })

        # 2. Add Swapped Workday on a Saturday (2024-03-02) -> Should expect work on weekend!
        self.env['cn.attendance.holiday.rule'].create({
            'name': 'National Day Swapped Workday',
            'holiday_type': 'workday',
            'date': '2024-03-02',
            'settings_id': settings.id,
        })

        # 3. Add Expected Workday on a Monday (2024-03-11) -> Expected to work, no punch -> absent 1.0!
        self.env['cn.attendance.holiday.rule'].create({
            'name': 'Standard Workday Monday',
            'holiday_type': 'workday',
            'date': '2024-03-11',
            'settings_id': settings.id,
        })

        # Assert: Odoo-native calendar leaf is automatically synced for 'holiday' type
        leaf = self.env['resource.calendar.leaves'].search([
            ('calendar_id', '=', calendar.id),
            ('name', '=', 'National Day Holiday Rest'),
        ], limit=1)
        self.assertTrue(leaf, "Holiday should sync directly to Odoo resource calendar leaves")

        # Now simulate actual punch cards
        # 1. Saturday 2024-03-02: Expected to work!
        # If they check-in late at 09:25 -> should count as 25 late minutes!
        self.env['hr.attendance'].create({
            'employee_id': employee.id,
            'check_in': '2024-03-02 01:25:00', # UTC (09:25 Beijing time)
            'check_out': '2024-03-02 10:00:00', # UTC (18:00 Beijing time)
        })

        # 2. Monday 2024-03-04: Registered holiday -> Not expected to work!
        # No attendance punch on this day should NOT trigger absent penalties!

        # 3. Monday 2024-03-11: Standard expected weekday.
        # No attendance punch on this day and no leave -> Should count as 1.0 day absent!

        # Compute Monthly Summary
        self.env.flush_all()
        self.env.invalidate_all()
        summary = self.env['cn.attendance.summary'].create({
            'employee_id': employee.id,
            'period': '2024-03',
        })
        summary.action_calculate_summary()

        # Assertions:
        # - late_minutes should be 25 (from the swapped weekend workday punch)
        self.assertEqual(summary.late_minutes, 25)
        # - absent_days should be 1.0 (from 2024-03-11 standard expected weekday with no punch.
        #   2024-03-04 holiday must be skipped, avoiding incorrect absence penalties!)
        self.assertEqual(summary.absent_days, 1.0)

    def test_flexible_calendar_and_overtime(self):
        """Validate that 12-hour shifts and 7-day schedules dynamically calculate standard hours vs multi-bracket overtime"""
        # Create a 7-day working calendar (every day is scheduled)
        calendar_7day = self.env['resource.calendar'].create({
            'name': '7-Day Continuous Schedule',
            'company_id': self.env.company.id,
        })
        calendar_7day.attendance_ids.unlink()
        for day in ['0', '1', '2', '3', '4', '5', '6']: # Mon to Sun
            self.env['resource.calendar.attendance'].create({
                'name': f"Shift {day}",
                'dayofweek': day,
                'hour_from': 8.0,
                'hour_to': 20.0, # 12-hour shift
                'calendar_id': calendar_7day.id,
            })

        # Create an employee with this 7-day calendar
        employee = self.env['hr.employee'].create({
            'name': 'Factory 7/12 Worker',
            'resource_calendar_id': calendar_7day.id,
        })

        # Create 8-hour standard limit settings for this company default
        settings = self.env['cn.attendance.settings'].create({
            'name': '8-Hour Limit Policy',
            'company_id': self.env.company.id,
            'standard_check_in': 8.0,
            'standard_check_out': 20.0,
            'standard_daily_hours': 8.0, # 8 hours standard, extra 4 hours are overtime!
        })

        # 1. Standard expected workday (Monday 2024-03-04): worked 12 hours (08:00 to 20:00)
        # 12 - 8 = 4.0 hours should be Weekday Overtime!
        self.env['hr.attendance'].create({
            'employee_id': employee.id,
            'check_in': '2024-03-04 00:00:00', # UTC (08:00 Beijing time)
            'check_out': '2024-03-04 12:00:00', # UTC (20:00 Beijing time)
        })

        # 2. Add Holiday on Wednesday 2024-03-06 (放假) but worker actually worked 12 hours!
        # This should count as Holiday Overtime!
        self.env['cn.attendance.holiday.rule'].create({
            'name': 'Special Day Rest',
            'holiday_type': 'holiday',
            'date': '2024-03-06',
            'settings_id': settings.id,
        })
        self.env['hr.attendance'].create({
            'employee_id': employee.id,
            'check_in': '2024-03-06 00:00:00', # UTC (08:00 Beijing time)
            'check_out': '2024-03-06 12:00:00', # UTC (20:00 Beijing time)
        })

        # Calculate summary
        summary = self.env['cn.attendance.summary'].create({
            'employee_id': employee.id,
            'period': '2024-03',
        })
        summary.action_calculate_summary()

        # Assertions:
        # - Weekday Overtime should be 4.0 hours (from Mon 2024-03-04: 12 - 8 = 4)
        self.assertEqual(summary.overtime_weekday_hours, 4.0)
        # - Holiday Overtime should be 12.0 hours (from Wed 2024-03-06)
        self.assertEqual(summary.overtime_holiday_hours, 12.0)

    def test_attendance_calendar_adjustments(self):
        """Validate that HR batch calendar adjustments (swapping workdays, temporary leaves, scheduled OT) work atomically across multiple settings/calendars"""
        # Setup basic employees and settings
        settings = self.env['cn.attendance.settings'].create({
            'name': 'Company Scope Settings',
            'company_id': self.env.company.id,
            'standard_check_in': 9.0,
            'standard_check_out': 18.0,
        })
        employee = self.env['hr.employee'].create({
            'name': 'Adjustment Test Worker',
            'attendance_settings_id': settings.id,
        })
        
        # Create a second settings group (e.g., Factory) to test multi-settings broadcast!
        factory_settings = self.env['cn.attendance.settings'].create({
            'name': 'Factory Scope Settings',
            'company_id': self.env.company.id,
            'standard_check_in': 8.0,
            'standard_check_out': 17.0,
        })
        # Create a dedicated calendar and employee to prevent overlapping rule sync conflicts on the company calendar
        calendar_factory = self.env['resource.calendar'].create({
            'name': 'Factory Schedule',
            'company_id': self.env.company.id,
        })
        calendar_factory.attendance_ids.unlink()
        for day in ['0', '1', '2', '3', '4']:
            self.env['resource.calendar.attendance'].create({
                'name': f"Day {day}",
                'dayofweek': day,
                'hour_from': 8.0,
                'hour_to': 17.0,
                'calendar_id': calendar_factory.id,
            })
        employee_factory = self.env['hr.employee'].create({
            'name': 'Factory Test Worker',
            'attendance_settings_id': factory_settings.id,
            'resource_calendar_id': calendar_factory.id,
        })

        # 1. Test 'swap_workday' adjustment (调休) across BOTH settings groups!
        adj_swap = self.env['cn.attendance.adjustment'].create({
            'name': 'Mid-Autumn Sunday Swap Workday',
            'settings_ids': [(6, 0, [settings.id, factory_settings.id])],
            'adjustment_type': 'swap_workday',
            'date': '2024-03-03',
        })
        self.assertEqual(adj_swap.state, 'draft')
        adj_swap.action_execute_adjustment()
        self.assertEqual(adj_swap.state, 'executed')

        # Assert: Automatic creation of 'workday' type Holiday Rule on BOTH settings!
        rule1 = self.env['cn.attendance.holiday.rule'].search([
            ('settings_id', '=', settings.id),
            ('date', '=', '2024-03-03'),
            ('holiday_type', '=', 'workday')
        ], limit=1)
        self.assertTrue(rule1, "Executing swap_workday adjustment should create a workday rule on group 1")

        rule2 = self.env['cn.attendance.holiday.rule'].search([
            ('settings_id', '=', factory_settings.id),
            ('date', '=', '2024-03-03'),
            ('holiday_type', '=', 'workday')
        ], limit=1)
        self.assertTrue(rule2, "Executing swap_workday adjustment should create a workday rule on group 2")

        # 2. Test 'temp_leave' adjustment (临时放假)
        # HR grant Monday 2024-03-04 temporary holiday across BOTH groups
        adj_leave = self.env['cn.attendance.adjustment'].create({
            'name': 'Mid-Autumn Monday Temporary Rest',
            'settings_ids': [(6, 0, [settings.id, factory_settings.id])],
            'adjustment_type': 'temp_leave',
            'date': '2024-03-04',
        })
        adj_leave.action_execute_adjustment()

        # Assert: Automatic creation of 'holiday' type Holiday Rule on both
        rule_holiday1 = self.env['cn.attendance.holiday.rule'].search([
            ('settings_id', '=', settings.id),
            ('date', '=', '2024-03-04'),
            ('holiday_type', '=', 'holiday')
        ], limit=1)
        self.assertTrue(rule_holiday1, "Executing temp_leave adjustment should create holiday rule on group 1")

        rule_holiday2 = self.env['cn.attendance.holiday.rule'].search([
            ('settings_id', '=', factory_settings.id),
            ('date', '=', '2024-03-04'),
            ('holiday_type', '=', 'holiday')
        ], limit=1)
        self.assertTrue(rule_holiday2, "Executing temp_leave adjustment should create holiday rule on group 2")

        # 3. Test 'scheduled_ot' adjustment (安排周末加班)
        # HR schedules mandatory overtime on Sunday 2024-03-10
        adj_ot = self.env['cn.attendance.adjustment'].create({
            'name': 'Mid-Autumn Mandated Overtime',
            'settings_ids': [(6, 0, [settings.id, factory_settings.id])],
            'adjustment_type': 'scheduled_ot',
            'date': '2024-03-10',
        })
        adj_ot.action_execute_adjustment()

        # Simulate punches: worker worked 8 hours on Sunday 2024-03-10
        self.env['hr.attendance'].create({
            'employee_id': employee.id,
            'check_in': '2024-03-10 01:00:00', # UTC (09:00 Beijing time)
            'check_out': '2024-03-10 09:00:00', # UTC (17:00 Beijing time) -> 8.0 hours worked!
        })

        # Calculate monthly summary
        summary = self.env['cn.attendance.summary'].create({
            'employee_id': employee.id,
            'period': '2024-03',
        })
        summary.action_calculate_summary()

        # Assertions:
        # - Sunday 2024-03-10 was a scheduled overtime day. All 8.0 hours worked must count as Weekend Overtime!
        self.assertEqual(summary.overtime_weekend_hours, 8.0)
        # - Since Monday 2024-03-04 was a temp holiday, no attendance punch on this day should NOT trigger absence penalty.

    def test_hierarchical_attendance_inheritance(self):
        """Validate recursive policy climbing, department-level inheritance, sub-department scoping, and personal employee override"""
        # 1. Setup base policies
        global_policy = self.env['cn.attendance.settings'].create({
            'name': 'Global Parent Policy',
            'standard_check_in': 9.0,
            'standard_check_out': 18.0,
        })
        factory_policy = self.env['cn.attendance.settings'].create({
            'name': 'Factory Custom Policy',
            'standard_check_in': 8.0,
            'standard_check_out': 17.0,
        })

        # 2. Setup HR Department hierarchy
        parent_dept = self.env['hr.department'].create({
            'name': 'Manufacturing Division',
            'attendance_settings_id': factory_policy.id,
        })
        child_dept = self.env['hr.department'].create({
            'name': 'Assembly Line Section A',
            'parent_id': parent_dept.id, # Sub-department!
        })

        # 3. Setup Employees
        # Worker A: belongs to assembly line. No personal override, no department override. Should climb to parent_dept's policy!
        worker_a = self.env['hr.employee'].create({
            'name': 'Assembly Line Worker A',
            'department_id': child_dept.id,
        })

        # Executive B: belongs to assembly line but has a personal override settings. Should resolve to global_policy!
        exec_b = self.env['hr.employee'].create({
            'name': 'On-Site Inspector B',
            'department_id': child_dept.id,
            'attendance_settings_id': global_policy.id,
        })

        # 4. Resolve Active Policies
        policy_a = self.env['cn.attendance.settings'].get_settings_for_employee(worker_a)
        policy_b = self.env['cn.attendance.settings'].get_settings_for_employee(exec_b)

        # Assertions
        # Worker A inherits from parent department's factory_policy (recursive tree-climbing!)
        self.assertEqual(policy_a.id, factory_policy.id)
        self.assertEqual(policy_a.standard_check_in, 8.0)

        # Executive B bypasses department and resolves directly to global_policy (personal override!)
        self.assertEqual(policy_b.id, global_policy.id)
        self.assertEqual(policy_b.standard_check_in, 9.0)

    def test_minimum_wage_supplement_calculation(self):
        """Verify that falling below minimum wage dynamically generates correct supplement"""
        employee = self.env['hr.employee'].create({'name': 'Low Wage Worker'})
        
        # 1. Create structure with MINIMUM_WAGE_MAKEUP item
        item_basic = self.item_basic
        item_makeup = self.env['cn.salary.item'].create({
            'name': 'Minimum Wage Supplement', 'code': 'MAKEUP', 'item_type': 'variable',
            'python_code': 'result = MINIMUM_WAGE_MAKEUP'
        })
        item_net = self.env['cn.salary.item'].create({
            'name': 'Net Pay', 'code': 'NET', 'item_type': 'fixed',
            'python_code': 'result = BASIC + MAKEUP'
        })
        struct = self.env['cn.salary.structure'].create({
            'name': 'Minimum Wage Guard Structure',
            'item_ids': [(4, item_basic.id), (4, item_makeup.id), (4, item_net.id)],
        })

        # Base wage = 2000.0, below default 2690.0 minimum wage limit
        payslip = self.env['cn.payslip'].create({
            'employee_id': employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 2000.0,
            'local_minimum_wage': 2690.0,
        })
        
        payslip.action_compute_sheet()
        
        makeup_line = payslip.line_ids.filtered(lambda l: l.code == 'MAKEUP')
        # Makeup = 2690 - 2000 = 690.0 RMB
        self.assertEqual(makeup_line.amount, 690.0)
        
        net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
        self.assertEqual(net_line.amount, 2690.0)

    def test_monthly_overtime_36_hour_limit_audit_warning(self):
        """Verify that monthly overtime hours over 36 trigger statutory warning flag"""
        employee = self.env['hr.employee'].create({'name': 'Hardworking Worker'})
        
        # 1. Under limit (20 hours)
        summary_normal = self.env['cn.attendance.summary'].create({
            'employee_id': employee.id,
            'period': '2024-03',
            'overtime_weekday_hours': 10.0,
            'overtime_weekend_hours': 10.0,
        })
        summary_normal._compute_total_overtime()
        self.assertEqual(summary_normal.total_overtime_hours, 20.0)
        self.assertEqual(summary_normal.overtime_status, 'normal')

        # 2. Over limit (40 hours)
        summary_warning = self.env['cn.attendance.summary'].create({
            'employee_id': employee.id,
            'period': '2024-04',
            'overtime_weekday_hours': 20.0,
            'overtime_weekend_hours': 15.0,
            'overtime_holiday_hours': 5.0,
        })
        summary_warning._compute_total_overtime()
        self.assertEqual(summary_warning.total_overtime_hours, 40.0)
        self.assertEqual(summary_warning.overtime_status, 'warning')









