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

    def test_year_end_bonus_separate_tax_calculation(self):
        """Verify standard Chinese Year-end Bonus separate tax algorithm and brackets"""
        # Create year-end bonus slip of 60000.0 RMB
        struct = self.env['cn.salary.structure'].create({
            'name': 'Bonus Structure',
            'item_ids': [],
        })
        payslip = self.env['cn.payslip'].create({
            'employee_id': self.employee.id,
            'structure_id': struct.id,
            'period': '2024-12',
            'base_wage_amount': 60000.0,
            'payslip_type': 'bonus',
        })
        eval_ctx = payslip._get_eval_context()
        # 60000 / 12 = 5000 quotient. Falls into 10% rate, 210 quick deduction.
        # Tax = 60000 * 10% - 210 = 5790.0
        self.assertEqual(eval_ctx.get('IIT_AMOUNT'), 5790.0)

    def test_severance_pay_exemption_and_taxation(self):
        """Verify PRC Labor Contract severance exemption thresholds (3x local avg) and 3-year amortization tax lookup"""
        struct = self.env['cn.salary.structure'].create({
            'name': 'Severance Structure',
            'item_ids': [],
        })
        
        # 1. Under exemption threshold (250,000 <= 300,000 limit)
        payslip_exempt = self.env['cn.payslip'].create({
            'employee_id': self.employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 250000.0,
            'payslip_type': 'severance',
            'severance_exemption_limit': 300000.0,
        })
        eval_ctx_exempt = payslip_exempt._get_eval_context()
        self.assertEqual(eval_ctx_exempt.get('IIT_AMOUNT'), 0.0)
        
        # 2. Exceeds exemption threshold (440,000 > 300,000 limit)
        # Taxable excess = 140000.0
        # 140000 / 3 = 46666.67 quotient. Falls into 30% rate, 4410 quick deduction.
        # Tax part = 46666.67 * 30% - 4410 = 14000.00 - 4410 = 9590.00.
        # Total Tax = 9590.00 * 3 = 28770.0
        payslip_taxable = self.env['cn.payslip'].create({
            'employee_id': self.employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 440000.0,
            'payslip_type': 'severance',
            'severance_exemption_limit': 300000.0,
        })
        eval_ctx_taxable = payslip_taxable._get_eval_context()
        self.assertEqual(eval_ctx_taxable.get('IIT_AMOUNT'), 28770.0)

    def test_non_resident_individual_monthly_tax_calculation(self):
        """Verify non-resident individual monthly tax calculations on isolated single-month progressive brackets"""
        struct = self.env['cn.salary.structure'].create({
            'name': 'Standard Structure',
            'item_ids': [],
        })
        
        # Non-resident worker
        foreign_employee = self.env['hr.employee'].create({
            'name': 'John Expat',
            'resident_status': 'non_resident',
        })
        
        # Monthly wage = 25000.0. Exemption = 5000.0. Taxable = 20000.0.
        # 20000.0 falls into 12000~25000 bracket: rate 20%, quick deduction 1410.
        # Tax = 20000 * 20% - 1410 = 4000 - 1410 = 2590.0 RMB.
        payslip = self.env['cn.payslip'].create({
            'employee_id': foreign_employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 25000.0,
        })
        eval_ctx = payslip._get_eval_context()
        self.assertEqual(eval_ctx.get('IIT_AMOUNT'), 2590.0)

    def test_disability_security_levy_monthly_accrual(self):
        """Verify Disability Security Fund (残保金) monthly compute projections based on corporate staffing metrics"""
        struct = self.env['cn.salary.structure'].create({
            'name': 'Standard Structure',
            'item_ids': [],
        })
        
        # 1. Create 100 employees in this company (Self.employee is Company A, let's make sure company_id is matched)
        company_id = self.env.company.id
        self.employee.company_id = company_id
        
        # Create 99 more employees in company A
        for i in range(99):
            self.env['hr.employee'].create({
                'name': f'Worker A-{i}',
                'company_id': company_id,
            })
            
        # Total workforce = 100. Disabled employees count = 0.
        # PRC Target = 100 * 1.5% = 1.5. Deficit = 1.5.
        # Monthly base wage projection = 10000.0.
        # Estimated levy = 1.5 * 10000.0 = 15000.0.
        payslip_deficit = self.env['cn.payslip'].create({
            'employee_id': self.employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 10000.0,
        })
        payslip_deficit._compute_disability_levy()
        self.assertEqual(payslip_deficit.estimated_disability_security_levy, 15000.0)
        
        # 2. If we hire 2 disabled workers (disabled_count = 2)
        # Disabled count (2) > Target (1.5) -> deficit = 0.
        # Estimated levy = 0.0
        self.env['hr.employee'].create({
            'name': 'Disabled Worker 1',
            'company_id': company_id,
            'is_disabled': True,
        })
        self.env['hr.employee'].create({
            'name': 'Disabled Worker 2',
            'company_id': company_id,
            'is_disabled': True,
        })
        
        payslip_compliant = self.env['cn.payslip'].create({
            'employee_id': self.employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 10000.0,
        })
        payslip_compliant._compute_disability_levy()
        self.assertEqual(payslip_compliant.estimated_disability_security_levy, 0.0)
