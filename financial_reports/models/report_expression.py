# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountReportExpression(models.Model):
    _inherit = 'account.report.expression'

    name = fields.Char(string='Name', default='Expression')
    engine = fields.Selection(default='custom')
    formula = fields.Char(default='0')

    expression_type = fields.Selection([
        ('account', 'Account balance'),
        ('account_type', 'Account Type balance'),
        ('account_group', 'Account Group balance'),
        ('aggregation', 'Aggregation of other expressions'),
        ('tax_tags', 'Tax Tags balance'),
        ('analytic_account', 'Analytic Account balance'),
        ('analytic_plan', 'Analytic Plan balance'),
        ('formula', 'Custom Formula'),
    ], string='Expression Type', required=True, default='account')

    account_id = fields.Many2one('account.account', string='Account')
    account_type = fields.Selection([
        ('asset_receivable', 'Receivable'),
        ('asset_cash', 'Bank and Cash'),
        ('asset_current', 'Current Assets'),
        ('asset_non_current', 'Non-current Assets'),
        ('asset_prepayments', 'Prepayments'),
        ('asset_fixed', 'Fixed Assets'),
        ('liability_payable', 'Payable'),
        ('liability_credit_card', 'Credit Card'),
        ('liability_current', 'Current Liabilities'),
        ('liability_non_current', 'Non-current Liabilities'),
        ('equity', 'Equity'),
        ('equity_unaffected', 'Current Year Earnings'),
        ('income', 'Income'),
        ('income_other', 'Other Income'),
        ('expense', 'Expense'),
        ('expense_depreciation', 'Depreciation'),
        ('expense_direct_cost', 'Cost of Revenue'),
        ('off_balance', 'Off-Balance Sheet'),
    ], string='Account Type')
    account_group_id = fields.Many2one('account.group', string='Account Group')
    tax_tag_ids = fields.Many2many('account.account.tag', string='Tax Tags')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    analytic_plan_id = fields.Many2one('account.analytic.plan', string='Analytic Plan')
    sub_expression_ids = fields.Many2many(
        'account.report.expression',
        'account_report_expression_sub_rel',
        'parent_id', 'child_id',
        string='Sub Expressions'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' in vals and 'label' not in vals:
                vals['label'] = vals['name']
            elif 'label' in vals and 'name' not in vals:
                vals['name'] = vals['label']
            if 'engine' not in vals:
                vals['engine'] = 'custom'
            if 'formula' not in vals:
                vals['formula'] = '0'
        return super(AccountReportExpression, self).create(vals_list)

    def write(self, vals):
        if 'name' in vals and 'label' not in vals:
            vals['label'] = vals['name']
        elif 'label' in vals and 'name' not in vals:
            vals['name'] = vals['label']
        return super(AccountReportExpression, self).write(vals)
