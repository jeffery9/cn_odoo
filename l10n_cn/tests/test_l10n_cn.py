# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

@tagged('post_install', '-at_install')
class TestL10nCnTemplates(TransactionCase):
    def test_specialized_coa_inheritance_and_fpos_support(self):
        """Validate that all 5 specialized Chinese CoAs exist and inherit standard 'cn' to enjoy native taxes and fpos"""
        chart_template = self.env['account.chart.template']
        
        specialized_keys = ['cn_npo', 'cn_gov', 'cn_construction', 'cn_agri', 'cn_finance']
        
        for key in specialized_keys:
            # 1. Fetch the raw chart template dict from Odoo's registry
            template_data = chart_template._get_chart_template_data(key)
            self.assertTrue(template_data, f"Chart template '{key}' should be registered in Odoo 17")
            
            # 2. Verify that parent template is 'cn' to automatically inherit taxes and fpos
            self.assertEqual(template_data.get('parent'), 'cn', 
                             f"Template '{key}' must inherit from standard 'cn' to receive native taxes and fiscal positions")
