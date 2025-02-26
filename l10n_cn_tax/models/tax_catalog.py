# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TaxCAtalogCAtegory(models.Model):
    _name = 'tax.catalog.category'
    _description = 'Tax Catalog Category'
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    # Hierarchy and sequence
    parent_id = fields.Many2one(
        "tax.catalog.category", string="Parent Category", tracking=True,
        ondelete="cascade")
    # used to speed-up hierarchy operators such as child_of/parent_of
    # see '_parent_store' implementation in the ORM for details
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many(
        "tax.catalog.category", "parent_id", string="Child Category",
        copy=True)

    code = fields.Char('Code')

    name = fields.Char('Name', index='trigram', required=True)
    complete_name = fields.Char(
        'Complete Name', compute='_compute_complete_name', recursive=True,
        store=True)

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = '%s / %s' % (category.parent_id.complete_name, category.name)
            else:
                category.complete_name = category.name

class TaxCatalogItem(models.Model):
    _name = 'tax.catalog.item'
    _description = 'Tax Catalog Item'

    code = fields.Char('code')
    name = fields.Char('name')
    description = fields.Char('description')
    rate = fields.Float('rate')

    categ_id = fields.Many2one(
        'tax.catalog.category', string='Category')
