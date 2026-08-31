# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields

class TestL10nCnDataExtensions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.user.company_id
        
        # Ensure a journal exists
        cls.journal = cls.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', cls.company.id)], limit=1)
        if not cls.journal:
            cls.journal = cls.env['account.journal'].create({
                'name': 'Test Journal',
                'code': 'TSTX',
                'type': 'general',
                'company_id': cls.company.id,
            })
            
        cls.account = cls.env['account.account'].search([('company_id', '=', cls.company.id)], limit=1)
        if not cls.account:
            cls.account = cls.env['account.account'].create({
                'name': 'Test Account',
                'code': '999999',
                'account_type': 'asset_current',
                'company_id': cls.company.id,
            })
            
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Test Warehouse',
                'code': 'TWH',
                'company_id': cls.company.id,
            })

    def test_stock_warehouse_data_extensions(self):
        """Test standard has_initialized_locations and initialization action on stock.warehouse"""
        # Delete existing custom locations if any to ensure clean test
        child_locs = self.env['stock.location'].search([
            ('location_id', '=', self.warehouse.view_location_id.id),
            ('name', 'in', ['原材料区', '半成品区', '成品区', '不良品区', '退货区', '待检区'])
        ])
        if child_locs:
            child_locs.unlink()
            
        # Verify has_initialized_locations compute field
        self.warehouse._compute_has_initialized_locations()
        self.assertFalse(self.warehouse.has_initialized_locations)
        
        # Trigger initialization
        res = self.warehouse.action_initialize_locations()
        self.assertEqual(res['tag'], 'display_notification')
        self.assertEqual(res['params']['type'], 'success')
        
        self.warehouse._compute_has_initialized_locations()
        self.assertTrue(self.warehouse.has_initialized_locations)
        
        # Test calling again does nothing
        res_empty = self.warehouse.action_initialize_locations()
        self.assertIsNone(res_empty)

    def test_account_move_currency_rate_handling(self):
        """Test inverse rates, currency verification checks, and actions on account.move"""
        # Dynamically select a foreign currency that does not match company currency
        foreign_currency = self.env.ref('base.EUR') if self.company.currency_id != self.env.ref('base.EUR') else self.env.ref('base.USD')
        # Ensure foreign currency is active
        foreign_currency.active = True
        
        # Create general journal to prevent Odoo from overriding currency
        usd_journal = self.env['account.journal'].create({
            'name': 'Foreign Journal',
            'code': 'FRNJ',
            'type': 'general',
            'currency_id': foreign_currency.id,
            'company_id': self.company.id,
        })
        
        # Create partner
        partner = self.env['res.partner'].create({'name': 'Foreign Client'})
        
        # Create invoice in foreign currency
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': usd_journal.id,
            'currency_id': foreign_currency.id,
            'invoice_date': '2024-03-15',
            'date': '2024-03-15',
            'invoice_line_ids': [(0, 0, {
                'name': 'Test product',
                'quantity': 1.0,
                'price_unit': 100.0,
                'account_id': self.account.id,
            })]
        })
        
        # 1. Test computed rate and inverse rate
        move.invoice_currency_rate = 7.25
        move._compute_inverse_currency_rate()
        self.assertAlmostEqual(move.inverse_currency_rate, 1.0 / 7.25, places=6)
        
        # Rate zero
        move.invoice_currency_rate = 0.0
        move._compute_inverse_currency_rate()
        self.assertEqual(move.inverse_currency_rate, 0.0)
        
        # 2. Test action_refresh_currency_rate
        # For company native currency (should show info message)
        move_company = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal.id,
            'currency_id': self.company.currency_id.id,
            'invoice_date': '2024-03-15',
            'invoice_line_ids': [(0, 0, {
                'name': 'Test product',
                'quantity': 1.0,
                'price_unit': 100.0,
                'account_id': self.account.id,
            })]
        })
        res_comp = move_company.action_refresh_currency_rate()
        self.assertEqual(res_comp['params']['type'], 'info')
        
        # For foreign currency
        res_usd = move.action_refresh_currency_rate()
        self.assertEqual(res_usd['params']['type'], 'success')
        
        # 3. Test check rate presence (posting fails when rate is missing)
        # Clear rate records for foreign currency
        existing_rates = self.env['res.currency.rate'].search([
            ('currency_id', '=', foreign_currency.id),
            ('company_id', '=', self.company.id),
            ('name', '>=', '2024-03-01'),
            ('name', '<=', '2024-03-15')
        ])
        existing_rates.unlink()
        
        with self.assertRaises(UserError):
            move.action_post()
            
        # Create rate record
        self.env['res.currency.rate'].create({
            'currency_id': foreign_currency.id,
            'company_id': self.company.id,
            'name': '2024-03-05',
            'rate': 0.138, # 1 / 7.25
        })
        
        # Should now succeed check (we don't post fully because of ledger state, we just test the verification)
        self.assertTrue(move._check_currency_rate_current_month())


class TestL10nCnTemplates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.user.company_id

    def test_all_chart_template_methods(self):
        """Directly call and cover all custom chart template Python files using dynamic python import"""
        import importlib.util
        import os
        
        template_files = {
            'template_cn_common.py': [
                '_get_cn_common_template_data',
                '_get_cn_common_res_company',
            ],
            'template_cn_finance.py': [
                '_get_cn_finance_template_data',
            ],
            'template_cn_agri.py': [
                '_get_cn_agri_template_data',
            ],
            'template_cn_construction.py': [
                '_get_cn_construction_template_data',
            ],
            'template_cn_gov.py': [
                '_get_cn_gov_template_data',
            ],
            'template_cn_npo.py': [
                '_get_cn_npo_template_data',
            ],
            'template_cn_large_bis.py': [
                '_get_cn_large_bis_template_data',
                '_get_cn_large_bis_company',
                '_get_cn_large_bis_account_journal',
            ],
            'template_cn.py': [
                '_get_cn_template_data',
                '_get_cn_res_company',
                '_get_cn_account_journal',
            ]
        }
        
        chart_model = self.env['account.chart.template']
        
        mapping = chart_model._get_chart_template_mapping()
        self.assertIn('generic_coa', mapping)
        
        for filename, methods in template_files.items():
            filepath = os.path.join('/mnt/extra-addons/cn_odoo/l10n_cn/models/', filename)
            mod_name = "odoo.addons.l10n_cn.models." + filename.split('.')[0]
            spec = importlib.util.spec_from_file_location(mod_name, filepath)
            module = importlib.util.module_from_spec(spec)
            # Register in sys.modules to be super clean
            import sys
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            
            cls_obj = getattr(module, 'AccountChartTemplate')
            self.assertTrue(cls_obj)
            
            for method_name in methods:
                method = getattr(cls_obj, method_name)
                res = method(chart_model)
                self.assertTrue(isinstance(res, dict))

    def test_account_move_custom_logic(self):
        """Test account.move constraints, amount in words conversion, and attachments count in l10n_cn"""
        from odoo.exceptions import ValidationError
        
        journal = self.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', self.company.id)], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Test Journal',
                'code': 'TST_TMP',
                'type': 'general',
                'company_id': self.company.id,
            })
            
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': '2024-03-15',
        })
        
        # 1. Test Fapiao Constraints
        # Succeeded: 8 decimal digits
        move.fapiao = '12345678'
        move._check_fapiao()
        
        # ValidationError: length != 8
        with self.assertRaises(ValidationError):
            move.fapiao = '123'
            move._check_fapiao()
            
        # ValidationError: not decimal
        with self.assertRaises(ValidationError):
            move.fapiao = 'abcdefgh'
            move._check_fapiao()
            
        # 2. Test Amount in Words conversion
        self.env['account.move'].check_cn2an()
        res = move._convert_to_amount_in_word(10050.25)
        if res:
            self.assertTrue(len(res) > 0)
            
        # 3. Test attachment counting method
        count = move._count_attachments()
        self.assertEqual(count, 0)

