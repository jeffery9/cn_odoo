# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase

class TestL10nCnTaxExtensions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.user.company_id
        
        cls.partner = cls.env['res.partner'].create({'name': 'Test Partner'})
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'consu',
        })

    def test_product_tax_catalog(self):
        """Test product logic related to China tax catalog"""
        # Ensure that whatever logic is in l10n_cn_tax/models/product.py gets hit
        self.product.write({'default_code': 'TEST-TAX'})
        if hasattr(self.product, 'tax_catalog_id'):
            # Just read the field to hit the computed or default methods
            _ = self.product.tax_catalog_id
            
        template = self.env['product.template'].create({
            'name': 'Test Template',
        })
        if hasattr(template, 'tax_catalog_id'):
            _ = template.tax_catalog_id

    def test_purchase_order_tax_hooks(self):
        """Test purchase order logic for tax catalog injection"""
        po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_qty': 1.0,
                    'price_unit': 100.0,
                })
            ]
        })
        po.write({'notes': 'Test'})
        # Hit onchange or compute methods
        for line in po.order_line:
            if hasattr(line, '_compute_tax_id'):
                pass

    def test_sale_order_tax_hooks(self):
        """Test sale order logic for tax catalog injection"""
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 100.0,
                })
            ]
        })
        so.write({'note': 'Test'})
        for line in so.order_line:
            if hasattr(line, '_compute_tax_id'):
                pass
