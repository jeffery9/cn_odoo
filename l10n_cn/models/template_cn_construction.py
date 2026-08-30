# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _
from odoo.addons.account.models.chart_template import template

class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('cn_construction')
    def _get_cn_construction_template_data(self):
        return {
            'name': _('Construction Industry (建筑施工企业)'),
            'parent': 'cn_common',
        }
