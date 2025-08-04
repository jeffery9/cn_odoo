# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    cashflow_category_id = fields.Many2one(
        'account.cashflow.category',
        string='Cash Flow Category',
        compute='_compute_cashflow_category',
        store=True,
        help="Categorizes the cash flow for reporting purposes."
    )

    is_cash_flow_item = fields.Boolean(
        string='Is Cash Flow Item',
        compute='_compute_is_cash_flow_item',
        store=True,
        help="Indicates if this move line is relevant for cash flow statement."
    )

    @api.depends('account_id', 'account_id.account_type', 'account_id.cash_flow_category_ids')
    def _compute_cashflow_category(self):
        for line in self:
            line.cashflow_category_id = False
            if line.account_id and line.account_id.cash_flow_category_ids:
                # For simplicity, take the first category if multiple are linked
                line.cashflow_category_id = line.account_id.cash_flow_category_ids[0]

    @api.depends('account_id.account_type')
    def _compute_is_cash_flow_item(self):
        for line in self:
            # A move line is a cash flow item if its account is a liquidity account
            # or if it's linked to a cash flow category.
            line.is_cash_flow_item = line.account_id.account_type in ('asset_cash', 'liability_cash') or bool(line.cashflow_category_id)

    @api.model
    def _create_financial_report_index(self):
        index_name = 'account_move_line_report_index'
        # Check if the index already exists
        self.env.cr.execute("""
            SELECT 1 FROM pg_indexes WHERE indexname = %s
        """, (index_name,))
        if self.env.cr.fetchone():
            _logger.info(f"Index [{index_name}] already exists.")
            return

        # Create the index
        _logger.info(f"Creating database index [{index_name}] for financial reports.")
        self.env.cr.execute("""
            CREATE INDEX account_move_line_report_index 
            ON account_move_line (account_id, date, company_id);
        """)
        _logger.info(f"Index [{index_name}] created successfully.")
