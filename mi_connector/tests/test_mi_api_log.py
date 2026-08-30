# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
import json

class TestMiApiLog(TransactionCase):

    def setUp(self):
        super().setUp()
        self.log_model = self.env['mi.api.log']
        
        # Setup standard base data for business flow tests
        self.employee = self.env['hr.employee'].create({
            'name': 'Government Test Worker',
            'identification_id': '110101199003071234'
        })
        self.state_sh = self.env['res.country.state'].search([], limit=1)
        self.policy = self.env['mi.policy'].create({
            'name': 'Shanghai Standard Policy 2026',
            'region_id': self.state_sh.id,
            'date_start': '2026-07-01',
            'state': 'active'
        })
        self.line_med = self.env['mi.policy.line'].create({
            'policy_id': self.policy.id,
            'insurance_type': 'medical',
            'base_min': 5000.0,
            'base_max': 30000.0,
            'rate_employer': 10.0,
            'rate_employee': 2.0
        })

    def test_api_log_creation(self):
        """Test standard creation of the API transaction log with all required attributes."""
        log = self.log_model.create({
            'name': 'TX-SSB-2026-001',
            'request_data': '{"employee": "Wang Wu", "action": "enroll"}',
            'response_data': '{"status": "accepted", "registry_id": "SSB-9981"}',
            'state': 'success',
            'res_model': 'mi.enrollment',
            'res_id': 1
        })
        self.assertEqual(log.name, 'TX-SSB-2026-001')
        self.assertEqual(log.state, 'success')
        self.assertEqual(log.res_model, 'mi.enrollment')

    def test_enrollment_declaration_and_polling_success(self):
        """Test the complete workflow of declaring enrollment and successfully polling results."""
        enrollment = self.env['mi.enrollment'].create({
            'employee_id': self.employee.id,
            'policy_id': self.policy.id,
            'base_amount': 8000.0,
            'state': 'pending',
            'start_date': '2026-09-01'
        })
        
        # 1. Action Submit Declaration
        enrollment.action_submit_declaration()
        self.assertEqual(enrollment.declaration_state, 'submitting')
        self.assertTrue(enrollment.declaration_receipt_id.startswith('TX-SSB-'))
        
        # Verify Pending API Log Created
        log = self.log_model.search([('res_model', '=', 'mi.enrollment'), ('res_id', '=', enrollment.id)])
        self.assertEqual(len(log), 1)
        self.assertEqual(log.state, 'pending')
        
        # 2. Trigger Polling with forced success
        self.env['mi.enrollment'].with_context(test_force_success=True).cron_poll_mi_declaration_status()
        
        # Verify transitions and active enrollment state
        self.assertEqual(log.state, 'success')
        self.assertEqual(enrollment.declaration_state, 'enrolled')
        self.assertEqual(enrollment.state, 'enrolled')
        
        # Verify chatter log response
        response_payload = json.loads(log.response_data)
        self.assertTrue(response_payload.get('registry_code').startswith('SSB-REG-'))

    def test_enrollment_declaration_and_polling_failure(self):
        """Test declaration workflow with validation failure resulting in rejection and reversion."""
        enrollment = self.env['mi.enrollment'].create({
            'employee_id': self.employee.id,
            'policy_id': self.policy.id,
            'base_amount': 8000.0,
            'state': 'pending',
            'start_date': '2026-09-01'
        })
        
        # 1. Action Submit
        enrollment.action_submit_declaration()
        log = self.log_model.search([('res_model', '=', 'mi.enrollment'), ('res_id', '=', enrollment.id)])
        
        # 2. Poll with forced failure
        self.env['mi.enrollment'].with_context(test_force_fail=True).cron_poll_mi_declaration_status()
        
        # Verify transition to rejected state and reversion of enrollment to draft for correction
        self.assertEqual(log.state, 'failed')
        self.assertEqual(enrollment.declaration_state, 'rejected')
        self.assertEqual(enrollment.state, 'draft')

    def test_policy_base_synchronization(self):
        """Test synchronization of policy base boundaries against municipal government service."""
        # Check initial values
        self.assertEqual(self.line_med.base_min, 5000.0)
        self.assertEqual(self.line_med.base_max, 30000.0)
        
        # Run base synchronization
        updated = self.policy.action_sync_policy_bases()
        self.assertTrue(updated)
        
        # Check limits were dynamically updated
        self.assertEqual(self.line_med.base_min, 6800.0)
        self.assertEqual(self.line_med.base_max, 36500.0)
        
        # Verify sync transaction was recorded
        log = self.log_model.search([('res_model', '=', 'mi.policy'), ('res_id', '=', self.policy.id)])
        self.assertEqual(len(log), 1)
        self.assertEqual(log.state, 'success')
        self.assertTrue('medical' in log.response_data)

    def test_enrollment_export_wizard(self):
        """Test the Excel bulk-import batch sheet generation wizard."""
        from odoo.exceptions import UserError
        
        # Create enrollment for the target month
        enrollment = self.env['mi.enrollment'].create({
            'employee_id': self.employee.id,
            'policy_id': self.policy.id,
            'base_amount': 7500.0,
            'state': 'pending',
            'start_date': '2026-08-15'
        })
        
        # Instantiate the export wizard
        wizard = self.env['mi.enrollment.export.wizard'].create({
            'period': '2026-08',
            'state': 'pending'
        })
        
        # Generate the Excel sheet
        wizard.action_export_excel()
        
        # Assert generation success and file details
        self.assertEqual(wizard.export_status, 'done')
        self.assertIsNotNone(wizard.file_data)
        self.assertEqual(wizard.file_name, 'SSB_Unified_Enrollment_2026-08_pending.xlsx')
        
        # Assert that generating for a period with zero records raises UserError
        wizard_empty = self.env['mi.enrollment.export.wizard'].create({
            'period': '2026-09',
            'state': 'pending'
        })
        with self.assertRaises(UserError):
            wizard_empty.action_export_excel()
