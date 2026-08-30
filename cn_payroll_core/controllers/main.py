# -*- coding: utf-8 -*-
import datetime
from odoo import http, fields, _
from odoo.http import request

class CnPayrollSyncController(http.Controller):

    @http.route('/api/v1/attendance/sync', type='json', auth='public', methods=['POST'], csrf=False)
    def sync_attendance(self, **kwargs):
        data = request.jsonrequest
        if not data:
            return {'status': 'error', 'message': 'No data provided'}

        emp_id = data.get('emp_id')
        time_str = data.get('time')
        punch_type = data.get('type') # 'check_in' or 'check_out'

        if not emp_id or not time_str or not punch_type:
            return {'status': 'error', 'message': 'Missing parameters'}

        # Find employee by barcode, employee code, or name
        employee = request.env['hr.employee'].sudo().search([
            '|', ('barcode', '=', emp_id), ('name', '=', emp_id)
        ], limit=1)

        if not employee:
            return {'status': 'error', 'message': f"Employee with code/name {emp_id} not found"}

        # Convert time_str to datetime
        try:
            dt = fields.Datetime.to_datetime(time_str)
        except Exception:
            return {'status': 'error', 'message': 'Invalid time format, must be YYYY-MM-DD HH:MM:SS'}

        attendance_obj = request.env['hr.attendance'].sudo()
        if punch_type == 'check_in':
            new_record = attendance_obj.create({
                'employee_id': employee.id,
                'check_in': dt,
            })
            return {'status': 'success', 'message': 'Attendance check_in registered', 'id': new_record.id}
        elif punch_type == 'check_out':
            # Find latest open check_in
            open_attendance = attendance_obj.search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)
            ], order='check_in desc', limit=1)
            
            if open_attendance:
                open_attendance.write({'check_out': dt})
                return {'status': 'success', 'message': 'Attendance check_out updated', 'id': open_attendance.id}
            else:
                # Fallback: create new record with check_in = check_out = dt
                new_record = attendance_obj.create({
                    'employee_id': employee.id,
                    'check_in': dt,
                    'check_out': dt,
                })
                return {'status': 'success', 'message': 'No open check_in found; fallback created', 'id': new_record.id}

        return {'status': 'error', 'message': 'Invalid punch type, must be check_in or check_out'}

    @http.route('/api/v1/leave/sync', type='json', auth='public', methods=['POST'], csrf=False)
    def sync_leave(self, **kwargs):
        data = request.jsonrequest
        if not data:
            return {'status': 'error', 'message': 'No data provided'}

        emp_id = data.get('emp_id')
        date_from_str = data.get('date_from')
        date_to_str = data.get('date_to')
        leave_type_code = data.get('type') # 'personal' or 'sick'

        if not emp_id or not date_from_str or not date_to_str or not leave_type_code:
            return {'status': 'error', 'message': 'Missing parameters'}

        # Find employee
        employee = request.env['hr.employee'].sudo().search([
            '|', ('barcode', '=', emp_id), ('name', '=', emp_id)
        ], limit=1)

        if not employee:
            return {'status': 'error', 'message': f"Employee with code/name {emp_id} not found"}

        # Find or create leave type
        leave_type_name = "Personal Leave" if leave_type_code == 'personal' else "Sick Leave"
        leave_type = request.env['hr.leave.type'].sudo().search([
            ('name', 'ilike', leave_type_name)
        ], limit=1)
        if not leave_type:
            leave_type = request.env['hr.leave.type'].sudo().create({
                'name': leave_type_name,
                'requires_allocation': 'no',
            })

        # Parse datetimes
        try:
            date_from = fields.Datetime.to_datetime(date_from_str)
            date_to = fields.Datetime.to_datetime(date_to_str)
        except Exception:
            return {'status': 'error', 'message': 'Invalid date format, must be YYYY-MM-DD HH:MM:SS'}

        # Create leave record in approved status
        leave = request.env['hr.leave'].sudo().create({
            'employee_id': employee.id,
            'holiday_status_id': leave_type.id,
            'date_from': date_from,
            'date_to': date_to,
            'request_date_from': date_from.date(),
            'request_date_to': date_to.date(),
            'number_of_days': (date_to - date_from).days or 1.0,
        })
        # Validate directly to bypass request states and make it directly actionable by payroll
        try:
            leave.action_approve()
            leave.action_validate()
        except Exception:
            leave.state = 'validate'

        return {'status': 'success', 'message': 'Leave registered and approved', 'id': leave.id}
