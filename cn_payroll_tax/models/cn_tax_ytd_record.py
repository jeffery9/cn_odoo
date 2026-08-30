# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CnTaxYtdRecord(models.Model):
    _name = 'cn.tax.ytd.record'
    _description = 'Year-to-Date Tax Ledger'

    employee_id = fields.Many2one('hr.employee', required=True)
    year = fields.Integer(required=True, default=lambda self: fields.Date.today().year)

    _sql_constraints = [
        ('emp_year_unique', 'unique(employee_id, year)', 'Each employee can only have one YTD record per year!')
    ]

    def compute_monthly_iit(self, month, current_income, current_sihf, current_special_add, cumulative_paid_before):
        self.ensure_one()
        
        # Calculate YTD metrics
        cumulative_income = current_income * month
        cumulative_exempt = 0.0
        cumulative_standard = 5000.0 * month
        cumulative_sihf = current_sihf * month
        cumulative_special_add = current_special_add * month

        taxable_income = cumulative_income - cumulative_exempt - cumulative_standard - cumulative_sihf - cumulative_special_add
        if taxable_income <= 0.0:
            return 0.0

        # PRC IIT Progressive Bracket Schedule (Annualized)
        # Bracket 1: <= 36000 -> 3%, Quick Ded 0
        # Bracket 2: 36000 to 144000 -> 10%, Quick Ded 2520
        # Bracket 3: 144000 to 300000 -> 20%, Quick Ded 16920
        # Bracket 4: 300000 to 420000 -> 25%, Quick Ded 31920
        # Bracket 5: 420000 to 660000 -> 30%, Quick Ded 52920
        # Bracket 6: 660000 to 960000 -> 35%, Quick Ded 85920
        # Bracket 7: > 960000 -> 45%, Quick Ded 181920
        
        rate = 0.03
        quick_ded = 0.0

        if taxable_income > 960000:
            rate = 0.45
            quick_ded = 181920.0
          # We check the ranges descending
        elif taxable_income > 660000:
            rate = 0.35
            quick_ded = 85920.0
        elif taxable_income > 420000:
            rate = 0.30
            quick_ded = 52920.0
        elif taxable_income > 300000:
            rate = 0.25
            quick_ded = 31920.0
        elif taxable_income > 144000:
            rate = 0.20
            quick_ded = 16920.0
        elif taxable_income > 36000:
            rate = 0.10
            quick_ded = 2520.0

        cumulative_tax = round(taxable_income * rate - quick_ded, 2)
        current_month_tax = round(max(0.0, cumulative_tax - cumulative_paid_before), 2)
        return current_month_tax
