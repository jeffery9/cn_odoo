# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class MiEnrollment(models.Model):
    _name = 'mi.enrollment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Medical Insurance Enrollment'

    employee_id = fields.Many2one('hr.employee', required=True, tracking=True)
    policy_id = fields.Many2one('mi.policy', required=True, tracking=True)
    base_amount = fields.Float(required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Declaration'),
        ('enrolled', 'Enrolled'),
        ('terminated', 'Terminated')
    ], default='draft', required=True, tracking=True)
    start_date = fields.Date(required=True, tracking=True, default=fields.Date.today)
    end_date = fields.Date(tracking=True)
    
    amount_employer = fields.Float(compute='_compute_contributions', store=True, tracking=True)
    amount_employee = fields.Float(compute='_compute_contributions', store=True, tracking=True)
    line_ids = fields.One2many('mi.enrollment.line', 'enrollment_id', string='Custom Base Lines')

    @api.depends('base_amount', 'policy_id', 'policy_id.line_ids', 'line_ids', 'line_ids.base_amount', 'line_ids.insurance_type_group')
    def _compute_contributions(self):
        for rec in self:
            emp_total = 0.0
            p_total = 0.0
            if rec.policy_id:
                # Map out customized bases from line_ids
                custom_bases = {line.insurance_type_group: line.base_amount for line in rec.line_ids}
                
                for line in rec.policy_id.line_ids:
                    # Determine the applicable base following fallback rules:
                    # Specific Type Base -> Group Base -> Core Base
                    applicable_base = rec.base_amount
                    
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

                    actual_base = max(line.base_min, min(applicable_base, line.base_max))
                    emp_total += round(actual_base * (line.rate_employer / 100.0), 2)
                    p_total += round(actual_base * (line.rate_employee / 100.0), 2)
            rec.amount_employer = emp_total
            rec.amount_employee = p_total

    @api.constrains('employee_id', 'state')
    def _check_duplicate_active_enrollment(self):
        for rec in self:
            if rec.state in ['pending', 'enrolled']:
                duplicates = self.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', 'in', ['pending', 'enrolled']),
                    ('id', '!=', rec.id)
                ])
                if duplicates:
                    raise ValidationError(_("This employee already has an active or pending enrollment record!"))


class MiEnrollmentLine(models.Model):
    _name = 'mi.enrollment.line'
    _description = 'Employee Multi-Base Insurance Line'

    enrollment_id = fields.Many2one('mi.enrollment', ondelete='cascade', required=True)
    insurance_type_group = fields.Selection([
        ('social_security', 'Social Security Unified Base (社保统一基数)'),
        ('housing_fund', 'Housing Fund Unified Base (公积金统一基数)'),
        ('pension', 'Pension Separate Base (养老单独基数)'),
        ('medical', 'Medical Separate Base (医疗单独基数)'),
        ('housing_fund_sep', 'Housing Fund Separate Base (公积金单独基数)')
    ], required=True, default='social_security')
    base_amount = fields.Float(required=True)

