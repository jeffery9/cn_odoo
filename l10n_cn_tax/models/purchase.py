# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_account_move_line(self, move=False):

        self.ensure_one()

        res = super(PurchaseOrderLine, self)._prepare_account_move_line(move)

        tax_item_id = self.product_id.get_tax_item_id()

        res.update(
            {
                'tax_item_id': tax_item_id.id
            }
        )

        return res
