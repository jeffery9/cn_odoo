# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProductCategory(models.Model):
    _inherit = 'product.category'

    tax_item_id = fields.Many2one('tax.catalog.item', string='Tax Item')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    tax_item_id = fields.Many2one('tax.catalog.item', string='Tax Item')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    tax_item_id = fields.Many2one('tax.catalog.item', string='Tax Item')

    def get_tax_item_id(self):
        for record in self:
            if record.tax_item_id:
                return record.tax_item_id

            elif record.product_tmpl_id.tax_item_id:
                return record.product_tmpl_id.tax_item_id

            else:

                all_parent_categ_ids = self.env['product.category'].search(
                    [('id', 'parent_of', record.categ_id.id)]).filtered(lambda x: x.tax_item_id)

                return all_parent_categ_ids[0].tax_item_id
