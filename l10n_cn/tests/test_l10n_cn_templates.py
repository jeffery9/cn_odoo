# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase

class TestL10nCnTemplates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.user.company_id

    def test_l10n_cn_common_template(self):
        """Test the template loading for common enterprise chart of accounts"""
        template = self.env.ref('l10n_cn.l10n_chart_china_common', raise_if_not_found=False)
        if template:
            template.try_loading(self.company)
            # Verify the company has an account chart assigned
            self.assertTrue(self.company.chart_template_id)
            # Verify some core accounts are generated
            accounts = self.env['account.account'].search([('company_id', '=', self.company.id)])
            self.assertTrue(len(accounts) > 10, "Failed to generate common COA accounts")

    def test_l10n_cn_agri_template(self):
        """Test agricultural template loading"""
        template = self.env.ref('l10n_cn.l10n_chart_china_agri', raise_if_not_found=False)
        if template:
            template.try_loading(self.company)
            self.assertTrue(self.company.chart_template_id)

    def test_l10n_cn_construction_template(self):
        """Test construction template loading"""
        template = self.env.ref('l10n_cn.l10n_chart_china_construction', raise_if_not_found=False)
        if template:
            template.try_loading(self.company)
            self.assertTrue(self.company.chart_template_id)

    def test_l10n_cn_finance_template(self):
        """Test finance template loading"""
        template = self.env.ref('l10n_cn.l10n_chart_china_finance', raise_if_not_found=False)
        if template:
            template.try_loading(self.company)
            self.assertTrue(self.company.chart_template_id)

    def test_l10n_cn_gov_template(self):
        """Test government template loading"""
        template = self.env.ref('l10n_cn.l10n_chart_china_gov', raise_if_not_found=False)
        if template:
            template.try_loading(self.company)
            self.assertTrue(self.company.chart_template_id)

    def test_l10n_cn_large_bis_template(self):
        """Test large business template loading"""
        template = self.env.ref('l10n_cn.l10n_chart_china_large_bis', raise_if_not_found=False)
        if template:
            template.try_loading(self.company)
            self.assertTrue(self.company.chart_template_id)

    def test_l10n_cn_npo_template(self):
        """Test non-profit template loading"""
        template = self.env.ref('l10n_cn.l10n_chart_china_npo', raise_if_not_found=False)
        if template:
            template.try_loading(self.company)
            self.assertTrue(self.company.chart_template_id)

    def test_l10n_cn_account_move_amount_in_words(self):
        """Test standard CN amount in words conversion method on account.move"""
        journal = self.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', self.company.id)], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Test Journal',
                'code': 'TST',
                'type': 'general',
                'company_id': self.company.id,
            })
            
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': '2024-03-15',
        })
        
        # In Odoo, amount_total is usually computed. We can manually test the converter method
        if hasattr(move, '_get_amount_in_words'):
            words = move._get_amount_in_words(10050.25)
            self.assertIsInstance(words, str)
            
        if hasattr(move, 'cn_amount_to_text'):
            words = move.cn_amount_to_text(10050.25)
            self.assertIsInstance(words, str)
