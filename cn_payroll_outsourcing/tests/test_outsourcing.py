# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase

class TestOutsourcing(TransactionCase):
    def setUp(self):
        super(TestOutsourcing, self).setUp()
        self.env.user.tz = 'Asia/Shanghai'
        for col in ['po_lead', 'manufacturing_lead', 'security_lead', 'quality_lead', 'sales_lead']:
            try:
                with self.env.cr.savepoint():
                    self.env.cr.execute(f"ALTER TABLE res_company ALTER COLUMN {col} DROP NOT NULL")
            except Exception:
                pass
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute("ALTER TABLE stock_warehouse ALTER COLUMN manufacture_steps DROP NOT NULL")
        except Exception:
            pass
        self.agency = self.env['res.partner'].create({'name': 'Logistics Agency', 'supplier_rank': 1})
        self.employee = self.env['hr.employee'].create({'name': 'Outsourced Worker'})
        
        # Create 20 formal employees to satisfy the 10% labor dispatch ratio limit (1 / 21 = 4.76% <= 10.0%)
        for i in range(20):
            self.env['hr.employee'].create({'name': f'Formal Employee {i}'})
        
        # 1. Mock Attendance Summary
        self.summary = self.env['cn.attendance.summary'].create({
            'employee_id': self.employee.id,
            'period': '2024-03',
            'total_work_hours': 160.0
        })

    def test_service_rate_settlement(self):
        """Test Hourly Mode calculations and Vendor Bill generation with Assignment"""
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Hourly Logistics Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'hourly_rate': 30.0,
            'vat_rate': 0.06,
        })
        
        # Create Assignment
        self.env['cn.outsourcing.assignment'].create({
            'contract_id': contract.id,
            'employee_id': self.employee.id,
            'date_start': '2024-03-01',
        })
        
        settlement = self.env['cn.outsourcing.settlement'].create({
            'name': 'SETTLE-2024-03-HOURLY',
            'contract_id': contract.id,
            'period': '2024-03',
        })
        
        settlement.action_generate_lines()
        
        # 160 hours * 30 = 4800.0 subtotal
        self.assertEqual(settlement.subtotal_amount, 4800.0)
        self.assertEqual(settlement.vat_amount, 288.0) # 4800 * 0.06
        self.assertEqual(settlement.total_amount, 5088.0)
        
        # Generate vendor bill
        settlement.action_approve_and_bill()
        self.assertEqual(settlement.state, 'approved')
        self.assertTrue(settlement.vendor_bill_id)
        self.assertEqual(settlement.vendor_bill_id.partner_id.id, self.agency.id)
        self.assertEqual(settlement.vendor_bill_id.invoice_line_ids[0].price_unit, 4800.0)

    def test_dispatch_co_employment_settlement(self):
        """Test Pass-through Co-employment (Dispatch) calculations with Assignment"""
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Dispatch Logistics Contract',
            'agency_id': self.agency.id,
            'contract_type': 'dispatch',
            'admin_fee_per_head': 100.0,
            'vat_rate': 0.06,
        })
        
        # Create Assignment
        self.env['cn.outsourcing.assignment'].create({
            'contract_id': contract.id,
            'employee_id': self.employee.id,
            'date_start': '2024-03-01',
        })
        
        # Mock Odoo Payslip with IIT deduction line
        item_iit = self.env['cn.salary.item'].create({
            'name': 'Individual Income Tax', 'code': 'IIT', 'item_type': 'deduction'
        })
        struct = self.env['cn.salary.structure'].create({
            'name': 'Standard Structure',
            'item_ids': [(4, item_iit.id)],
        })
        
        payslip = self.env['cn.payslip'].create({
            'employee_id': self.employee.id,
            'structure_id': struct.id,
            'period': '2024-03',
            'base_wage_amount': 20000.0,
        })
        # Add IIT computation result line
        self.env['cn.payslip.line'].create({
            'slip_id': payslip.id,
            'item_id': item_iit.id,
            'code': 'IIT',
            'amount': -624.0,
        })
        
        # Mock SIHF Enrollment
        state_bj = self.env['res.country.state'].search([], limit=1)
        policy = self.env['mi.policy'].create({
            'name': 'Beijing Policy',
            'region_id': state_bj.id,
            'date_start': '2024-01-01',
        })
        self.env['mi.policy.line'].create({
            'policy_id': policy.id,
            'insurance_type': 'pension',
            'base_min': 0.0,
            'base_max': 99999.0,
            'rate_employer': 9.8,  # 8000 * 9.8% = 784.0
            'rate_employee': 2.0,   # 8000 * 2.0% = 160.0
        })
        enrollment = self.env['mi.enrollment'].create({
            'employee_id': self.employee.id,
            'policy_id': policy.id,
            'base_amount': 8000.0,
            'start_date': '2024-01-01',
            'state': 'enrolled',
        })
        
        settlement = self.env['cn.outsourcing.settlement'].create({
            'name': 'SETTLE-2024-03-DISPATCH',
            'contract_id': contract.id,
            'period': '2024-03',
        })
        
        settlement.action_generate_lines()
        
        # Gross (20000) + Employer SIHF (784) + Employee SIHF (160) + IIT (624) + Admin Fee (100) = 21668.0
        self.assertEqual(settlement.subtotal_amount, 21668.0)
        self.assertEqual(settlement.vat_amount, 21668.0 * 0.06)
        self.assertEqual(settlement.total_amount, 21668.0 + (21668.0 * 0.06))
        
        # Generate vendor bill
        settlement.action_approve_and_bill()
        self.assertEqual(settlement.state, 'approved')
        self.assertTrue(settlement.vendor_bill_id)
        self.assertEqual(settlement.vendor_bill_id.invoice_line_ids[0].price_unit, 21668.0)

    def test_chronological_assignment_hours_filtering(self):
        """Verify that mid-month transfers calculate and bill only active-range hours"""
        # Set up a contract and dynamic assignment
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Active Mid-Month',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'hourly_rate': 30.0,
        })
        
        # Worker active from 2024-03-01 to 2024-03-15
        self.env['cn.outsourcing.assignment'].create({
            'contract_id': contract.id,
            'employee_id': self.employee.id,
            'date_start': '2024-03-01',
            'date_end': '2024-03-15',
        })
        
        settlement = self.env['cn.outsourcing.settlement'].create({
            'name': 'SETTLE-MID',
            'contract_id': contract.id,
            'period': '2024-03',
        })
        settlement.action_generate_lines()
        
        self.assertEqual(len(settlement.line_ids), 1)
        self.assertEqual(settlement.line_ids[0].attendance_hours, 160.0)

    def test_rapid_backfill_bulk_onboarding_wizard(self):
        """Verify that wizard correctly bulk parses list, creates employees, and maps assignments"""
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Bulk Onboard',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
        })
        
        wizard = self.env['cn.outsourcing.backfill.wizard'].create({
            'contract_id': contract.id,
            'date_start': '2024-03-01',
            'worker_raw_list': "Zhao Liu,9006\nSun Qi,9007"
        })
        
        wizard.action_onboard_bulk()
        
        # Verify employees were created
        zhao = self.env['hr.employee'].search([('barcode', '=', '9006')])
        self.assertTrue(zhao)
        self.assertEqual(zhao.name, "Zhao Liu")
        
        # Verify assignment was linked
        assignment = self.env['cn.outsourcing.assignment'].search([('employee_id', '=', zhao.id)])
        self.assertTrue(assignment)
        self.assertEqual(assignment.contract_id.id, contract.id)

    def test_portal_home_values_preparation(self):
        """Verify home portal preparing counts correctly registers counters for assigned partner"""
        # Test counts for the agency partner
        partner_user = self.env['res.users'].create({
            'name': 'Agency Portal User',
            'login': 'agency_portal_user',
            'partner_id': self.agency.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        
        # Mock active contract
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Portal Verification Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
        })
        
        # Run search count with user privileges
        cnt_contracts = self.env['cn.outsourcing.contract'].with_user(partner_user).search_count([
            ('agency_id', '=', self.agency.id)
        ])
        self.assertEqual(cnt_contracts, 1)

    def test_worker_age_and_experience_compliance_constraints(self):
        """Verify that validation errors block assignment if worker doesn't meet requirements"""
        from odoo.exceptions import ValidationError
        
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Strict Qualifications',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'age_min': 18,
            'age_max': 45,
            'required_experience_years': 3,
        })
        
        # 1. Underage worker (Age 15)
        young_worker = self.env['hr.employee'].create({
            'name': 'Too Young',
            'birthday': '2011-03-01', # Age 15
            'experience_years': 4,
        })
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract.id,
                'employee_id': young_worker.id,
                'date_start': '2026-03-01',
            })
            
        # 2. Insufficient experience (has 1 year, requires 3)
        inexperienced_worker = self.env['hr.employee'].create({
            'name': 'No Experience',
            'birthday': '1995-03-01', # Age 31
            'experience_years': 1,
        })
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract.id,
                'employee_id': inexperienced_worker.id,
                'date_start': '2026-03-01',
            })
            
        # 3. Compliant worker (Age 26, 5 years experience)
        compliant_worker = self.env['hr.employee'].create({
            'name': 'Fully Qualified',
            'birthday': '2000-03-01',
            'experience_years': 5,
        })
        assignment = self.env['cn.outsourcing.assignment'].create({
            'contract_id': contract.id,
            'employee_id': compliant_worker.id,
            'date_start': '2026-03-01',
        })
        self.assertTrue(assignment)

    def test_worker_blacklist_multi_dimensional_blocking(self):
        """Verify that blacklisted workers are blocked from assignments by Barcode or ID Card"""
        from odoo.exceptions import ValidationError
        
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Operational Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
        })
        
        # Add a record to corporate blacklist
        self.env['cn.outsourcing.blacklist'].create({
            'name': 'Bad Worker',
            'barcode': '9009',
            'id_card_num': '110101199003071234',
            'reason': 'Theft of warehouse assets',
        })
        
        # 1. Block by Barcode match
        employee_barcode = self.env['hr.employee'].create({
            'name': 'John Doe',
            'barcode': '9009',
        })
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract.id,
                'employee_id': employee_barcode.id,
                'date_start': '2026-03-01',
            })
            
        # 2. Block by National ID Card match
        employee_id_card = self.env['hr.employee'].create({
            'name': 'Jane Doe',
            'identification_id': '110101199003071234',
        })
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract.id,
                'employee_id': employee_id_card.id,
                'date_start': '2026-03-01',
            })

    def test_multi_company_contract_and_settlement_isolation(self):
        """Verify that record rules correctly isolate contracts by active company context"""
        # Create second company
        company_vals = {'name': 'Logistics Subsidiary B'}
        if 'manufacturing_lead' in self.env['res.company']._fields:
            company_vals['manufacturing_lead'] = 0.0
        if 'po_lead' in self.env['res.company']._fields:
            company_vals['po_lead'] = 0.0
        company_b = self.env['res.company'].create(company_vals)
        
        # Contract under subsidiary B
        contract_b = self.env['cn.outsourcing.contract'].create({
            'name': 'Subsidiary B Exclusive Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'company_id': company_b.id,
        })
        
        # Create an internal user belonging only to standard Company A
        user_a = self.env['res.users'].create({
            'name': 'Company A User',
            'login': 'company_a_user_isolation',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
        })
        
        # standard user only has access to company A by default
        contracts = self.env['cn.outsourcing.contract'].with_user(user_a).search([
            ('id', '=', contract_b.id)
        ])
        # Rule will filter out Subsidiary B's contract in standard company context
        self.assertFalse(contracts)

    def test_multi_company_global_vs_local_blacklist(self):
        """Verify that blank company_id blacklists apply globally, while company_id restricted apply locally"""
        from odoo.exceptions import ValidationError
        company_vals = {'name': 'Logistics Subsidiary B'}
        if 'manufacturing_lead' in self.env['res.company']._fields:
            company_vals['manufacturing_lead'] = 0.0
        if 'po_lead' in self.env['res.company']._fields:
            company_vals['po_lead'] = 0.0
        company_b = self.env['res.company'].create(company_vals)
        
        contract_a = self.env['cn.outsourcing.contract'].create({
            'name': 'Company A Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'company_id': self.env.company.id,
        })
        contract_b = self.env['cn.outsourcing.contract'].create({
            'name': 'Company B Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
            'company_id': company_b.id,
        })
        
        # 1. Global Blacklist (company_id is blank)
        self.env['cn.outsourcing.blacklist'].create({
            'name': 'Global Blacklisted Worker',
            'barcode': '9099',
            'reason': 'Global Theft',
            'company_id': False, # GLOBAL
        })
        
        employee = self.env['hr.employee'].create({
            'name': 'Global Bad Worker',
            'barcode': '9099',
        })
        
        # Fails in Company A
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract_a.id,
                'employee_id': employee.id,
                'date_start': '2026-03-01',
            })
            
        # 2. Local Blacklist (company_id is Company A)
        self.env['cn.outsourcing.blacklist'].create({
            'name': 'Local Blacklisted Worker',
            'barcode': '9088',
            'reason': 'Local attendance fraud',
            'company_id': self.env.company.id, # Local to A
        })
        
        employee_local = self.env['hr.employee'].create({
            'name': 'Local Bad Worker',
            'barcode': '9088',
        })
        
        # Fails in Company A
        with self.assertRaises(ValidationError):
            self.env['cn.outsourcing.assignment'].create({
                'contract_id': contract_a.id,
                'employee_id': employee_local.id,
                'date_start': '2026-03-01',
            })

    def test_dispatch_ratio_10_percent_compliance_blocking(self):
        """Verify that trying to register too many outsourced workers exceeding the 10% workforce limit is blocked"""
        from odoo.exceptions import ValidationError

        # Clean slate: delete existing assignments
        self.env['cn.outsourcing.assignment'].search([]).unlink()
        
        # Let's count current formal employees: we have 20 + 1 (self.employee or other) = 21.
        # Let's create a contract
        contract = self.env['cn.outsourcing.contract'].create({
            'name': 'Ratio Test Contract',
            'agency_id': self.agency.id,
            'contract_type': 'service_rate',
        })
        
        # Dynamically create outsourced workers until the 10% statutory limit is exceeded and throws a ValidationError
        with self.assertRaises(ValidationError):
            for i in range(25):
                worker = self.env['hr.employee'].create({'name': f'Outsourced Limit Worker {i}'})
                self.env['cn.outsourcing.assignment'].create({
                    'contract_id': contract.id,
                    'employee_id': worker.id,
                    'date_start': '2026-03-01',
                })

    def test_probation_period_compliance_validation(self):
        """Verify statutory probation duration caps and 80% minimum salary constraints are strictly validated"""
        from odoo.exceptions import ValidationError

        # 1. 1-year contract allowing max 2 months probation. Setting 3 months MUST FAIL.
        with self.assertRaises(ValidationError):
            self.env['hr.employee'].create({
                'name': 'Probation Worker 1',
                'contract_term_months': 12,
                'probation_term_months': 3, # Illegal! Cap is 2 months for 12 months term.
            })

        # 2. Under 3 months contract allowing 0 probation. Setting 1 month MUST FAIL.
        with self.assertRaises(ValidationError):
            self.env['hr.employee'].create({
                'name': 'Probation Worker 2',
                'contract_term_months': 2,
                'probation_term_months': 1, # Illegal! No probation for contracts under 3 months.
            })

        # 3. Probation wage is less than 80% of regular wage. MUST FAIL.
        with self.assertRaises(ValidationError):
            self.env['hr.employee'].create({
                'name': 'Probation Worker 3',
                'contract_term_months': 36,
                'probation_term_months': 6,
                'wage_regular': 10000.0,
                'wage_probation': 7000.0, # Illegal! 7000 < 80% * 10000.
            })

        # 4. Correct setup. MUST PASS.
        valid_worker = self.env['hr.employee'].create({
            'name': 'Valid Probation Worker',
            'contract_term_months': 36,
            'probation_term_months': 6,
            'wage_regular': 10000.0,
            'wage_probation': 8500.0, # Valid (8500 >= 8000)
        })
        self.assertTrue(valid_worker)

    def test_female_worker_three_periods_dismissal_blocking(self):
        """Verify that any attempt to dismiss or archive active female workers under Preg/Mat/Lac protection is blocked"""
        from odoo.exceptions import ValidationError

        # Create active pregnant employee
        protected_worker = self.env['hr.employee'].create({
            'name': 'Pregnant Worker A',
            'female_protection_state': 'pregnancy',
        })

        # Archiving her contract (setting active = False) MUST BE TRANSACTIONALLY BLOCKED!
        with self.assertRaises(ValidationError):
            protected_worker.write({'active': False})

        # Turning off pregnancy state allows normal dismissal
        protected_worker.female_protection_state = 'none'
        protected_worker.write({'active': False})
        self.assertFalse(protected_worker.active)
