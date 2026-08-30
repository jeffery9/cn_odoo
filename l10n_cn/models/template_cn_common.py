# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, api, _
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @api.model
    def _get_chart_template_mapping(self):
        mapping = super()._get_chart_template_mapping()
        mapping.update({
            'cn_npo': {
                'name': _('Non-Profit Organization (民间非营利组织)'),
                'module': 'l10n_cn',
                'parent': 'cn',
                'country_id': 'base.cn',
            },
            'cn_gov': {
                'name': _('Government & Public Institutions (政府会计制度)'),
                'module': 'l10n_cn',
                'parent': 'cn',
                'country_id': 'base.cn',
            },
            'cn_construction': {
                'name': _('Construction Industry (建筑施工企业)'),
                'module': 'l10n_cn',
                'parent': 'cn',
                'country_id': 'base.cn',
            },
            'cn_agri': {
                'name': _('Agriculture (农业企业)'),
                'module': 'l10n_cn',
                'parent': 'cn',
                'country_id': 'base.cn',
            },
            'cn_finance': {
                'name': _('Financial Institutions (金融企业)'),
                'module': 'l10n_cn',
                'parent': 'cn',
                'country_id': 'base.cn',
            },
        })
        return mapping

    @template('cn_common')
    def _get_cn_common_template_data(self):
        return {
            'name': _('Common'),
            'visible': 0,
            'code_digits': 6,
            'property_account_receivable_id': 'l10n_cn_common_112200',
            'property_account_payable_id': 'l10n_cn_common_220200',
            'property_account_expense_categ_id': 'l10n_cn_common_640100',
            'property_account_income_categ_id': 'l10n_cn_common_600100',
        }

    @template('cn_common', 'res.company')
    def _get_cn_common_res_company(self):
        return {
            self.env.company.id: {
                'account_storno': True,
                'anglo_saxon_accounting': True,
                'account_fiscal_country_id': 'base.cn',
                'bank_account_code_prefix': '1002',
                'cash_account_code_prefix': '1001',
                'transfer_account_code_prefix': '1012',
                'account_default_pos_receivable_account_id': 'l10n_cn_common_112400',
                'income_currency_exchange_account_id': 'l10n_cn_common_605100',
                'expense_currency_exchange_account_id': 'l10n_cn_common_671100',
            },
        }
