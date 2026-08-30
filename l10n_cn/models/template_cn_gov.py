# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _
from odoo.addons.account.models.chart_template import template

class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('cn_gov')
    def _get_cn_gov_template_data(self):
        return {
            'name': _('Government & Public Institutions (政府会计制度)'),
            'parent': 'cn',
        }
