# -*- coding: utf-8 -*-
from odoo import models, fields

class MiApiLog(models.Model):
    _name = 'mi.api.log'
    _description = 'API Transaction Log'

    name = fields.Char(required=True, string="Transaction ID")
    request_data = fields.Text(string="Request Payload")
    response_data = fields.Text(string="Response Payload")
    state = fields.Selection([
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed')
    ], default='pending', required=True, string="State")
    res_model = fields.Char(string="Associated Model")
    res_id = fields.Integer(string="Associated ID")
