# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class MiPolicy(models.Model):
    _name = 'mi.policy'
    _description = 'Medical Insurance Policy'

    name = fields.Char(required=True)
    region_id = fields.Many2one('res.country.state', required=True, string='Region/City')
    date_start = fields.Date(required=True, default=fields.Date.today)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired')
    ], default='draft', required=True)
    line_ids = fields.One2many('mi.policy.line', 'policy_id', string='Lines')

    _sql_constraints = [
        ('region_date_unique', 'unique(region_id, date_start)', 'A policy with this start date already exists for this region!')
    ]

    @api.constrains('date_start', 'region_id')
    def _check_date_chronology(self):
        for rec in self:
            overlapping = self.search([
                ('region_id', '=', rec.region_id.id),
                ('date_start', '>', rec.date_start),
                ('id', '!=', rec.id)
            ])
            if overlapping:
                raise ValidationError(_("The policy's start date cannot predate any existing rules for this region."))

class MiPolicyLine(models.Model):
    _name = 'mi.policy.line'
    _description = 'Medical Insurance Policy Line'

    policy_id = fields.Many2one('mi.policy', ondelete='cascade', required=True)
    insurance_type = fields.Selection([
        ('pension', 'Pension (养老保险)'),
        ('medical', 'Medical Insurance (医疗保险)'),
        ('unemployment', 'Unemployment (失业保险)'),
        ('injury', 'Injury (工伤保险)'),
        ('maternity', 'Maternity (生育保险)'),
        ('housing_fund', 'Housing Provident Fund (住房公积金)'),
        ('supp_housing_fund', 'Supplementary Housing Fund (补充公积金)'),
        ('supp_medical', 'Supplementary Medical (补充医疗)'),
        ('care', 'Long-term Care (长期护理险)')
    ], default='medical', required=True)
    base_min = fields.Float(required=True)
    base_max = fields.Float(required=True)
    rate_employer = fields.Float(required=True)
    rate_employee = fields.Float(required=True)
