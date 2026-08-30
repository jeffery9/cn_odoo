# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, timedelta
import pytz

class CnAttendanceSummary(models.Model):
    _name = 'cn.attendance.summary'
    _description = 'Monthly Attendance Summary'

    employee_id = fields.Many2one('hr.employee', required=True)
    period = fields.Char(required=True, help="Format: YYYY-MM")
    late_minutes = fields.Integer(string='Late Minutes', default=0)
    personal_leave_days = fields.Float(string='Personal Leave Days', default=0.0)
    sick_leave_days = fields.Float(string='Sick Leave Days', default=0.0)
    absent_days = fields.Float(string='Absent Days', default=0.0)

    # Chinese Labor Law Overtime Metrics (工作日平时、周末及法定节假日加班)
    overtime_weekday_hours = fields.Float(string='Weekday Overtime Hours (平时加班)', default=0.0)
    overtime_weekend_hours = fields.Float(string='Weekend Overtime Hours (周末加班)', default=0.0)
    overtime_holiday_hours = fields.Float(string='Holiday Overtime Hours (节日加班)', default=0.0)

    overtime_status = fields.Selection([
        ('normal', 'Normal'),
        ('warning', 'Exceeds Statutory 36-Hour Limit')
    ], default='normal', string='Statutory Overtime Compliance')

    total_overtime_hours = fields.Float(compute='_compute_total_overtime', string='Total Overtime Hours', store=True)

    @api.depends('overtime_weekday_hours', 'overtime_weekend_hours', 'overtime_holiday_hours')
    def _compute_total_overtime(self):
        for rec in self:
            rec.total_overtime_hours = (
                rec.overtime_weekday_hours + rec.overtime_weekend_hours + rec.overtime_holiday_hours
            )
            if rec.total_overtime_hours > 36.0:
                rec.overtime_status = 'warning'
            else:
                rec.overtime_status = 'normal'

    _sql_constraints = [
        ('emp_period_unique', 'unique(employee_id, period)', 'Employee summary already exists for this period!')
    ]

    def action_calculate_summary(self):
        self.ensure_one()
        # Parse period dates
        year, month = map(int, self.period.split('-'))
        tz_name = self.env.user.tz or 'Asia/Shanghai'
        tz = pytz.timezone(tz_name)

        # Local start/end dates
        start_dt = tz.localize(datetime(year, month, 1, 0, 0, 0))
        if month == 12:
            end_dt = tz.localize(datetime(year + 1, 1, 1, 0, 0, 0))
        else:
            end_dt = tz.localize(datetime(year, month + 1, 1, 0, 0, 0))

        # UTC conversion for database queries
        start_utc = start_dt.astimezone(pytz.utc).replace(tzinfo=None)
        end_utc = end_dt.astimezone(pytz.utc).replace(tzinfo=None)

        # Fetch active cohort-specific settings using resolution helper
        settings = self.env['cn.attendance.settings'].get_settings_for_employee(self.employee_id)

        std_in_hour = settings.standard_check_in if settings else 9.0
        std_out_hour = settings.standard_check_out if settings else 18.0
        grace_period = settings.grace_period_late if settings else 0
        fallback_policy = settings.missing_checkout_fallback if settings else 'standard'
        standard_daily_hours = settings.standard_daily_hours if settings else 8.0

        # Fetch active working calendar for the employee
        calendar = self.employee_id.resource_calendar_id or self.employee_id.company_id.resource_calendar_id

        # Fetch holiday and workday exceptions
        holiday_dates = settings.holiday_rule_ids.filtered(lambda r: r.holiday_type == 'holiday').mapped('date') if settings else []
        workday_dates = settings.holiday_rule_ids.filtered(lambda r: r.holiday_type == 'workday').mapped('date') if settings else []

        # Fetch active scheduled overtime adjustments across all applied groups
        adjustments = self.env['cn.attendance.adjustment'].search([
            ('settings_ids', 'in', settings.id),
            ('state', '=', 'executed')
        ]) if settings else self.env['cn.attendance.adjustment']
        scheduled_ot_dates = adjustments.filtered(lambda a: a.adjustment_type == 'scheduled_ot').mapped('date')

        # Generate expected work dates in this period dynamically based on the resource calendar and adjustments!
        expected_dates = []
        curr = start_dt.date()
        while curr < end_dt.date():
            dayofweek = str(curr.weekday())
            is_scheduled = False
            if calendar:
                is_scheduled = bool(calendar.attendance_ids.filtered(lambda l: l.dayofweek == dayofweek))
            
            if curr in holiday_dates:
                pass # Public Holiday (Not expected to work)
            elif curr in workday_dates:
                expected_dates.append(curr) # Rostered Swapped Workday (Always expected to work)
            elif curr in scheduled_ot_dates:
                expected_dates.append(curr) # Mandated Scheduled Overtime Workday (Always expected to work)
            elif is_scheduled:
                expected_dates.append(curr) # Scheduled calendar workday
            curr += timedelta(days=1)

        # Parse actual attendances
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            ('check_in', '>=', start_utc),
            ('check_in', '<', end_utc)
        ])

        # Map actual attendances by local date for rapid lookup
        attendance_by_date = {}
        for att in attendances:
            local_in = pytz.utc.localize(att.check_in).astimezone(tz)
            attendance_by_date[local_in.date()] = att

        # Parse hr.leave (Personal vs. Sick)
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('date_from', '>=', start_utc),
            ('date_from', '<', end_utc)
        ])

        late_sum = 0
        absent_sum = 0.0
        ot_weekday = 0.0
        ot_weekend = 0.0
        ot_holiday = 0.0

        # 1. Evaluate absence for expected work dates with no attendance
        for expected_date in expected_dates:
            att = attendance_by_date.get(expected_date)
            if not att:
                on_leave = False
                for leave in leaves:
                    lf = pytz.utc.localize(leave.date_from).astimezone(tz).date()
                    lt = pytz.utc.localize(leave.date_to).astimezone(tz).date()
                    if lf <= expected_date <= lt:
                        on_leave = True
                        break
                
                if not on_leave:
                    absent_sum += 1.0

        # 2. Evaluate check-ins, late minutes, and multi-bracket overtime hours
        for local_date, att in attendance_by_date.items():
            # Calculate worked hours
            hours_worked = 0.0
            if att.check_out:
                hours_worked = (att.check_out - att.check_in).total_seconds() / 3600.0
            else:
                if fallback_policy == 'absent':
                    absent_sum += 0.5
                else:
                    # Autocomplete missing checkout to standard duration for calculation
                    hours_worked = std_out_hour - std_in_hour

            # Categorize working hours and overtime
            if local_date in holiday_dates:
                # Every single hour worked on a registered public holiday is Holiday Overtime (3.0x standard)
                ot_holiday += hours_worked
            elif local_date in scheduled_ot_dates:
                # Working on scheduled overtime adjustment days counts 100% as Weekend Overtime (2.0x standard)
                ot_weekend += hours_worked
            elif local_date in expected_dates:
                # Working on standard scheduled workdays/swapped workdays
                # Evaluate late minutes
                local_in = pytz.utc.localize(att.check_in).astimezone(tz)
                in_hour = int(std_in_hour)
                in_min = int(round((std_in_hour % 1) * 60))
                standard_in = local_in.replace(hour=in_hour, minute=in_min, second=0, microsecond=0)
                
                if local_in > standard_in:
                    diff_min = int((local_in - standard_in).total_seconds() / 60)
                    if diff_min > grace_period:
                        if diff_min < 240:
                            late_sum += diff_min

                # Hours exceeding standard daily hours count as Weekday Overtime (1.5x standard)
                if hours_worked > standard_daily_hours:
                    ot_weekday += (hours_worked - standard_daily_hours)
            else:
                # Working on standard rest days (weekends) counts as Weekend Overtime (2.0x standard)
                ot_weekend += hours_worked

        self.late_minutes = late_sum
        self.absent_days = absent_sum
        self.overtime_weekday_hours = ot_weekday
        self.overtime_weekend_hours = ot_weekend
        self.overtime_holiday_hours = ot_holiday

        personal = 0.0
        sick = 0.0
        for leave in leaves:
            leave_name = leave.holiday_status_id.name or ''
            if 'sick' in leave_name.lower() or '病假' in leave_name:
                sick += leave.number_of_days
            else:
                personal += leave.number_of_days

        self.personal_leave_days = personal
        self.sick_leave_days = sick
