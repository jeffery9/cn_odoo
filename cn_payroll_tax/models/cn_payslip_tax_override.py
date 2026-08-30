# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CnPayslip(models.Model):
    _inherit = 'cn.payslip'

    special_additional_deduction = fields.Float(string="Special Additional Deduction", default=0.0)
    cumulative_paid_before = fields.Float(string="Cumulative Paid IIT Before", default=0.0)

    def _get_eval_context(self):
        # Call super to load standard payroll variables
        res = super(CnPayslip, self)._get_eval_context()

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
