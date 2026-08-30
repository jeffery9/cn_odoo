# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import io
import base64
import xlsxwriter

class MiEnrollmentExportWizard(models.TransientModel):
    _name = 'mi.enrollment.export.wizard'
    _description = 'Export Unified Medical Insurance Enrollment Sheet'

    @api.model
    def _default_period(self):
        return fields.Date.today().strftime('%Y-%m')

    period = fields.Char(string='Target Period', required=True, default=_default_period, help="Format: YYYY-MM")
    state = fields.Selection([
        ('draft', 'Draft / 草稿'),
        ('pending', 'Pending Declaration / 待申报'),
        ('enrolled', 'Enrolled / 已参保'),
    ], default='pending', string='Enrollment Status', required=True)
    
    file_data = fields.Binary(string='Exported Excel File', readonly=True)
    file_name = fields.Char(string='File Name', readonly=True)
    export_status = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done')
    ], default='draft', readonly=True)

    def action_export_excel(self):
        self.ensure_one()
        
        # Search for enrollments matching state
        domain = [('state', '=', self.state)]
        enrollments = self.env['mi.enrollment'].search(domain)
        
        # Filter by start_date's YYYY-MM format
        filtered_enrollments = enrollments.filtered(lambda e: e.start_date.strftime('%Y-%m') == self.period)
        
        if not filtered_enrollments:
            raise UserError(_("No enrollment records found for the period %s with status '%s'.") % (self.period, self.state))
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('社保公积金统一申报表')
        
        # Formats
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 16,
            'bg_color': '#1F4E79',
            'font_color': 'white'
        })
        
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 11,
            'bg_color': '#D9E1F2',
            'border': 1
        })
        
        cell_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 10,
            'border': 1
        })
        
        num_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'font_size': 10,
            'border': 1,
            'num_format': '#,##0.00'
        })

        # Set title row
        worksheet.merge_range('A1:I1', f'国家医保局/社保局统一申报导入报文 ({self.period})', title_format)
        worksheet.set_row(0, 35)
        
        # Set headers
        headers = [
            '序号', '员工姓名', '证件类型', '证件号码', '参保城市', 
            '申报缴费基数', '起保日期', '手机号码', '当前状态'
        ]
        for col_idx, header in enumerate(headers):
            worksheet.write(1, col_idx, header, header_format)
        worksheet.set_row(1, 25)
        
        # Write rows
        row_idx = 2
        for idx, rec in enumerate(filtered_enrollments, 1):
            worksheet.write(row_idx, 0, idx, cell_format)
            worksheet.write(row_idx, 1, rec.employee_id.name or '', cell_format)
            worksheet.write(row_idx, 2, '居民身份证', cell_format)
            worksheet.write(row_idx, 3, rec.employee_id.identification_id or '', cell_format)
            worksheet.write(row_idx, 4, rec.policy_id.region_id.name or '', cell_format)
            worksheet.write(row_idx, 5, rec.base_amount, num_format)
            worksheet.write(row_idx, 6, str(rec.start_date), cell_format)
            worksheet.write(row_idx, 7, rec.employee_id.mobile_phone or '', cell_format)
            worksheet.write(row_idx, 8, dict(rec._fields['state'].selection).get(rec.state, rec.state), cell_format)
            worksheet.set_row(row_idx, 20)
            row_idx += 1
            
        # Adjust column widths
        worksheet.set_column('A:A', 6)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 22)
        worksheet.set_column('E:E', 15)
        worksheet.set_column('F:F', 15)
        worksheet.set_column('G:G', 15)
        worksheet.set_column('H:H', 15)
        worksheet.set_column('I:I', 15)
        
        workbook.close()
        output.seek(0)
        
        file_bytes = output.read()
        self.write({
            'file_data': base64.b64encode(file_bytes),
            'file_name': f'SSB_Unified_Enrollment_{self.period}_{self.state}.xlsx',
            'export_status': 'done'
        })
        
        # Return form view to keep the dialog open for download
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
