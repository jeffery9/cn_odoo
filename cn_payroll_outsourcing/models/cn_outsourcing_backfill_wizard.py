# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CnOutsourcingBackfillWizard(models.TransientModel):
    _name = 'cn.outsourcing.backfill.wizard'
    _description = 'Rapid Backfill Onboarding Wizard'

    contract_id = fields.Many2one('cn.outsourcing.contract', required=True, string='Target Contract')
    date_start = fields.Date(required=True, default=fields.Date.today, string='Assignment Start Date')
    attendance_settings_id = fields.Many2one('cn.attendance.settings', string='Target Policy / Calendar')
    worker_raw_list = fields.Text(required=True, string='Worker Details (Name,Barcode - Line by Line)')

    def action_onboard_bulk(self):
        self.ensure_one()
        lines = self.worker_raw_list.strip().split('\n')
        for line in lines:
            if not line:
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 2:
                continue
            name, barcode = parts[0], parts[1]
            
            # Optional columns
            birthday = False
            experience_years = 0
            if len(parts) >= 3 and parts[2]:
                birthday = parts[2]
            if len(parts) >= 4 and parts[3]:
                try:
                    experience_years = int(parts[3])
                except ValueError:
                    pass
            
            # 1. Create Employee
            employee = self.env['hr.employee'].create({
                'name': name,
                'barcode': barcode,
                'birthday': birthday,
                'experience_years': experience_years,
                'attendance_settings_id': self.attendance_settings_id.id if self.attendance_settings_id else False,
            })
            
            # 2. Register Assignment
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': self.contract_id.id,
                'employee_id': employee.id,
                'date_start': self.date_start,
            })
