# -*- coding: utf-8 -*-
from odoo import models, fields

class CnOutsourcingBlacklist(models.Model):
    _name = 'cn.outsourcing.blacklist'
    _description = 'Enterprise Outsourcing Blacklist'

    name = fields.Char(required=True, string='Worker Name')
    id_card_num = fields.Char(string='ID Card Number')
    barcode = fields.Char(string='Barcode')
    mobile = fields.Char(string='Mobile Phone')
    reason = fields.Text(required=True, string='Reason for Blacklist')
    active = fields.Boolean(default=True, string='Active')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, help="Leave blank for global blacklist across all companies.")
