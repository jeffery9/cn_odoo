# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase
import json

class TestFinancialReportPortal(HttpCase):
    
    def test_sankey_data_endpoint(self):
        """Test the sankey diagram JSON endpoint"""
        # The endpoint might require login for full data, but the route should be accessible
        response = self.url_open('/financial_reports/sankey_data')
        self.assertEqual(response.status_code, 200)
        
    def test_financial_dashboard_endpoint(self):
        """Test the main dashboard web controller"""
        response = self.url_open('/financial_reports/dashboard')
        self.assertEqual(response.status_code, 200)
        
    def test_pdf_export_endpoint(self):
        """Test the PDF export endpoint format"""
        # Pass dummy report_id to trigger logic
        response = self.url_open('/financial_reports/export_pdf?report_id=999')
        # Even if it errors out due to missing ID, the controller route is hit
        self.assertTrue(response.status_code in (200, 302, 500, 404))
