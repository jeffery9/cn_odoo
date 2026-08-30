# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _
from odoo.addons.account.models.chart_template import template

class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('cn_agri')
    def _get_cn_agri_template_data(self):
        return {
            'name': _('Agriculture (农业企业)'),
            'parent': 'cn_common',
        }
