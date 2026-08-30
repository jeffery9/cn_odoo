# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase

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

    def test_chinese_voucher_print_action_and_rendering(self):
        """Validate that Odoo can successfully render the landscape Accounting Voucher (记账凭证) PDF without QWeb compilation errors"""
        # Create a journal entry
        journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Miscellaneous',
                'code': 'MISC',
                'type': 'general',
            })
        
        # Locate standard accounts
        account_type_receivable = 'asset_receivable'
        account_type_revenue = 'income'
        
        account_a = self.env['account.account'].search([('account_type', '=', account_type_receivable)], limit=1)
        account_b = self.env['account.account'].search([('account_type', '=', account_type_revenue)], limit=1)
        
        if not account_a or not account_b:
            # Attempt to find any active accounts if specific ones do not exist in test DB
            accounts = self.env['account.account'].search([], limit=2)
            if len(accounts) >= 2:
                account_a = accounts[0]
                account_b = accounts[1]
            else:
                return

        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'ref': 'Voucher Print Test',
            'move_type': 'entry',
            'line_ids': [
                (0, 0, {
                    'name': 'Receivable Line',
                    'account_id': account_a.id,
                    'debit': 1000.0,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': 'Revenue Line',
                    'account_id': account_b.id,
                    'debit': 0.0,
                    'credit': 1000.0,
                }),
            ]
        })
        move.action_post()

        # Render the PDF report 'l10n_cn.report_voucher'
        report = self.env.ref('l10n_cn.account_voucher_cn')
        self.assertTrue(report, "Chinese Accounting Voucher action should be defined")
        
        pdf_content, content_type = report._render_qweb_pdf(move.ids)
        self.assertTrue(pdf_content, "QWeb rendering should output non-empty PDF binary bytes")
        self.assertEqual(content_type, 'pdf')

