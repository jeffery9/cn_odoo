# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase

class TestPayrollTax(TransactionCase):
    def setUp(self):
        super().setUp()
        self.employee = self.env['hr.employee'].create({'name': 'Li Si'})

    def test_cumulative_iit_calculation_march(self):
        """Validate that cumulative taxation computes correct progressive IIT on month 3"""
        ytd_ledger = self.env['cn.tax.ytd.record'].create({
            'employee_id': self.employee.id,
            'year': 2024,
        })
        
        # March parameters
        tax_amount = ytd_ledger.compute_monthly_iit(
            month=3,
            current_income=20000.0,
            current_sihf=2200.0,
            current_special_add=2000.0,
            cumulative_paid_before=348.0
        )
        # YTD Taxable (Month 3) = (20000*3) - (5000*3) - (2200*3) - (2000*3) = 60000 - 15000 - 6600 - 6000 = 32400.0
        # Progressive bracket <= 36000 is 3%, Quick Deduction 0.
        # YTD Tax March = 32400 * 3% = 972.0
        # March Tax = 972.0 - 348.0 = 624.0
        self.assertEqual(tax_amount, 624.0)

    def test_payslip_iit_integration_calculation(self):
        """Validate that payslips dynamically calculate cumulative pre-withholding taxes inside standard Odoo formula runs"""
        employee = self.env['hr.employee'].create({
            'name': 'Li Si Taxable',
            'hire_date': '2024-01-01',
        })
        
        # Setup items
        item_basic = self.env['cn.salary.item'].create({
            'name': 'Basic Wage', 'code': 'BASIC', 'item_type': 'fixed'
        })
        item_sihf = self.env['cn.salary.item'].create({
            'name': 'SIHF Deduction', 'code': 'SIHF', 'item_type': 'deduction',
            'python_code': 'result = - 2200.0'
        })
        item_iit = self.env['cn.salary.item'].create({
            'name': 'Individual Income Tax', 'code': 'IIT', 'item_type': 'deduction',
            'python_code': 'result = - IIT_AMOUNT'
        })
        item_net = self.env['cn.salary.item'].create({
            'name': 'Net Salary', 'code': 'NET', 'item_type': 'fixed',
            'python_code': 'result = BASIC + SIHF + IIT'
        })

        struct = self.env['cn.salary.structure'].create({
            'name': 'Standard SIHF & Tax Structure',
            'item_ids': [(4, item_basic.id), (4, item_sihf.id), (4, item_iit.id), (4, item_net.id)],
        })

        # Create slip for Month 3 (March)
        payslip = self.env['cn.payslip'].create({
            'employee_id': employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 20000.0,
        })
        
        # Set special additional deduction to 2000 on slip
        payslip.special_additional_deduction = 2000.0
        payslip.cumulative_paid_before = 348.0
        
        payslip.action_compute_sheet()
        
        iit_line = payslip.line_ids.filtered(lambda l: l.code == 'IIT')
        self.assertEqual(iit_line.amount, -624.0)
        
        net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
        self.assertEqual(net_line.amount, 17176.0) # 20000 - 2200 - 624 = 17176.0
