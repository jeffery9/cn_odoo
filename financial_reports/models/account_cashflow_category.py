# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class AccountCashFlowCategory(models.Model):
    _name = 'account.cashflow.category'
    _description = 'Cash Flow Category'

    name = fields.Char(string='Category Name', required=True)
    code = fields.Char(string='Category Code', required=True)
    activity_type = fields.Selection([
        ('operating', 'Operating Activities'),
        ('investing', 'Investing Activities'),
        ('financing', 'Financing Activities')
    ], string='Activity Type', required=True)
    account_ids = fields.Many2many('account.account', string='Related Accounts')
