# -*- coding: utf-8 -*-
from odoo import models, fields

class CnSalaryStructure(models.Model):
    _name = 'cn.salary.structure'
    _description = 'Salary Structure'

    name = fields.Char(required=True)
    item_ids = fields.Many2many('cn.salary.item', string='Salary Items')
