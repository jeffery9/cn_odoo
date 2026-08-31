# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase

class TestOutsourcingPortal(HttpCase):
    
    def test_portal_outsourcing_dashboard_access(self):
        """Test that the main outsourcing portal dashboard renders without crashing"""
        # Access the page as a public user (should redirect to login or show empty portal)
        response = self.url_open('/my/outsourcing')
        self.assertEqual(response.status_code, 200)
        
    def test_portal_contract_list_access(self):
        """Test contract list endpoint"""
        response = self.url_open('/my/outsourcing/contracts')
        self.assertEqual(response.status_code, 200)

    def test_portal_worker_list_access(self):
        """Test worker assignment list endpoint"""
        response = self.url_open('/my/outsourcing/workers')
        self.assertEqual(response.status_code, 200)
        
    def test_portal_settlement_list_access(self):
        """Test settlement list endpoint"""
        response = self.url_open('/my/outsourcing/settlements')
        self.assertEqual(response.status_code, 200)
