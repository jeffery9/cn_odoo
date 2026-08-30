# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo import fields

class TestMICompliance(TransactionCase):
    def setUp(self):
        super().setUp()
        self.employee = self.env['hr.employee'].create({'name': 'Overdue Worker'})
        
    def test_late_penalty_calculation(self):
        """Validate late payments correctly accrue daily 0.05% interest fees"""
        scan = self.env['mi.compliance.scan'].create({
            'scan_date': '2024-04-15',
        })
        risk_line = self.env['mi.compliance.risk.line'].create({
            'scan_id': scan.id,
            'employee_id': self.employee.id,
            'risk_type': 'missing',
            'amount_principal': 3600.0,
            'months_overdue': 3,
        })
        scan._calculate_penalties(risk_line, overdue_days=100)
        self.assertEqual(risk_line.amount_penalty, 180.00)

    def test_compliance_scan_execution(self):
        """Validate running the compliance scan correctly identifies missing and low-base risks"""
        state_bj = self.env['res.country.state'].search([('code', '=', 'BJ')], limit=1)
        if not state_bj:
            country_cn = self.env['res.country'].search([('code', '=', 'CN')], limit=1)
            if not country_cn:
                country_cn = self.env['res.country'].create({'name': 'China', 'code': 'CN'})
            state_bj = self.env['res.country.state'].create({
                'name': 'Beijing',
                'code': 'BJ',
                'country_id': country_cn.id,
            })

        policy_2023 = self.env['mi.policy'].create({
            'name': 'Beijing Policy 2023',
            'region_id': state_bj.id,
            'date_start': '2023-01-01',
            'state': 'active',
        })
        self.env['mi.policy.line'].create({
            'policy_id': policy_2023.id,
            'insurance_type': 'medical',
            'base_min': 10000.0,
            'base_max': 30000.0,
            'rate_employer': 10.0,
            'rate_employee': 2.0,
        })

        policy_2024 = self.env['mi.policy'].create({
            'name': 'Beijing Policy 2024',
            'region_id': state_bj.id,
            'date_start': '2024-01-01',
            'state': 'active',
        })
        self.env['mi.policy.line'].create({
            'policy_id': policy_2024.id,
            'insurance_type': 'medical',
            'base_min': 6821.0,
            'base_max': 30000.0,
            'rate_employer': 10.0,
            'rate_employee': 2.0,
        })

        emp_zhang = self.env['hr.employee'].create({
            'name': 'Zhang San',
            'hire_date': '2023-10-01',
        })

        emp_li = self.env['hr.employee'].create({
            'name': 'Li Si',
            'hire_date': '2023-01-01',
        })
        self.env['mi.enrollment'].create({
            'employee_id': emp_li.id,
            'policy_id': policy_2024.id,
            'base_amount': 5000.0,
            'start_date': '2024-01-01',
            'state': 'enrolled',
        })

        scan = self.env['mi.compliance.scan'].create({
            'scan_date': '2024-04-15',
        })
        scan.action_execute_scan()

        self.assertEqual(len(scan.risk_line_ids), 2)

        line_zhang = scan.risk_line_ids.filtered(lambda l: l.employee_id == emp_zhang)
        self.assertTrue(line_zhang)
        self.assertEqual(line_zhang.risk_type, 'missing')
        self.assertEqual(line_zhang.months_overdue, 3)
        self.assertEqual(line_zhang.amount_principal, 3600.0)
        self.assertEqual(line_zhang.amount_penalty, 180.00)

        line_li = scan.risk_line_ids.filtered(lambda l: l.employee_id == emp_li)
        self.assertTrue(line_li)
        self.assertEqual(line_li.risk_type, 'low_base')
        self.assertEqual(line_li.base_declared, 5000.0)
        self.assertEqual(line_li.base_expected, 6821.0)
        self.assertEqual(line_li.amount_principal, 1821.0)

    def test_pdf_hash_archival(self):
        """Validate that audit report generation creates a secure SHA-256 registry log"""
        archive_rec = self.env['mi.audit.archive']._generate_and_log_evidence(self.employee)
        self.assertTrue(archive_rec.sha256_hash)
        self.assertEqual(len(archive_rec.sha256_hash), 64)

    def test_compliance_scan_multibase_sihf(self):
        """Validate multi-base scanning correctly flags pension limits while honoring custom housing bases"""
        state_bj = self.env['res.country.state'].search([('code', '=', 'BJ')], limit=1)
        if not state_bj:
            country_cn = self.env['res.country'].search([('code', '=', 'CN')], limit=1)
            if not country_cn:
                country_cn = self.env['res.country'].create({'name': 'China', 'code': 'CN'})
            state_bj = self.env['res.country.state'].create({
                'name': 'Beijing',
                'code': 'BJ',
                'country_id': country_cn.id,
            })

        # Setup Beijing 2024 policy with both pension and housing lines
        policy_sihf = self.env['mi.policy'].create({
            'name': 'Beijing Full SIHF Policy 2024',
            'region_id': state_bj.id,
            'date_start': '2024-01-01',
            'state': 'active',
        })
        self.env['mi.policy.line'].create({
            'policy_id': policy_sihf.id,
            'insurance_type': 'pension',
            'base_min': 6000.0,
            'base_max': 30000.0,
            'rate_employer': 16.0,
            'rate_employee': 8.0,
        })
        self.env['mi.policy.line'].create({
            'policy_id': policy_sihf.id,
            'insurance_type': 'housing_fund',
            'base_min': 5000.0,
            'base_max': 30000.0,
            'rate_employer': 12.0,
            'rate_employee': 12.0,
        })

        # Create active worker
        emp_sihf = self.env['hr.employee'].create({
            'name': 'SIHF Custom Worker',
            'hire_date': '2024-01-01',
        })

        # Base 4500 is below pension (6000) and housing (5000)
        enrollment = self.env['mi.enrollment'].create({
            'employee_id': emp_sihf.id,
            'policy_id': policy_sihf.id,
            'base_amount': 4500.0,
            'start_date': '2024-01-01',
            'state': 'enrolled',
        })

        # Add custom subline for housing_fund = 5500 (above housing min 5000, so housing fund is safe!)
        self.env['mi.enrollment.line'].create({
            'enrollment_id': enrollment.id,
            'insurance_type_group': 'housing_fund',
            'base_amount': 5500.0,
        })

        # Execute scan
        scan = self.env['mi.compliance.scan'].create({
            'scan_date': '2024-04-15',
        })
        scan.action_execute_scan()

        # Check risk lines:
        # Pension base is 4500 (falls back to 4500) which is < pension.base_min 6000. Expected: low_base pension risk!
        # Housing base is 5500 (uses custom 5500) which is >= housing.base_min 5000. Expected: no housing risk!
        pension_risks = scan.risk_line_ids.filtered(lambda l: l.employee_id == emp_sihf)
        self.assertEqual(len(pension_risks), 1)
        self.assertEqual(pension_risks.risk_type, 'low_base')
        self.assertEqual(pension_risks.base_declared, 4500.0)
        self.assertEqual(pension_risks.base_expected, 6000.0)
        self.assertEqual(pension_risks.amount_principal, 1500.0) # 6000 - 4500
