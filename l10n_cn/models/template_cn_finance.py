# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _
from odoo.addons.account.models.chart_template import template

class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('cn_finance')
    def _get_cn_finance_template_data(self):
        return {
            'name': _('Financial Institutions (金融企业)'),
            'parent': 'cn',
        }
