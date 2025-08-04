# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools import float_is_zero
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

FINANCIAL_STATEMENT_MAPPING = {
    'balance_sheet': {
        'assets': ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current'],
        'liabilities': ['liability_payable', 'liability_current', 'liability_non_current'],
        'equity': ['equity', 'equity_unaffected']
    },
    'income_statement': {
        'revenue': ['income', 'income_other'],
        'expenses': ['expense', 'expense_depreciation', 'expense_direct_cost']
    },
}

class FinancialReport(models.AbstractModel):
    _name = 'report.financial_reports.financial_report'
    _description = 'Financial Report Abstract Model'

    def _get_report_data(self, report_obj, options):
        periods = options.get('periods', [])
        columns = []
        for p in periods:
            if p.get('date_from') and p.get('date_to'):
                columns.append(f"{p['date_from']} to {p['date_to']}")
            elif p.get('date_to'):
                columns.append(f"As of {p['date_to']}")
            else:
                columns.append("Current")

        lines = self._get_lines(report_obj, options)
        data = {
            'title': report_obj.name,
            'lines': lines,
            'columns': columns,
            'options': options,
        }
        return data

    def _get_lines(self, report_obj, options):
        company_id = self.env.company.id
        return self._process_report_lines(report_obj.line_ids, options['periods'], level=0, company_id=company_id, report_type=report_obj.report_type)

    def _process_report_lines(self, report_lines, periods, level, company_id, report_type):
        lines_data = []
        for line in report_lines:
            balances = self._calculate_line_balance(line, periods, company_id, report_type)
            children = self._process_report_lines(line.children_ids, periods, level + 1, company_id, report_type)
            lines_data.append({
                'name': line.name,
                'balances': balances,
                'level': level,
                'children': children,
                'action_ids': [self._get_drilldown_action(line, p, company_id, report_type) if line.action_id else False for p in periods]
            })
        return lines_data

    def _calculate_line_balance(self, report_line, periods, company_id, report_type):
        all_period_balances = []
        for period_options in periods:
            balance = 0.0
            for expression in report_line.expression_ids:
                balance += self._evaluate_expression(expression, period_options, company_id, report_type)
            all_period_balances.append(balance)
        return all_period_balances

    def _evaluate_expression(self, expression, period_options, company_id, report_type):
        balance = 0.0
        domain = [('company_id', '=', company_id)]
        domain.extend(self._get_period_domain(period_options, report_type))

        if expression.expression_type == 'account':
            domain.append(('account_id', '=', expression.account_id.id))
            aml = self.env['account.move.line'].search(domain)
            balance = sum(aml.mapped('balance'))
        elif expression.expression_type == 'account_type':
            domain.append(('account_id.account_type', '=', expression.account_type))
            aml = self.env['account.move.line'].search(domain)
            balance = sum(aml.mapped('balance'))
        elif expression.expression_type == 'account_group':
            domain.append(('account_id.group_id', '=', expression.account_group_id.id))
            aml = self.env['account.move.line'].search(domain)
            balance = sum(aml.mapped('balance'))
        elif expression.expression_type == 'aggregation':
            for sub_expression in expression.sub_expression_ids:
                balance += self._evaluate_expression(sub_expression, period_options, company_id, report_type)
        elif expression.expression_type == 'tax_tags':
            domain.append(('tax_tag_ids', 'in', expression.tax_tag_ids.ids))
            aml = self.env['account.move.line'].search(domain)
            balance = sum(aml.mapped('balance'))
        elif expression.expression_type == 'analytic_account':
            if expression.analytic_account_id:
                domain.append(('analytic_distribution', 'ilike', f'%"{{expression.analytic_account_id.id}}"%')) # Simplified check
                aml = self.env['account.move.line'].search(domain)
                balance = sum(aml.mapped('balance'))
        elif expression.expression_type == 'analytic_plan':
            if expression.analytic_plan_id:
                analytic_account_ids = expression.analytic_plan_id.account_ids.ids
                if analytic_account_ids:
                    # This is a simplified approach. A more robust solution would involve analytic.line
                    domain.append(('analytic_distribution', 'ilike', f'%"{{' + str(analytic_account_ids[0]) + '}}"%')) # Simplified check
                    aml = self.env['account.move.line'].search(domain)
                    balance = sum(aml.mapped('balance'))
        elif expression.expression_type == 'formula':
            # WARNING: Executing arbitrary code from database is a security risk.
            # Ensure strict access control to account.report.expression records.
            # The context for safe_eval should be carefully controlled.
            eval_context = {
                'balance': balance, # Current accumulated balance for this line
                'env': self.env, # Limited access to env for specific queries if needed, but be careful
                'float_is_zero': float_is_zero,
                'sum': sum,
                'min': min,
                'max': max,
                'abs': abs,
            }
            try:
                balance = safe_eval(expression.formula, eval_context)
            except Exception as e:
                raise UserError(f"Error evaluating formula for expression {expression.name}: {e}")
        elif expression.expression_type == 'external':
            # This would involve calling an external service or a specific Odoo method.
            # For now, return 0.
            balance = 0.0

        return balance

    def _get_period_domain(self, period_options, report_type):
        domain = []
        # Income statement and Cash Flow typically use date_from and date_to
        # Balance sheet typically uses date_to
        if report_type in ['income_statement', 'cash_flow']:
            if period_options.get('date_from'):
                domain.append(('date', '>=', period_options['date_from']))
            if period_options.get('date_to'):
                domain.append(('date', '<=', period_options['date_to']))
        else: # Default to balance sheet behavior
            if period_options.get('date_to'):
                domain.append(('date', '<=', period_options['date_to']))
        return domain

    def _get_drilldown_action(self, report_line, period_options, company_id, report_type):
        domain = [('company_id', '=', company_id)]
        # Try to derive domain from the first expression
        if report_line.expression_ids:
            expression = report_line.expression_ids[0]
            if expression.expression_type == 'account':
                domain.append(('account_id', '=', expression.account_id.id))
            elif expression.expression_type == 'account_type':
                domain.append(('account_id.account_type', '=', expression.account_type))
            elif expression.expression_type == 'account_group':
                domain.append(('account_id.group_id', '=', expression.account_group_id.id))
            elif expression.expression_type == 'tax_tags':
                domain.append(('tax_tag_ids', 'in', expression.tax_tag_ids.ids))
            elif expression.expression_type == 'analytic_account':
                if expression.analytic_account_id:
                    domain.append(('analytic_distribution', 'ilike', f'%"{{expression.analytic_account_id.id}}"%'))
            elif expression.expression_type == 'analytic_plan':
                if expression.analytic_plan_id:
                    analytic_account_ids = expression.analytic_plan_id.account_ids.ids
                    if analytic_account_ids:
                        domain.append(('analytic_distribution', 'ilike', f'%"{{' + str(analytic_account_ids[0]) + '}}"%'))
            # Aggregation and formula types are harder to drill down directly to AMLs
            # For now, we'll only drill down for direct account/type/group/tag expressions.

        domain.extend(self._get_period_domain(period_options, report_type))

        return {
            'type': 'ir.actions.act_window',
            'name': report_line.name,
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': domain,
        }

    def _write_excel_data(self, worksheet, data):
        # Header
        header_format = worksheet.get_workbook().add_format({'bold': True, 'bg_color': '#f2f2f2'})
        worksheet.write(0, 0, 'Name', header_format)
        
        col = 1
        for column_name in data['columns']:
            worksheet.write(0, col, column_name, header_format)
            worksheet.set_column(col, col, 15) # Column width
            col += 1

        # Write lines
        row = 1
        for line in data['lines']:
            self._write_excel_line(worksheet, row, line)
            row += 1 # Simplified row increment

    def _write_excel_line(self, worksheet, row, line):
        indent_format = worksheet.get_workbook().add_format()
        indent_format.set_indent(line.get('level', 0))
        worksheet.write(row, 0, line['name'], indent_format)
        
        col = 1
        for balance in line['balances']:
            worksheet.write(row, col, balance)
            col += 1

    @api.model
    def _create_report_menu_entries(self):
        reports = self.env['account.report'].search([])
        menu_parent_id = self.env.ref('financial_reports.menu_financial_report_viewer').id

        for report in reports:
            action_xml_id = f'financial_reports.action_report_{report.id}'
            menu_xml_id = f'financial_reports.menu_report_{report.id}'

            # Create or update ir.actions.client
            action_vals = {
                'name': report.name,
                'tag': 'financial_report_viewer_action',
                'context': {'default_report_id': report.id},
            }
            action_record = self.env['ir.actions.client']._load_records([{ 'xml_id': action_xml_id, 'values': action_vals }])

            # Create or update ir.ui.menu
            menu_vals = {
                'name': report.name,
                'parent_id': menu_parent_id,
                'action': action_xml_id,
                'sequence': report.sequence or 10,
            }
            self.env['ir.ui.menu']._load_records([{ 'xml_id': menu_xml_id, 'values': menu_vals }])
