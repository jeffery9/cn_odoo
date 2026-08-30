# -*- coding: utf-8 -*-
from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    structure_id = fields.Many2one(
        'cn.salary.structure', 
        string='Default Salary Structure', 
        help='Default salary structure used for automated payroll calculation.'
    )
