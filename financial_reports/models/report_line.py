# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountReportLine(models.Model):
    _inherit = 'account.report.line'

    level = fields.Integer(string='Level', default=0)
