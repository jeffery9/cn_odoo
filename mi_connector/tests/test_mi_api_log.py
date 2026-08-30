# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase

class TestMiApiLog(TransactionCase):

    def setUp(self):
        super().setUp()
        self.log_model = self.env['mi.api.log']

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
