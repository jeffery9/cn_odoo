# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json

import io
import xlsxwriter

class FinancialReportController(http.Controller):

    def _check_access(self):
        if not request.env.user.has_group('account.group_account_user'):
            raise http.JsonRequestError("You don't have access rights to this document.")

    @http.route('/api/financial_reports/<int:report_id>', type='json', auth='user')
    def get_report_data(self, report_id, **kwargs):
        self._check_access()
        report_obj = request.env['account.report'].browse(report_id)
        if not report_obj.exists():
            raise http.request.not_found()

        options = {
            'date_from': kwargs.get('date_from'),
            'date_to': kwargs.get('date_to'),
        }
        report_model = request.env['report.financial_report_viewer.financial_report']
        return report_model._get_report_data(report_obj, options)

    @http.route('/financial_reports/pdf/<string:report_type>', type='http', auth='user')
    def export_pdf(self, report_type, **kwargs):
        self._check_access()
        options = {
            'date_from': kwargs.get('date_from'),
            'date_to': kwargs.get('date_to'),
        }
        report_model = request.env['report.financial_report_viewer.financial_report']
        report_data = report_model._get_report_data(report_type, options)
        
        report_action = request.env.ref('financial_report_viewer.action_report_financial_statement')
        pdf_content, content_type = report_action._render_qweb_pdf(request.env.company.ids, data=report_data)
        
        pdf_http_headers = [
            ('Content-Type', content_type),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', f'attachment; filename={report_type}.pdf;')
        ]
        return request.make_response(pdf_content, headers=pdf_http_headers)

    @http.route('/financial_reports/excel/<string:report_type>', type='http', auth='user')
    def export_excel(self, report_type, **kwargs):
        self._check_access()
        options = {
            'date_from': kwargs.get('date_from'),
            'date_to': kwargs.get('date_to'),
        }
        report_model = request.env['report.financial_report_viewer.financial_report']
        report_data = report_model._get_report_data(report_type, options)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(report_type)

        report_model._write_excel_data(worksheet, report_data)

        workbook.close()
        output.seek(0)

        excel_http_headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Length', len(output.getvalue())),
            ('Content-Disposition', f'attachment; filename={report_type}.xlsx;')
        ]
        return request.make_response(output.getvalue(), headers=excel_http_headers)
