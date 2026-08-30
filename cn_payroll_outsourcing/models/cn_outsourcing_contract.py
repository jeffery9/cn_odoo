# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CnOutsourcingContract(models.Model):
    _name = 'cn.outsourcing.contract'
    _description = 'Labor Outsourcing Contract'

    name = fields.Char(required=True, string='Contract Name')
    agency_id = fields.Many2one('res.partner', required=True, string='Outsourcing Agency')
    contract_type = fields.Selection([
        ('dispatch', 'Co-employment / Dispatch'),
        ('service_rate', 'Service-Rate / Hourly Billing')
    ], string='Billing Mode', required=True, default='dispatch')
    
    admin_fee_per_head = fields.Float(string='Admin Fee (Per Head/Month)', default=0.0)
    hourly_rate = fields.Float(string='Hourly Billing Rate', default=0.0)
    vat_rate = fields.Float(string='VAT Rate', default=0.06)
    
    employee_ids = fields.Many2many('hr.employee', string='Assigned Workers')

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    # Entry Requirements
    age_min = fields.Integer(default=18, string='Min Age Required')
    age_max = fields.Integer(default=60, string='Max Age Allowed')
    required_experience_years = fields.Integer(default=0, string='Min Experience Years')
    required_skills = fields.Text(string='Required Skills')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    experience_years = fields.Integer(default=0, string='Experience Years')
    skills_description = fields.Text(string='Skills Description')
    is_disabled = fields.Boolean(default=False, string='Has Disability Certification')


class CnAttendanceSummaryInherit(models.Model):
    _inherit = 'cn.attendance.summary'

    total_work_hours = fields.Float(string='Total Billing Work Hours', default=160.0)
