# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    resident_status = fields.Selection([
        ('resident', 'Resident Individual'),
        ('non_resident', 'Non-Resident Individual')
    ], default='resident', string='Resident Status', required=True)


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

    resident_status = fields.Selection(
        related='employee_id.resident_status',
        store=True,
        string='Resident Status',
        readonly=True
    )

    estimated_disability_security_levy = fields.Float(compute='_compute_disability_levy', string='Est Disability Levy Accrual', store=True)

    @api.depends('base_wage_amount', 'company_id')
    def _compute_disability_levy(self):
        for rec in self:
            # 1. Total formal employees in the same company
            total_employees = self.env['hr.employee'].search_count([
                ('company_id', '=', rec.company_id.id)
            ]) or 1
            
            # 2. Total disabled employees in the same company
            disabled_count = self.env['hr.employee'].search_count([
                ('company_id', '=', rec.company_id.id),
                ('is_disabled', '=', True)
            ])
            
            # PRC target: 1.5% of workforce
            target_count = total_employees * 0.015
            deficit = max(0.0, target_count - disabled_count)
            
            # Monthly levy = deficit * company monthly average wage (using current base wage as projection)
            rec.estimated_disability_security_levy = round(deficit * rec.base_wage_amount, 2)

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
        elif self.resident_status == 'non_resident':
            # Non-residents are taxed individually per-month using 5,000 standard deduction
            taxable_income = max(0.0, self.base_wage_amount - 5000.0)
            # Reuses standard monthly progressive brackets (same table as bonus quotient)
            # Note: monthly tax table has brackets on taxable income directly:
            # Let's compute with standard monthly bracket formula (using divide by 12 quotient,
            # but wait, the monthly table for non-residents is:
            # 0~3000: 3%, 3000~12000: 10% - 210.
            # This is the exact same math as _calculate_monthly_bracket_tax(taxable_income * 12)!
            # Wait, our _calculate_monthly_bracket_tax divides by 12, so if we pass total = taxable_income * 12,
            # it divides it by 12 back to taxable_income and multiplies the total by rate!
            # Let's check:round((taxable_income * 12) * rate - quick_ded, 2)
            # Actually, standard monthly tax for a single month of taxable_income is:
            # Tax = taxable_income * Rate - Quick Deduction.
            # So if we define a clean _calculate_non_resident_monthly_tax(taxable_income):
            # It's even cleaner and 100% direct! Let's write that helper method:
            # Let's implement it directly in python:
            iit_amount = self._calculate_non_resident_monthly_tax(taxable_income)
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

    def _calculate_non_resident_monthly_tax(self, taxable_income):
        if taxable_income <= 3000:
            rate, quick_ded = 0.03, 0
        elif taxable_income <= 12000:
            rate, quick_ded = 0.10, 210
        elif taxable_income <= 25000:
            rate, quick_ded = 0.20, 1410
        elif taxable_income <= 35000:
            rate, quick_ded = 0.25, 2660
        elif taxable_income <= 55000:
            rate, quick_ded = 0.30, 4410
        elif taxable_income <= 80000:
            rate, quick_ded = 0.35, 7160
        else:
            rate, quick_ded = 0.45, 15160
        return round(taxable_income * rate - quick_ded, 2)
