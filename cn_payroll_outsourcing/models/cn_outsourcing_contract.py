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

    contract_term_months = fields.Integer(string="Contract Term (Months)", default=0)
    probation_term_months = fields.Integer(string="Probation Term (Months)", default=0)
    wage_regular = fields.Float(string="Regular Wage", default=0.0)
    wage_probation = fields.Float(string="Probation Wage", default=0.0)

    female_protection_state = fields.Selection([
        ('none', 'None'),
        ('pregnancy', 'Pregnancy (孕期)'),
        ('maternity', 'Maternity Leave (产期)'),
        ('lactation', 'Lactation / Breastfeeding (哺乳期)')
    ], default='none', string="Female Special Protection State")

    @api.constrains('contract_term_months', 'probation_term_months', 'wage_regular', 'wage_probation')
    def _check_probation_compliance(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            if rec.probation_term_months <= 0:
                continue

            t_months = rec.contract_term_months
            p_months = rec.probation_term_months
            
            if t_months < 3:
                raise ValidationError(
                    f"Compliance Error: Contract of employee {rec.name} is shorter than 3 months. "
                    f"Under Article 19 of PRC Labor Contract Law, probation period is NOT allowed for terms under 3 months."
                )
            elif t_months >= 3 and t_months < 12:
                if p_months > 1:
                    raise ValidationError(
                        f"Compliance Error: Employee {rec.name} has a contract term of {t_months} months. "
                        f"Under PRC Law, probation period cannot exceed 1 month."
                    )
            elif t_months >= 12 and t_months < 36:
                if p_months > 2:
                    raise ValidationError(
                        f"Compliance Error: Employee {rec.name} has a contract term of {t_months} months. "
                        f"Under PRC Law, probation period cannot exceed 2 months."
                    )
            else: # >= 36 months
                if p_months > 6:
                    raise ValidationError(
                        f"Compliance Error: Employee {rec.name} has a contract term of {t_months} months. "
                        f"Under PRC Law, probation period cannot exceed 6 months."
                    )

            if rec.wage_regular > 0.0:
                min_probation_wage = rec.wage_regular * 0.8
                if rec.wage_probation < min_probation_wage:
                    raise ValidationError(
                        f"Compliance Error: Employee {rec.name} probation wage ({rec.wage_probation} RMB) "
                        f"is lower than 80% of trans-regular wage ({rec.wage_regular} RMB). "
                        f"This violates Article 20 of PRC Labor Contract Law."
                    )

    def write(self, vals):
        if 'active' in vals and not vals['active']:
            from odoo.exceptions import ValidationError
            for rec in self:
                if rec.female_protection_state and rec.female_protection_state != 'none':
                    raise ValidationError(
                        f"Compliance Lock: Employee {rec.name} is currently under special "
                        f"legal protection ({rec.get_female_protection_label()}). "
                        f"Under Article 42 of the PRC Labor Contract Law, "
                        f"dismissing, deactivating, or archiving her contract is strictly prohibited!"
                    )
        return super(HrEmployee, self).write(vals)

    def get_female_protection_label(self):
        state_labels = {
            'pregnancy': 'Pregnancy (孕期)',
            'maternity': 'Maternity (产期)',
            'lactation': 'Lactation (哺乳期)',
        }
        return state_labels.get(self.female_protection_state, 'Unknown')


class CnAttendanceSummaryInherit(models.Model):
    _inherit = 'cn.attendance.summary'

    total_work_hours = fields.Float(string='Total Billing Work Hours', default=160.0)
