# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _
from odoo.addons.account.models.chart_template import template

class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('cn_npo')
    def _get_cn_npo_template_data(self):
        return {
            'name': _('Non-Profit Organization (民间非营利组织)'),
            'parent': 'cn',
        }
