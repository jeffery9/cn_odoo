# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestMICore(TransactionCase):
    def setUp(self):
        super().setUp()
        self.state_bj = self.env['res.country.state'].search([], limit=1)
        self.employee_test = self.env['hr.employee'].create({
            'name': 'Test',
        })
        self.policy_1 = self.env['mi.policy'].create({
            'name': 'Beijing Policy 2023',
            'region_id': self.state_bj.id,
            'date_start': '2023-01-01',
        })
        self.env['mi.policy.line'].create({
            'policy_id': self.policy_1.id,
            'insurance_type': 'medical',
            'base_min': 6000.0,
            'base_max': 30000.0,
            'rate_employer': 9.8,
            'rate_employee': 2.0,
        })

    def test_policy_overlap_constraint(self):
        """Validate overlapping policies under same region and date raise error"""
        from psycopg2 import IntegrityError
        try:
            with self.cr.savepoint():
                self.env['mi.policy'].create({
                    'name': 'Beijing Policy Overlap',
                    'region_id': self.state_bj.id,
                    'date_start': '2023-01-01',
                })
                self.env['mi.policy'].flush_model()
        except (ValidationError, IntegrityError):
            pass
        else:
            self.fail("ValidationError or IntegrityError not raised")

    def test_policy_date_chronology(self):
        """Validate that new rule cannot predate currently active rules"""
        with self.assertRaises(ValidationError):
            self.env['mi.policy'].create({
                'name': 'Beijing Policy Backdated',
                'region_id': self.state_bj.id,
                'date_start': '2022-01-01',
            })

    def test_contribution_calculations_mid(self):
        """Validate mid-tier wage values calculate exact shares"""
        enrollment = self.env['mi.enrollment'].create({
            'employee_id': self.env.user.employee_id.id or self.env['hr.employee'].create({'name': 'Employee Test'}).id,
            'policy_id': self.policy_1.id,
            'base_amount': 8000.0,
            'start_date': '2024-01-01',
        })
        # Base 8000 (between 6000 and 30000)
        # Employer share: 8000 * 9.8% = 784.00
        # Employee share: 8000 * 2.0% = 160.00
        self.assertEqual(enrollment.amount_employer, 784.00)
        self.assertEqual(enrollment.amount_employee, 160.00)

    def test_contribution_calculations_truncation(self):
        """Validate wage ceiling limits base calculations to 30000"""
        enrollment = self.env['mi.enrollment'].create({
            'employee_id': self.env['hr.employee'].create({'name': 'Employee High Wage'}).id,
            'policy_id': self.policy_1.id,
            'base_amount': 40000.0,
            'start_date': '2024-01-01',
        })
        # Base capped at 30000
        # Employer share: 30000 * 9.8% = 2940.00
        # Employee share: 30000 * 2.0% = 600.00
        self.assertEqual(enrollment.amount_employer, 2940.00)
        self.assertEqual(enrollment.amount_employee, 600.00)

    def test_duplicate_active_enrollment_constraint(self):
        """Validate that an employee cannot have duplicate active/pending enrollments"""
        employee = self.env['hr.employee'].create({'name': 'Employee Dual'})
        self.env['mi.enrollment'].create({
            'employee_id': employee.id,
            'policy_id': self.policy_1.id,
            'base_amount': 10000.0,
            'start_date': '2024-01-01',
            'state': 'enrolled',
        })
        with self.assertRaises(ValidationError):
            self.env['mi.enrollment'].create({
                'employee_id': employee.id,
                'policy_id': self.policy_1.id,
                'base_amount': 12000.0,
                'start_date': '2024-02-01',
                'state': 'pending',
            })

    def test_base_import_override_intercept(self):
        """Validate that importing enrollment records with lower base gets flagged with error"""
        import_wizard = self.env['base_import.import'].create({
            'res_model': 'mi.enrollment',
            'file': b"employee_id,policy_id,base_amount,start_date\nTest,Beijing Policy 2023,4000.0,2024-01-01",
            'file_name': 'test.csv',
            'file_type': 'text/csv'
        })
        results = import_wizard.execute_import(
            ['employee_id', 'policy_id', 'base_amount', 'start_date'],
            ['employee_id', 'policy_id', 'base_amount', 'start_date'],
            {'headers': True, 'quoting': '"', 'separator': ',', 'has_headers': True},
            dryrun=True
        )
        messages = results.get('messages', [])
        self.assertTrue(any("below policy lower limit" in m.get('message', '') for m in messages))

    def test_policy_full_sihf_creation(self):
        """Validate that policy lines can be registered for all 五险一金 classes"""
        state_bj = self.env['res.country.state'].search([], limit=1)
        policy = self.env['mi.policy'].create({
            'name': 'Beijing Full SIHF 2024',
            'region_id': state_bj.id,
            'date_start': '2024-07-01',
        })
        # Verify the model accepts all the new selection categories
        for category in ['pension', 'medical', 'unemployment', 'injury', 'maternity', 'housing_fund', 'supp_housing_fund']:
            line = self.env['mi.policy.line'].create({
                'policy_id': policy.id,
                'insurance_type': category,
                'base_min': 5000.0,
                'base_max': 30000.0,
                'rate_employer': 8.0 if category == 'pension' else 1.0,
                'rate_employee': 4.0 if category == 'pension' else 0.5,
            })
            self.assertEqual(line.insurance_type, category)

    def test_multibase_calculations_and_fallback(self):
        """Validate that contributions correctly use customized bases (social_security vs housing_fund) or fallback to main base"""
        # Setup Policy
        state_bj = self.env['res.country.state'].search([], limit=1)
        policy = self.env['mi.policy'].create({
            'name': 'Beijing Multi-Base Policy',
            'region_id': state_bj.id,
            'date_start': '2024-01-01',
            'state': 'active',
        })
        # Pension line: base_min 5000, base_max 25000, rates: 8% employer, 4% employee
        self.env['mi.policy.line'].create({
            'policy_id': policy.id,
            'insurance_type': 'pension',
            'base_min': 5000.0,
            'base_max': 25000.0,
            'rate_employer': 8.0,
            'rate_employee': 4.0,
        })
        # Housing Fund line: base_min 3000, base_max 30000, rates: 12% employer, 12% employee
        self.env['mi.policy.line'].create({
            'policy_id': policy.id,
            'insurance_type': 'housing_fund',
            'base_min': 3000.0,
            'base_max': 30000.0,
            'rate_employer': 12.0,
            'rate_employee': 12.0,
        })

        # Create Enrollment with base_amount = 6000
        enrollment = self.env['mi.enrollment'].create({
            'employee_id': self.env['hr.employee'].create({'name': 'Wang Wu'}).id,
            'policy_id': policy.id,
            'base_amount': 6000.0,
            'start_date': '2024-01-01',
        })

        # Scenario A: Fallback mode (no enrollment lines)
        # Pension base is 6000 -> 6000 * 8% = 480, 6000 * 4% = 240
        # Housing base is 6000 -> 6000 * 12% = 720, 6000 * 12% = 720
        # Employer total = 480 + 720 = 1200
        # Employee total = 240 + 720 = 960
        self.assertEqual(enrollment.amount_employer, 1200.0)
        self.assertEqual(enrollment.amount_employee, 960.0)

        # Scenario B: Custom line bases
        # Add custom line for housing_fund base = 4000 (different from pension/social security base)
        self.env['mi.enrollment.line'].create({
            'enrollment_id': enrollment.id,
            'insurance_type_group': 'housing_fund',
            'base_amount': 4000.0,
        })
        
        # Re-compute
        enrollment._compute_contributions()
        # Pension base still falls back to 6000 -> 6000 * 8% = 480 / 240
        # Housing base now uses 4000 -> 4000 * 12% = 480 / 480
        # Employer total = 480 + 480 = 960
        # Employee total = 240 + 480 = 720
        self.assertEqual(enrollment.amount_employer, 960.0)
        self.assertEqual(enrollment.amount_employee, 720.0)

    def test_base_import_override_subline_intercept(self):
        """Validate that importing enrollment records with lower base on subline gets flagged with error"""
        # Create a policy with custom bounds
        state_bj = self.env['res.country.state'].search([], limit=1)
        policy_full = self.env['mi.policy'].create({
            'name': 'Beijing Full SIHF Import 2024',
            'region_id': state_bj.id,
            'date_start': '2024-07-01',
        })
        self.env['mi.policy.line'].create({
            'policy_id': policy_full.id,
            'insurance_type': 'housing_fund',
            'base_min': 5000.0,
            'base_max': 30000.0,
            'rate_employer': 12.0,
            'rate_employee': 12.0,
        })
        
        # Dryrun import of mi.enrollment with sub-line housing_fund having 4000 (which is < 5000)
        import_wizard = self.env['base_import.import'].create({
            'res_model': 'mi.enrollment',
            'file': b"employee_id,policy_id,base_amount,start_date,line_ids/insurance_type_group,line_ids/base_amount\nTest,Beijing Full SIHF Import 2024,6000.0,2024-07-01,housing_fund,4000.0",
            'file_name': 'test.csv',
            'file_type': 'text/csv'
        })
        results = import_wizard.execute_import(
            ['employee_id', 'policy_id', 'base_amount', 'start_date', 'line_ids/insurance_type_group', 'line_ids/base_amount'],
            ['employee_id', 'policy_id', 'base_amount', 'start_date', 'line_ids/insurance_type_group', 'line_ids/base_amount'],
            {'headers': True, 'quoting': '"', 'separator': ',', 'has_headers': True},
            dryrun=True
        )
        messages = results.get('messages', [])
        self.assertTrue(any("below policy lower limit" in m.get('message', '') and "housing_fund" in m.get('message', '') for m in messages))

    def test_base_import_override_edge_cases(self):
        """Validate all sub-line base ceiling validations, duplicate checking, and relation resolution in base_import_override"""
        state_bj = self.env['res.country.state'].search([], limit=1)
        policy_full = self.env['mi.policy'].create({
            'name': 'Beijing Edge Case Import 2024',
            'region_id': state_bj.id,
            'date_start': '2024-09-01', # Shifted to prevent constraint violation
        })
        self.env['mi.policy.line'].create({
            'policy_id': policy_full.id,
            'insurance_type': 'housing_fund',
            'base_min': 5000.0,
            'base_max': 30000.0,
            'rate_employer': 12.0,
            'rate_employee': 12.0,
        })
        
        # 1. Sub-line housing_fund over upper limit (40000.0 > 30000)
        import_wizard_over = self.env['base_import.import'].create({
            'res_model': 'mi.enrollment',
            'file': b"employee_id,policy_id,base_amount,start_date,line_ids/insurance_type_group,line_ids/base_amount\nTest,Beijing Edge Case Import 2024,6000.0,2024-09-01,housing_fund,40000.0",
            'file_name': 'test.csv',
            'file_type': 'text/csv'
        })
        results_over = import_wizard_over.execute_import(
            ['employee_id', 'policy_id', 'base_amount', 'start_date', 'line_ids/insurance_type_group', 'line_ids/base_amount'],
            ['employee_id', 'policy_id', 'base_amount', 'start_date', 'line_ids/insurance_type_group', 'line_ids/base_amount'],
            {'headers': True, 'quoting': '"', 'separator': ',', 'has_headers': True},
            dryrun=True
        )
        self.assertTrue(any("above policy upper limit" in m.get('message', '') for m in results_over.get('messages', [])))

        # 2. Duplicate active enrollment warning
        emp_dup = self.env['hr.employee'].create({'name': 'Duplicate Import Worker'})
        self.env['mi.enrollment'].create({
            'employee_id': emp_dup.id,
            'policy_id': policy_full.id,
            'base_amount': 6000.0,
            'start_date': '2024-09-01',
            'state': 'enrolled',
        })
        import_wizard_dup = self.env['base_import.import'].create({
            'res_model': 'mi.enrollment',
            'file': f"employee_id,policy_id,base_amount,start_date,state\nDuplicate Import Worker,Beijing Edge Case Import 2024,6000.0,2024-09-01,enrolled".encode('utf-8'),
            'file_name': 'test.csv',
            'file_type': 'text/csv'
        })
        results_dup = import_wizard_dup.execute_import(
            ['employee_id', 'policy_id', 'base_amount', 'start_date', 'state'],
            ['employee_id', 'policy_id', 'base_amount', 'start_date', 'state'],
            {'headers': True, 'quoting': '"', 'separator': ',', 'has_headers': True},
            dryrun=True
        )
        self.assertTrue(any("already has an active or pending enrollment record" in m.get('message', '') for m in results_dup.get('messages', [])))

        # 3. Test duplicate in same file
        emp_file_dup = self.env['hr.employee'].create({'name': 'File Dup Worker'})
        import_wizard_file_dup = self.env['base_import.import'].create({
            'res_model': 'mi.enrollment',
            'file': f"employee_id,policy_id,base_amount,start_date,state\nFile Dup Worker,Beijing Edge Case Import 2024,6000.0,2024-09-01,enrolled\nFile Dup Worker,Beijing Edge Case Import 2024,6000.0,2024-09-01,enrolled".encode('utf-8'),
            'file_name': 'test.csv',
            'file_type': 'text/csv'
        })
        results_file_dup = import_wizard_file_dup.execute_import(
            ['employee_id', 'policy_id', 'base_amount', 'start_date', 'state'],
            ['employee_id', 'policy_id', 'base_amount', 'start_date', 'state'],
            {'headers': True, 'quoting': '"', 'separator': ',', 'has_headers': True},
            dryrun=True
        )
        self.assertTrue(any("already has an active or pending enrollment record in this import file" in m.get('message', '') for m in results_file_dup.get('messages', [])))

        # 4. _resolve_relation with empty, integer, xml id, etc.
        Import_model = self.env['base_import.import']
        self.assertFalse(Import_model._resolve_relation('hr.employee', ''))
        self.assertEqual(Import_model._resolve_relation('hr.employee', emp_dup.id).id, emp_dup.id)
        self.assertEqual(Import_model._resolve_relation('hr.employee', f" {emp_dup.id} ").id, emp_dup.id)
        self.assertFalse(Import_model._resolve_relation('hr.employee', 999999))



