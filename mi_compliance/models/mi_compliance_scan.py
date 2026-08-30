# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    hire_date = fields.Date(string='Hire Date', default=fields.Date.today)

class MiComplianceScan(models.Model):
    _name = 'mi.compliance.scan'
    _description = 'Compliance Scan'

    name = fields.Char(readonly=True, default='New')
    scan_date = fields.Date(default=fields.Date.today, required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    risk_line_ids = fields.One2many('mi.compliance.risk.line', 'scan_id', string='Risks', cascade='delete')
    total_penalty_estimate = fields.Float(compute='_compute_totals', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('mi.compliance.scan') or 'SCAN/NEW'
        return super(MiComplianceScan, self).create(vals_list)

    @api.depends('risk_line_ids.amount_penalty')
    def _compute_totals(self):
        for rec in self:
            rec.total_penalty_estimate = sum(rec.risk_line_ids.mapped('amount_penalty'))

    def _calculate_penalties(self, risk_line, overdue_days):
        risk_line.amount_penalty = round(risk_line.amount_principal * 0.0005 * overdue_days, 2)

    def action_execute_scan(self):
        self.ensure_one()
        self.risk_line_ids.unlink()

        employees = self.env['hr.employee'].search([])

        for emp in employees:
            # 1. Missing Enrollment Risk
            enrollments = self.env['mi.enrollment'].search([
                ('employee_id', '=', emp.id),
                ('state', 'in', ['pending', 'enrolled'])
            ])
            if not enrollments:
                if emp.hire_date and emp.hire_date < self.scan_date:
                    months_overdue = 3
                    state_bj = self.env['res.country.state'].search([('code', '=', 'BJ')], limit=1)
                    policy = self.env['mi.policy'].search([
                        ('region_id', '=', state_bj.id),
                        ('date_start', '<=', '2023-12-31'),
                        ('state', '=', 'active')
                    ], order='date_start desc', limit=1)
                    
                    if policy:
                        monthly_cost = 0.0
                        for line in policy.line_ids:
                            monthly_cost += line.base_min * ((line.rate_employer + line.rate_employee) / 100.0)
                        
                        principal = monthly_cost * months_overdue
                        
                        risk_line = self.env['mi.compliance.risk.line'].create({
                            'scan_id': self.id,
                            'employee_id': emp.id,
                            'risk_type': 'missing',
                            'months_overdue': months_overdue,
                            'amount_principal': principal,
                        })
                        overdue_days = (fields.Date.from_string(self.scan_date) - date(2024, 1, 6)).days
                        self._calculate_penalties(risk_line, overdue_days)

            # 2. Low Base Risk
            for enroll in enrollments:
                policy = enroll.policy_id
                if policy:
                    # Map out customized bases from subline line_ids
                    custom_bases = {line.insurance_type_group: line.base_amount for line in enroll.line_ids}
                    
                    for line in policy.line_ids:
                        # Determine applicable base following fallback rules:
                        applicable_base = enroll.base_amount
                        
                        if line.insurance_type == 'pension' and 'pension' in custom_bases:
                            applicable_base = custom_bases['pension']
                        elif line.insurance_type == 'medical' and 'medical' in custom_bases:
                            applicable_base = custom_bases['medical']
                        elif line.insurance_type in ['housing_fund', 'supp_housing_fund'] and 'housing_fund_sep' in custom_bases:
                            applicable_base = custom_bases['housing_fund_sep']
                        elif line.insurance_type in ['pension', 'medical', 'unemployment', 'injury', 'maternity'] and 'social_security' in custom_bases:
                            applicable_base = custom_bases['social_security']
                        elif line.insurance_type in ['housing_fund', 'supp_housing_fund'] and 'housing_fund' in custom_bases:
                            applicable_base = custom_bases['housing_fund']

                        if applicable_base < line.base_min:
                            difference = line.base_min - applicable_base
                            self.env['mi.compliance.risk.line'].create({
                                'scan_id': self.id,
                                'employee_id': emp.id,
                                'risk_type': 'low_base',
                                'base_declared': applicable_base,
                                'base_expected': line.base_min,
                                'amount_principal': difference,
                                'description': _("Base declared (%s) is below required %s policy minimum (%s)") % (applicable_base, line.insurance_type, line.base_min)
                            })

class MiComplianceRiskLine(models.Model):
    _name = 'mi.compliance.risk.line'
    _description = 'Compliance Risk Line'

    scan_id = fields.Many2one('mi.compliance.scan', ondelete='cascade', required=True)
    employee_id = fields.Many2one('hr.employee', required=True)
    risk_type = fields.Selection([
        ('missing', 'Missing Enrollment'),
        ('low_base', 'Low Base amount'),
        ('break_缴', 'Historical Gap')
    ], required=True)
    base_declared = fields.Float()
    base_expected = fields.Float()
    months_overdue = fields.Integer()
    amount_principal = fields.Float()
    amount_penalty = fields.Float()
    description = fields.Text()
