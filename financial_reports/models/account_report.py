# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountReport(models.Model):
    _inherit = 'account.report'

    report_type = fields.Selection([
        ('balance_sheet', 'Balance Sheet'),
        ('income_statement', 'Profit and Loss'),
        ('cash_flow', 'Cash Flow Statement'),
    ], string='Report Type', required=True, default='balance_sheet')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
