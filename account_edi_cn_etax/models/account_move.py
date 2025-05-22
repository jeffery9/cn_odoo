import base64
import re
from werkzeug.urls import url_encode

from collections import defaultdict
from markupsafe import Markup
import addressparser

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
        data = []
        for IssuItem in IssuItemInformation:
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
            parnter_id = self.env['res.partner'].with_context(
                lang='zh_CN').search(
                [('name', '=', SellerName)], limit=1)

            if not parnter_id:
                address_json = self._parse_cn_address([SellerAddr])
                province = address_json.get('province')
                state_id = self.env['res.country.state'].with_context(
                    lang='zh_CN').search([('name', '=', province)], limit=1)

                parnter_id = self.env['res.partner'].with_context(
                    lang='zh_CN').create({
                        'name': SellerName,
                        'phone': SellerTelNum,
                        'state': state_id.id,
                        'city': address_json.get('city'),
                        'street': address_json.get('district'),
                        'street2': address_json.get('detail'),
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

                product_id = self.env['product.product'].with_context(
                    lang='zh_CN').search(
                    [('name', '=', item_name)], limit=1)
                if not product_id:
                    product_id = self.env['product.product'].with_context(
                        lang='zh_CN').create({
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

    def _parse_cn_address(address: list) -> dict:
        result = []
        df = addressparser.transform(address)

        for map_key in zip(df["省"], df["市"], df["区"], df["地名"]):
            place = map_key[3]
            if not isinstance(place, str):
                place = ''
            result.append(
                '\t'.join([map_key[0], map_key[1], map_key[2], place]))

        result = result[0].split('\t')
        return {
            'province': result[0],
            'city': result[1],
            'district': result[2],
            'detail': result[3]
        }

    def export_cn_etax_to_csv_attachment(self):  
        """导出中国电子发票数据为CSV并存储为附件"""  
        self.ensure_one()  
        
        if self.move_type != 'out_invoice':  
            raise UserError(_("只有销售发票可以导出到CSV"))  
        
        # 准备CSV表头和数据  
        header = ["开票日期", "购方名称", "购方税号", "购方地址电话", "购方开户行及账号",   
                "商品名称", "规格型号", "单位", "数量", "单价", "金额", "税率", "税额", "合计金额", "备注"]  
        rows = []  
        
        # 获取发票基本信息  
        invoice_date = self.invoice_date.strftime('%Y%m%d')  
        buyer_name = self.partner_id.name  
        buyer_vat = self.partner_id.vat or ''  
        buyer_address = (self.partner_id.street or '') + (self.partner_id.street2 or '')  
        buyer_phone = self.partner_id.phone or ''  
        buyer_address_phone = f"{buyer_address} {buyer_phone}"  
        buyer_bank = self.partner_id.bank_ids and self.partner_id.bank_ids[0].bank_name or ''  
        buyer_account = self.partner_id.bank_ids and self.partner_id.bank_ids[0].acc_number or ''  
        buyer_bank_account = f"{buyer_bank} {buyer_account}"  
        
        # 处理每个发票行  
        for line in self.invoice_line_ids:  
            if line.display_type or not line.product_id:  
                continue  
                
            product_name = line.product_id.name  
            spec = line.name  
            unit = line.product_uom_id.name  
            quantity = str(line.quantity)  
            price = str(line.price_unit)  
            amount = str(line.price_subtotal)  
            tax_rate = line.tax_ids and f"{line.tax_ids[0].amount}%" or "0%"  
            tax_amount = str(line.price_total - line.price_subtotal)  
            total_amount = str(line.price_total)  
            note = self.narration or f"合同编号：{self.name}"  
            
            row = [invoice_date, buyer_name, buyer_vat, buyer_address_phone, buyer_bank_account,  
                product_name, spec, unit, quantity, price, amount, tax_rate, tax_amount, total_amount, note]  
            rows.append(row)  
        
        # 如果没有行，至少添加一个空行  
        if not rows:  
            empty_row = [invoice_date, buyer_name, buyer_vat, buyer_address_phone, buyer_bank_account,  
                        "", "", "", "", "", "", "", "", "", ""]  
            rows.append(empty_row)  
        
        # 生成CSV内容  
        import io  
        import csv  
        csv_file = io.StringIO()  
        writer = csv.writer(csv_file)  
        writer.writerow(header)  
        writer.writerows(rows)  
        
        # 创建附件  
        filename = f"{self.name.replace('/', '_')}_cn_etax.csv"  
        attachment = self.env['ir.attachment'].create({  
            'name': filename,  
            'datas': base64.b64encode(csv_file.getvalue().encode('utf-8')),  
            'res_model': self._name,  
            'res_id': self.id,  
            'mimetype': 'text/csv',  
        })  
        
        # 返回下载链接  
        params = url_encode({  
            'model': self._name,  
            'id': self.id,  
            'filename': filename,  
            'download': True,  
        })  
        
        return {  
            'type': 'ir.actions.act_url',  
            'url': f'/web/content/{attachment.id}?{params}',  
            'target': 'new',  
        }

    def generate_cn_etax_export_xml(self):  
        """生成用于中国电子发票开票系统的XML数据"""  
        export_data = self.generate_cn_etax_export_data()  
        
        # 创建XML根元素  
        root = etree.Element('EInvoice')  
        
        # 添加基本元素  
        etree.SubElement(root, 'EIid').text = export_data['EInvoice']['EIid']  
        etree.SubElement(root, 'EInvoiceTag').text = export_data['EInvoice']['EInvoiceTag']  
        etree.SubElement(root, 'InIssuType').text = export_data['EInvoice']['InIssuType']  
        
        # 添加卖方信息  
        seller = etree.SubElement(root, 'SellerInformation')  
        for key, value in export_data['EInvoice']['SellerInformation'].items():  
            etree.SubElement(seller, key).text = value  
        
        # 添加买方信息  
        buyer = etree.SubElement(root, 'BuyerInformation')  
        for key, value in export_data['EInvoice']['BuyerInformation'].items():  
            etree.SubElement(buyer, key).text = value  
        
        # 添加基本信息  
        basic = etree.SubElement(root, 'BasicInformation')  
        for key, value in export_data['EInvoice']['BasicInformation'].items():  
            etree.SubElement(basic, key).text = value  
        
        # 添加发票项目信息  
        for item_data in export_data['EInvoice']['IssuItemInformation']:  
            item = etree.SubElement(root, 'IssuItemInformation')  
            for key, value in item_data.items():  
                etree.SubElement(item, key).text = value  
        
        # 返回格式化的XML字符串  
        return etree.tostring(root, pretty_print=True, encoding='UTF-8', xml_declaration=True)

    def download_cn_etax_export_xml(self):  
        """下载中国电子发票系统XML文件，使用Odoo附件机制"""  
        self.ensure_one()  
        
        if self.move_type != 'out_invoice':  
            raise UserError(_("只有销售发票可以导出到中国电子发票系统"))  
        
        # 生成XML内容  
        xml_content = self.generate_cn_etax_export_xml()  
        
        # 创建附件  
        filename = f"{self.name.replace('/', '_')}_cn_etax.xml"  
        attachment = self.env['ir.attachment'].create({  
            'name': filename,  
            'datas': base64.b64encode(xml_content),  
            'res_model': self._name,  
            'res_id': self.id,  
            'mimetype': 'application/xml',  
        })  
        
        # 返回下载链接  
        params = url_encode({  
            'model': self._name,  
            'id': self.id,  
            'filename': filename,  
            'download': True,  
        })  
        
        return {  
            'type': 'ir.actions.act_url',  
            'url': f'/web/content/{attachment.id}?{params}',  
            'target': 'new',  
        }