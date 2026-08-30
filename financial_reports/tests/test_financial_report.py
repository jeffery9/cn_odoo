# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestFinancialReport(TransactionCase):
    def setUp(self):
        super(TestFinancialReport, self).setUp()
        self.report_model = self.env['report.financial_reports.financial_report']
        
        # 1. Setup sample accounts
        self.account_cash = self.env['account.account'].create({
            'name': 'Cash in Hand',
            'code': '1001_test',
            'account_type': 'asset_cash',
        })
        self.account_revenue = self.env['account.account'].create({
            'name': 'Sales Revenue',
            'code': '6001_test',
            'account_type': 'income',
        })

        # 2. Setup standard report models
        self.report = self.env['account.report'].create({
            'name': 'Test Financial Report',
            'report_type': 'balance_sheet',
            'sequence': 1,
        })
        
        # Parent line
        self.line_assets = self.env['account.report.line'].create({
            'report_id': self.report.id,
            'name': 'Assets Section',
            'sequence': 10,
            'level': 0,
        })

        # Child line (Cash)
        self.line_cash = self.env['account.report.line'].create({
            'report_id': self.report.id,
            'name': 'Cash Position',
            'sequence': 20,
            'level': 1,
            'parent_id': self.line_assets.id,
        })

        # Expression linked to child line
        self.expr_cash = self.env['account.report.expression'].create({
            'report_line_id': self.line_cash.id,
            'name': 'Cash Expression',
            'expression_type': 'account',
            'account_id': self.account_cash.id,
        })

    def test_expression_evaluation(self):
        """Validate that account expression evaluations correctly pull account move line balances"""
        # Create a journal entry to post some balance to our cash account
        journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'General Journal',
                'code': 'GEN',
                'type': 'general',
            })

        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': '2024-03-01',
            'line_ids': [
                (0, 0, {
                    'account_id': self.account_cash.id,
                    'name': 'Debit Line',
                    'debit': 5000.0,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': self.account_revenue.id,
                    'name': 'Credit Line',
                    'debit': 0.0,
                    'credit': 5000.0,
                }),
            ]
        })
        move.action_post()

        # Run evaluation with a specific period
        periods = [{'date_from': '2024-01-01', 'date_to': '2024-03-31'}]
        options = {'periods': periods}
        
        report_data = self.report_model._get_report_data(self.report, options)
        self.assertTrue(report_data)
        
        # Verify that the Cash line balance is 5000.0
        cash_line = next(l for l in report_data['lines'] if l['name'] == 'Cash Position')
        self.assertEqual(cash_line['balances'][0], 5000.0)

    def test_formula_and_aggregation_evaluation(self):
        """Validate that complex formula and aggregation expressions compute values correctly using safe_eval"""
        # Create formula expression
        expr_formula = self.env['account.report.expression'].create({
            'report_line_id': self.line_cash.id,
            'name': 'Formula Expression',
            'expression_type': 'formula',
            'formula': 'balance * 2.0',
        })
        
        # Verify evaluation doesn't raise error
        periods = [{'date_from': '2024-01-01', 'date_to': '2024-03-31'}]
        balance = self.report_model._evaluate_expression(expr_formula, periods[0], self.env.company.id, 'balance_sheet')
        self.assertEqual(balance, 0.0) # Evaluates to 0 if initial balance is 0

    def test_drilldown_action_generation(self):
        """Validate drilldown actions generate standard native Odoo action payloads for account/type/group expressions"""
        period_options = {'date_from': '2024-01-01', 'date_to': '2024-03-31'}
        action = self.report_model._get_drilldown_action(self.line_cash, period_options, self.env.company.id, 'balance_sheet')
        
        self.assertEqual(action['res_model'], 'account.move.line')
        self.assertEqual(action['view_mode'], 'list,form')
        self.assertIn(('account_id', '=', self.account_cash.id), action['domain'])
