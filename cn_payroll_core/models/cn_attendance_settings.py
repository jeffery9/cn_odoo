# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime

class CnAttendanceSettings(models.Model):
    _name = 'cn.attendance.settings'
    _description = 'Chinese Attendance Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, string='Settings Label', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    standard_check_in = fields.Float(string='Standard Check-In', default=9.0, required=True, tracking=True)
    standard_check_out = fields.Float(string='Standard Check-Out', default=18.0, required=True, tracking=True)
    standard_daily_hours = fields.Float(string='Standard Daily Hours', default=8.0, required=True, tracking=True)
    grace_period_late = fields.Integer(string='Late Grace Period (Min)', default=0, required=True, tracking=True)
    missing_checkout_fallback = fields.Selection([
        ('standard', 'Autocomplete Shift'),
        ('absent', 'Count as Absent')
    ], string='Missing Check-out Fallback', default='standard', required=True, tracking=True)
    holiday_rule_ids = fields.One2many('cn.attendance.holiday.rule', 'settings_id', string='Holiday and Swapped Workday Rules')

    @api.model
    def get_settings_for_employee(self, employee):
        """
        Recursively climbs the HR hierarchy tree to locate the active attendance settings.
        Flow: Employee Override -> Department Tree (climbing upwards) -> Company Default -> Database Fallback.
        """
        if not employee:
            return self.browse()

        # 1. Personal Specific Policy Override
        if employee.attendance_settings_id:
            return employee.attendance_settings_id

        # 2. Climb Department tree (recursive)
        dept = employee.department_id
        while dept:
            if dept.attendance_settings_id:
                return dept.attendance_settings_id
            dept = dept.parent_id

        # 3. Company Default
        company_default = self.search([('company_id', '=', employee.company_id.id)], limit=1)
        if company_default:
            return company_default

        # 4. Standard Database Fallback
        return self.search([], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        records = super(CnAttendanceSettings, self).create(vals_list)
        for record in records:
            record._sync_to_resource_calendar()
        return records

    def write(self, vals):
        res = super(CnAttendanceSettings, self).write(vals)
        if any(f in vals for f in ['standard_check_in', 'standard_check_out']):
            for record in self:
                record._sync_to_resource_calendar()
        return res

    def _sync_to_resource_calendar(self):
        self.ensure_one()
        self.env.flush_all()
        self.env.invalidate_all()
        
        # Resolve all scoped employees directly or recursively under assigned departments
        direct_employees = self.env['hr.employee'].search([('attendance_settings_id', '=', self.id)])
        
        departments = self.env['hr.department'].search([('attendance_settings_id', '=', self.id)])
        dept_employees = self.env['hr.employee'].search([('department_id', 'child_of', departments.ids)]) if departments else self.env['hr.employee']
        
        all_employees = direct_employees + dept_employees
        calendars = all_employees.mapped('resource_calendar_id')
        
        # If no explicit assignments, fallback to company calendar
        if not calendars:
            if self.company_id.resource_calendar_id:
                calendars = self.company_id.resource_calendar_id

        if not calendars:
            return

        for calendar in calendars:
            # Adaptive Sync: For Mon to Fri (dayofweek '0' to '4'), adjust standard start/end bounds
            for day in ['0', '1', '2', '3', '4']:
                day_lines = calendar.attendance_ids.filtered(lambda l: l.dayofweek == day)
                if not day_lines:
                    continue

                # Sort lines ascending by hour_from
                sorted_lines = day_lines.sorted(key=lambda l: l.hour_from)
                
                # Set first line's start hour to standard_check_in
                sorted_lines[0].write({'hour_from': self.standard_check_in})
                
                # Set last line's end hour to standard_check_out
                sorted_lines[-1].write({'hour_to': self.standard_check_out})


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    attendance_settings_id = fields.Many2one('cn.attendance.settings', string='Personal Attendance Policy')
    resolved_attendance_settings_id = fields.Many2one(
        'cn.attendance.settings', 
        compute='_compute_resolved_settings', 
        string='Active Attendance Policy', 
        readonly=True
    )

    @api.depends('attendance_settings_id', 'department_id', 'department_id.attendance_settings_id')
    def _compute_resolved_settings(self):
        for employee in self:
            employee.resolved_attendance_settings_id = self.env['cn.attendance.settings'].get_settings_for_employee(employee)


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    attendance_settings_id = fields.Many2one('cn.attendance.settings', string='Department Attendance Policy')


class CnAttendanceHolidayRule(models.Model):
    _name = 'cn.attendance.holiday.rule'
    _description = 'Chinese Attendance Holiday and Swapped Workday Rule'

    name = fields.Char(required=True, string='Holiday/Workday Name')
    holiday_type = fields.Selection([
        ('holiday', 'Public Holiday (放假)'),
        ('workday', 'Swapped Workday (调休上班)')
    ], string='Type', required=True, default='holiday')
    date = fields.Date(string='Date', required=True)
    settings_id = fields.Many2one('cn.attendance.settings', string='Attendance Policy', required=True, ondelete='cascade')

    @api.model_create_multi
    def create(self, vals_list):
        records = super(CnAttendanceHolidayRule, self).create(vals_list)
        for record in records:
            record._sync_to_resource_calendar_leave()
        return records

    def write(self, vals):
        res = super(CnAttendanceHolidayRule, self).write(vals)
        if any(f in vals for f in ['name', 'date', 'holiday_type']):
            for record in self:
                record._sync_to_resource_calendar_leave()
        return res

    def unlink(self):
        # Remove synced leaves before unlinking
        for record in self:
            record._remove_resource_calendar_leave()
        return super(CnAttendanceHolidayRule, self).unlink()

    def _sync_to_resource_calendar_leave(self):
        self.ensure_one()
        self.env.flush_all()
        self.env.invalidate_all()
        if self.holiday_type != 'holiday':
            self._remove_resource_calendar_leave()
            return

        settings = self.settings_id
        
        # Resolve all scoped employees directly or recursively under assigned departments
        direct_employees = self.env['hr.employee'].search([('attendance_settings_id', '=', settings.id)])
        
        departments = self.env['hr.department'].search([('attendance_settings_id', '=', settings.id)])
        dept_employees = self.env['hr.employee'].search([('department_id', 'child_of', departments.ids)]) if departments else self.env['hr.employee']
        
        all_employees = direct_employees + dept_employees
        calendars = all_employees.mapped('resource_calendar_id')
        
        # If no explicit assignments, fallback to company calendar
        if not calendars:
            if settings.company_id.resource_calendar_id:
                calendars = settings.company_id.resource_calendar_id

        for calendar in calendars:
            existing_leave = self.env['resource.calendar.leaves'].search([
                ('calendar_id', '=', calendar.id),
                ('name', '=', self.name),
                ('date_from', '=', fields.Datetime.to_string(datetime.combine(self.date, datetime.min.time()))),
            ], limit=1)
            
            if not existing_leave:
                self.env['resource.calendar.leaves'].create({
                    'name': self.name,
                    'calendar_id': calendar.id,
                    'date_from': datetime.combine(self.date, datetime.min.time()),
                    'date_to': datetime.combine(self.date, datetime.max.time()),
                })

    def _remove_resource_calendar_leave(self):
        self.ensure_one()
        settings = self.settings_id
        
        direct_employees = self.env['hr.employee'].search([('attendance_settings_id', '=', settings.id)])
        
        departments = self.env['hr.department'].search([('attendance_settings_id', '=', settings.id)])
        dept_employees = self.env['hr.employee'].search([('department_id', 'child_of', departments.ids)]) if departments else self.env['hr.employee']
        
        all_employees = direct_employees + dept_employees
        calendars = all_employees.mapped('resource_calendar_id')
        
        if not calendars:
            if settings.company_id.resource_calendar_id:
                calendars = settings.company_id.resource_calendar_id

        if calendars:
            leaves = self.env['resource.calendar.leaves'].search([
                ('calendar_id', 'in', calendars.ids),
                ('name', '=', self.name),
            ])
            leaves.unlink()


class CnAttendanceAdjustment(models.Model):
    _name = 'cn.attendance.adjustment'
    _description = 'Chinese Attendance Calendar Adjustment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, string='Adjustment Name', tracking=True)
    settings_ids = fields.Many2many('cn.attendance.settings', 'cn_attendance_adj_settings_rel', 'adj_id', 'settings_id', string='Attendance Policy Groups', required=True, tracking=True)
    adjustment_type = fields.Selection([
        ('swap_workday', 'Swapped Workday (调休上班)'),
        ('temp_leave', 'Temporary Holiday/Leave (临时放假/休假)'),
        ('scheduled_ot', 'Scheduled Overtime (安排加班)')
    ], string='Adjustment Type', required=True, default='swap_workday', tracking=True)
    date = fields.Date(string='Adjustment Date', required=True, tracking=True)
    start_hour = fields.Float(string='Start Hour (For OT)', default=9.0, tracking=True)
    end_hour = fields.Float(string='End Hour (For OT)', default=18.0, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft (草稿)'),
        ('executed', 'Executed (已执行)'),
        ('cancelled', 'Cancelled (已取消)')
    ], string='Status', default='draft', tracking=True)

    def action_execute_adjustment(self):
        for record in self:
            if record.state != 'draft':
                continue
            
            # Atomic actions based on adjustment type applied to all scoped settings policy groups
            for settings in record.settings_ids:
                if record.adjustment_type == 'swap_workday':
                    # Create corresponding workday rule
                    self.env['cn.attendance.holiday.rule'].create({
                        'name': record.name,
                        'holiday_type': 'workday',
                        'date': record.date,
                        'settings_id': settings.id,
                    })
                elif record.adjustment_type == 'temp_leave':
                    # Create corresponding holiday rule
                    self.env['cn.attendance.holiday.rule'].create({
                        'name': record.name,
                        'holiday_type': 'holiday',
                        'date': record.date,
                        'settings_id': settings.id,
                    })
                elif record.adjustment_type == 'scheduled_ot':
                    # Custom scheduled overtime dates will be read dynamically by summary engine!
                    pass

            record.state = 'executed'
            record.message_post(body=f"Adjustment '{record.name}' executed successfully. Applied to {len(record.settings_ids)} groups on Target Date: {record.date}.")

    def action_cancel_adjustment(self):
        for record in self:
            if record.state != 'executed':
                continue
            
            # Remove associated holiday rules for all scoped settings policy groups
            rules = self.env['cn.attendance.holiday.rule'].search([
                ('settings_id', 'in', record.settings_ids.ids),
                ('date', '=', record.date),
                ('name', '=', record.name)
            ])
            rules.unlink()
            
            record.state = 'cancelled'
            record.message_post(body=f"Adjustment '{record.name}' cancelled and associated rules unlinked across all scoped groups.")
