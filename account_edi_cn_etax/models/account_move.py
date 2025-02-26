import re

from collections import defaultdict
from markupsafe import Markup

from odoo import fields, models, api, _, Command
from odoo.exceptions import UserError
from odoo.tools import float_repr, date_utils
from odoo.tools.xml_utils import cleanup_xml_node, find_xml_value

from lxml import etree
import logging

_logger = logging.getLogger()


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_edi_decoder(self, file_data, new=False):
        if file_data['type'] == 'xml' and file_data['xml_tree'].tag == 'EInvoice':
            return self.cn_etax_xml_decoder

        return super()._get_edi_decoder(file_data, new=new)

    def cn_etax_xml_decoder(self, invoice, file_data, new):
        tree = file_data['xml_tree']
        print(tree)
        EInvoiceId = tree.xpath('//EIid')
        EInvoiceTag = tree.xpath('//EInvoiceTag')
        InIssuType = tree.xpath('//InIssuType')
        SellerInformation = tree.xpath('//SellerInformation')
        BuyerInformation = tree.xpath('//BuyerInformation')
        BasicInformation = tree.xpath('//BasicInformation')

        IssuItemInformation = tree.xpath('//IssuItemInformation')
        # print(IssuItemInformation)
        data = []
        for IssuItem in IssuItemInformation:
            # <ItemName>*纸制品*纸箱</ItemName>
            #         <Amount>-2.73</Amount>
            #         <TaxRate>0.13</TaxRate>
            #         <ComTaxAm>-0.35</ComTaxAm>
            d = {}
            for ele in IssuItem.getchildren():
                d.update({
                    ele.tag: ele.text
                })
            data.append(d)

        result = []
        for d in data:
            if float(d['Amount']) > 0:
                result.append(d)
            else:
                to_update = result[-1]
                result[-1].update(
                    {
                        'Amount': str(float(d['Amount'])+float(to_update['Amount'])),
                        'ComTaxAm': str(float(d['ComTaxAm'])+float(to_update['ComTaxAm'])),
                        'TotaltaxIncludedAmount': str(float(d['TotaltaxIncludedAmount'])+float(to_update['TotaltaxIncludedAmount'])),
                    })

        SellerName = SellerInformation[0].find('SellerName').text
        SellerIdNum = SellerInformation[0].find('SellerIdNum').text
        SellerAddr = SellerInformation[0].find('SellerAddr').text
        SellerTelNum = SellerInformation[0].find('SellerTelNum').text

        if invoice.move_type == 'in_invoice':
            parnter_id = self.env['res.partner'].search(
                [('name', '=', SellerName)], limit=1)
            if not parnter_id:
                parnter_id = self.env['res.partner'].create({
                    'name': SellerName,
                    'phone': SellerTelNum,
                    'street': SellerAddr,
                    'vat': SellerIdNum
                })

            invoice.partner_id = parnter_id.id

            inv_lines_val = []

            for line in result:
                item_name = line['ItemName']
                spec = line['SpecMod']
                uint = line['MeaUnits']
                price = line['UnPrice']
                qty = line['Quantity']
                amount = line['Amount']
                rate = line['TaxRate']
                tax_code = line['TaxClassificationCode']

                uom_id = self.env['uom.uom'].search(
                    [('name', '=', uint)], limit=1)
                if not uom_id:
                    uom_id = self.env.ref('uom.product_uom_unit')
                tax_id = self.env['account.tax'].search(
                    [('type_tax_use', '=',  'purchase'), ('amount', '=', float(rate)*100)], limit=1)

                product_id = self.env['product.product'].search(
                    [('name', '=', item_name)], limit=1)
                if not product_id:
                    product_id = self.env['product.product'].create({
                        'name': item_name,
                        'uom_id': uom_id.id

                    })

                inv_lines_val.append(Command.create({
                    'product_id': product_id.id,
                    'name': spec,
                    'quantity': float(qty),
                    'price_unit': float(price),
                    'tax_ids':  tax_id and [Command.set([tax_id.id])] or False,
                }))

            invoice.invoice_line_ids = inv_lines_val

        return self
