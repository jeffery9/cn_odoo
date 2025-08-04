# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class AccountAccount(models.Model):
    _inherit = 'account.account'

    cash_flow_category_ids = fields.Many2many(
        'account.cashflow.category',
        string='Cash Flow Categories',
        help="Link this account to one or more cash flow categories."
    )
