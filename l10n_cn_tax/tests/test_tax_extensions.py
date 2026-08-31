# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase

class TestL10nCnTaxExtensions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.user.company_id
        
        cls.partner = cls.env['res.partner'].create({'name': 'Test Partner'})
        
        # Create categories hierarchy
        cls.parent_category = cls.env['product.category'].create({'name': 'Parent Category'})
        cls.child_category = cls.env['product.category'].create({
            'name': 'Child Category',
            'parent_id': cls.parent_category.id
        })
        
        # Create a tax catalog item
        cls.tax_item_parent = cls.env['tax.catalog.item'].create({
            'name': 'Parent Tax Category Item',
            'code': 'TX_PARENT',
        })
        cls.tax_item_template = cls.env['tax.catalog.item'].create({
            'name': 'Template Tax Item',
            'code': 'TX_TEMPLATE',
        })
        cls.tax_item_product = cls.env['tax.catalog.item'].create({
            'name': 'Product Tax Item',
            'code': 'TX_PRODUCT',
        })

    def test_product_tax_catalog_priority_funnel(self):
        """Verify the fallback priority funnel: Product-specific > Template-specific > Parent Categories"""
        # Create template with no direct tax_item_id, under parent category having tax_item_id
        self.parent_category.tax_item_id = self.tax_item_parent.id
        
        template = self.env['product.template'].create({
            'name': 'Test Priority Template',
            'categ_id': self.child_category.id,
        })
        product = template.product_variant_id
        
        # 1. Fallback to Parent Category
        retrieved_item = product.get_tax_item_id()
        self.assertEqual(retrieved_item.id, self.tax_item_parent.id)
        
        # 2. Fallback to Template-specific
        template.tax_item_id = self.tax_item_template.id
        retrieved_item = product.get_tax_item_id()
        self.assertEqual(retrieved_item.id, self.tax_item_template.id)
        
        # 3. Product-specific priority
        product.tax_item_id = self.tax_item_product.id
        retrieved_item = product.get_tax_item_id()
        self.assertEqual(retrieved_item.id, self.tax_item_product.id)
        
        # 4. Empty fallback when nothing is set
        self.parent_category.tax_item_id = False
        template.tax_item_id = False
        product.tax_item_id = False
        retrieved_item = product.get_tax_item_id()
        self.assertFalse(retrieved_item)

    def test_purchase_order_tax_hooks(self):
        """Test purchase order line values preparation correctly extracts and sets tax catalog item"""
        # Set tax item on category
        self.parent_category.tax_item_id = self.tax_item_parent.id
        
        product = self.env['product.product'].create({
            'name': 'Purchase Test Product',
            'categ_id': self.child_category.id,
            'type': 'consu',
        })
        
        po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': product.id,
                    'product_qty': 1.0,
                    'price_unit': 100.0,
                })
            ]
        })
        
        line = po.order_line[0]
        res = line._prepare_account_move_line()
        self.assertEqual(res.get('tax_item_id'), self.tax_item_parent.id)

    def test_sale_order_tax_hooks(self):
        """Test sale order line values preparation correctly extracts and sets tax catalog item"""
        # Set tax item on product
        product = self.env['product.product'].create({
            'name': 'Sale Test Product',
            'categ_id': self.child_category.id,
            'type': 'consu',
            'tax_item_id': self.tax_item_product.id,
        })
        
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 100.0,
                })
            ]
        })
        
        line = so.order_line[0]
        res = line._prepare_invoice_line()
        self.assertEqual(res.get('tax_item_id'), self.tax_item_product.id)
