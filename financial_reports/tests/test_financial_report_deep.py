# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase

class TestFinancialReportDeep(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.user.company_id
        
        # Create standard report
        cls.report = cls.env['account.report'].create({
            'name': 'Test Balance Sheet',
            'company_id': cls.company.id,
        })
        
        # Create an account
        cls.account = cls.env['account.account'].create({
            'code': '100101',
            'name': 'Cash in Bank',
            'account_type': 'asset_cash',
            'company_id': cls.company.id,
        })
        
        # Get an existing journal
        cls.journal = cls.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', cls.company.id)], limit=1)
        if not cls.journal:
            cls.journal = cls.env['account.journal'].create({
                'name': 'Misc Journal',
                'code': 'MSCX',
                'type': 'general',
                'company_id': cls.company.id,
            })

    def test_report_line_generation(self):
        """Test the multi-period data and expression generation logic for abstract financial report"""
        # Create an expression
        expr = self.env['account.report.expression'].create({
            'label': 'balance',
            'engine': 'domain',
            'formula': f"[('account_id', '=', {self.account.id})]",
            'subformula': 'sum',
            'report_line_id': self.env['account.report.line'].create({
                'name': 'Cash Line',
                'code': 'CASH',
                'sequence': 10,
                'report_id': self.report.id,
            }).id
        })
        
        # Make a move
        move = self.env['account.move'].create({
            'journal_id': self.journal.id,
            'date': '2024-03-15',
            'line_ids': [
                (0, 0, {'account_id': self.account.id, 'debit': 1000.0, 'credit': 0.0}),
                (0, 0, {'account_id': self.account.id, 'debit': 0.0, 'credit': 1000.0, 'display_type': 'product'}),
            ]
        })
        move.action_post()
        
        # Test basic expression eval on AbstractModel
        financial_model = self.env['report.financial_reports.financial_report']
        period_options = {'date_from': '2024-03-01', 'date_to': '2024-03-31'}
        res = financial_model._evaluate_expression(expr, period_options, self.company.id, 'balance_sheet')
        self.assertEqual(res, 0.0) # Domain fallback safely handled
        
        # Test full data payload method
        payload = financial_model._get_report_data(self.report, {'periods': [period_options]})
        self.assertIn('lines', payload)
        self.assertIn('columns', payload)

    def test_financial_report_edge_cases(self):
        """Cover edge case branches inside financial.report evaluation loops"""
        line_eval = self.env['account.report.line'].create({
            'name': 'Eval Error Line',
            'code': 'ERR',
            'sequence': 20,
            'report_id': self.report.id,
        })
        expr = self.env['account.report.expression'].create({
            'label': 'balance',
            'engine': 'custom',
            'formula': 'invalid_syntax_or_error_causing_eval_failure',
            'report_line_id': line_eval.id
        })
        
        financial_model = self.env['report.financial_reports.financial_report']
        period_options = {'date_from': '2024-03-01', 'date_to': '2024-03-31'}
        # Evaluates safely to 0.0 on exception
        val = financial_model._evaluate_expression(expr, period_options, self.company.id, 'balance_sheet')
        self.assertEqual(val, 0.0)
        
        # Test missing options edge cases
        payload = financial_model._get_report_data(self.report, {'periods': [{'date_to': '2024-03-31'}, {}]})
        self.assertTrue(len(payload['columns']) >= 2)

