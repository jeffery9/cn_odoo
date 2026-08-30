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

    deduction_child_education = fields.Float(string="Children Education Deduction", default=0.0)
    deduction_continuing_education = fields.Float(string="Continuing Education Deduction", default=0.0)
    deduction_housing_loan = fields.Float(string="Housing Loan Interest Deduction", default=0.0)
    deduction_housing_rent = fields.Float(string="Housing Rent Deduction", default=0.0)
    deduction_elderly_care = fields.Float(string="Supporting the Elderly Deduction", default=0.0)
    deduction_infant_care = fields.Float(string="Under 3 Infant Care Deduction", default=0.0)

    special_additional_deduction = fields.Float(
        compute='_compute_total_special_additional_deduction',
        store=True,
        string="Total Special Additional Deduction"
    )

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

    @api.depends(
        'deduction_child_education', 'deduction_continuing_education',
        'deduction_housing_loan', 'deduction_housing_rent',
        'deduction_elderly_care', 'deduction_infant_care'
    )
    def _compute_total_special_additional_deduction(self):
        for rec in self:
            rec.special_additional_deduction = (
                rec.deduction_child_education + rec.deduction_continuing_education +
                rec.deduction_housing_loan + rec.deduction_housing_rent +
                rec.deduction_elderly_care + rec.deduction_infant_care
            )

    @api.constrains(
        'deduction_child_education', 'deduction_continuing_education',
        'deduction_housing_loan', 'deduction_housing_rent',
        'deduction_elderly_care', 'deduction_infant_care'
    )
    def _check_special_deduction_limits(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            # 1. Mutual Exclusion: Housing rent and loan interest cannot both be claimed
            if rec.deduction_housing_loan > 0.0 and rec.deduction_housing_rent > 0.0:
                raise ValidationError(
                    "Compliance Error: Housing Loan Interest and Housing Rent "
                    "deductions cannot be claimed simultaneously under PRC Individual Income Tax Law."
                )
            
            # 2. Limit Cap Verification
            limits = {
                'Children Education': (rec.deduction_child_education, 2000.0),
                'Continuing Education': (rec.deduction_continuing_education, 400.0),
                'Housing Loan Interest': (rec.deduction_housing_loan, 1000.0),
                'Housing Rent': (rec.deduction_housing_rent, 1500.0),
                'Supporting the Elderly': (rec.deduction_elderly_care, 3000.0),
                'Under 3 Infant Care': (rec.deduction_infant_care, 2000.0),
            }
            for name, (val, cap) in limits.items():
                if val > cap:
                    raise ValidationError(
                        f"Compliance Error: {name} deduction of {val} RMB exceeds "
                        f"the maximum statutory monthly limit of {cap} RMB under PRC Tax Law."
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
        elif self.resident_status == 'non_resident':
            # Non-residents are taxed individually per-month using 5,000 standard deduction
            taxable_income = max(0.0, self.base_wage_amount - 5000.0)
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
