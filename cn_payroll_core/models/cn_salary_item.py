# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class CnSalaryItem(models.Model):
    _name = 'cn.salary.item'
    _description = 'Salary Item'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    item_type = fields.Selection([
        ('fixed', 'Fixed Salary'),
        ('variable', 'Variable/Bonus'),
        ('deduction', 'Deduction'),
        ('exempt', 'Tax Exempt')
    ], default='fixed', required=True)
    is_taxable = fields.Boolean(default=True)
    python_code = fields.Text(string='Computation Python Code')

    # Accounting Integration Mappings
    debit_account_id = fields.Many2one('account.account', string='Debit Account')
    credit_account_id = fields.Many2one('account.account', string='Credit Account')
    journal_id = fields.Many2one('account.journal', string='Accounting Journal')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Salary item code must be unique!')
    ]
