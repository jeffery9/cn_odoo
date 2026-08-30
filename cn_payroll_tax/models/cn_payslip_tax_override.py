# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CnPayslip(models.Model):
    _inherit = 'cn.payslip'

    special_additional_deduction = fields.Float(string="Special Additional Deduction", default=0.0)
    cumulative_paid_before = fields.Float(string="Cumulative Paid IIT Before", default=0.0)

    payslip_type = fields.Selection([
        ('salary', 'Regular Salary'),
        ('bonus', 'Year-end Bonus'),
        ('severance', 'Severance Pay')
    ], default='salary', string='Payslip Type', required=True)

    severance_exemption_limit = fields.Float(
        string='Severance Exemption Limit (3x Local Avg)',
        default=300000.0,
        help="Severance pay up to this limit is tax-free under PRC law. Excess is taxed separately."
    )

    def _calculate_monthly_bracket_tax(self, total_bonus):
        m_amount = total_bonus / 12.0
        if m_amount <= 3000:
            rate, quick_ded = 0.03, 0
        elif m_amount <= 12000:
            rate, quick_ded = 0.10, 210
        elif m_amount <= 25000:
            rate, quick_ded = 0.20, 1410
        elif m_amount <= 35000:
            rate, quick_ded = 0.25, 2660
        elif m_amount <= 55000:
            rate, quick_ded = 0.30, 4410
        elif m_amount <= 80000:
            rate, quick_ded = 0.35, 7160
        else:
            rate, quick_ded = 0.45, 15160
        return round(total_bonus * rate - quick_ded, 2)

    def _calculate_severance_tax(self, total_severance, exemption_limit):
        taxable_excess = max(0.0, total_severance - exemption_limit)
        if taxable_excess <= 0:
            return 0.0
        
        m_amount = taxable_excess / 3.0
        if m_amount <= 3000:
            rate, quick_ded = 0.03, 0
        elif m_amount <= 12000:
            rate, quick_ded = 0.10, 210
        elif m_amount <= 25000:
            rate, quick_ded = 0.20, 1410
        elif m_amount <= 35000:
            rate, quick_ded = 0.25, 2660
        elif m_amount <= 55000:
            rate, quick_ded = 0.30, 4410
        elif m_amount <= 80000:
            rate, quick_ded = 0.35, 7160
        else:
            rate, quick_ded = 0.45, 15160
            
        tax_part = m_amount * rate - quick_ded
        return round(tax_part * 3.0, 2)

    def _get_eval_context(self):
        # Call super to load standard payroll variables
        res = super(CnPayslip, self)._get_eval_context()

        if self.payslip_type == 'bonus':
            iit_amount = self._calculate_monthly_bracket_tax(self.base_wage_amount)
        elif self.payslip_type == 'severance':
            iit_amount = self._calculate_severance_tax(self.base_wage_amount, self.severance_exemption_limit)
        else:
            # Regular Salary (Cumulative YTD Pre-withholding)
            # Parse year/month
            if '-' in self.period:
                year = int(self.period.split('-')[0])
                month = int(self.period.split('-')[1])
            else:
                year = fields.Date.today().year
                month = fields.Date.today().month

            # Find or create active YTD record
            ytd_ledger = self.env['cn.tax.ytd.record'].search([
                ('employee_id', '=', self.employee_id.id),
                ('year', '=', year)
            ], limit=1)
            if not ytd_ledger:
                ytd_ledger = self.env['cn.tax.ytd.record'].create({
                    'employee_id': self.employee_id.id,
                    'year': year
                })

            # Calculate monthly tax
            sihf_personal = res.get('SIHF_PERSONAL', 0.0)
            iit_amount = ytd_ledger.compute_monthly_iit(
                month=month,
                current_income=self.base_wage_amount,
                current_sihf=sihf_personal,
                current_special_add=self.special_additional_deduction,
                cumulative_paid_before=self.cumulative_paid_before
            )

        # Inject IIT tax variables
        res.update({
            'IIT_AMOUNT': iit_amount,
        })
        return res
