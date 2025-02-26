# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self, **optional_values):
        """Prepare the values to create the new invoice line for a sales order line.

        :param optional_values: any parameter that should be added to the returned invoice line
        :rtype: dict
        """
        self.ensure_one()

        res = super(SaleOrderLine, self)._prepare_invoice_line(
            **optional_values)

        tax_item_id = self.product_id.get_tax_item_id()

        res.update(
            {
                'tax_item_id': tax_item_id.id
            }
        )
        return res
