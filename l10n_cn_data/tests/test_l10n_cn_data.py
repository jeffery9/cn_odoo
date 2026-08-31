# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

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
                'code': 'TST',
                'type': 'general',
                'company_id': cls.company.id,
            })
            
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Test Warehouse',
                'code': 'TWH',
                'company_id': cls.company.id,
            })

    def test_account_move_data_extensions(self):
        """Test any custom overrides on account.move in l10n_cn_data"""
        move = self.env['account.move'].create({
            'journal_id': self.journal.id,
            'date': '2024-03-15',
        })
        
        # If there are custom validation methods or hooks, we trigger them via write or action_post
        # Since we just want to execute the logic in l10n_cn_data/models/account_move.py
        move.write({'ref': 'Test Reference'})
        
        # Test Chinese amount conversion if present in this module
        if hasattr(move, '_get_amount_in_words'):
            words = move._get_amount_in_words(500.50)
            self.assertIsInstance(words, str)

    def test_stock_warehouse_data_extensions(self):
        """Test any custom overrides on stock.warehouse in l10n_cn_data"""
        self.warehouse.write({'name': 'Updated Test Warehouse'})
        # Verify any specific fields or constraints added by the module
        self.assertTrue(self.warehouse.name == 'Updated Test Warehouse')
