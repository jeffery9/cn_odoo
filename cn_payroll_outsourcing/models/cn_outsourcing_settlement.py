# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError

class CnOutsourcingSettlement(models.Model):
    _name = 'cn.outsourcing.settlement'
    _description = 'Outsourcing Monthly Settlement'

    name = fields.Char(required=True, string='Settlement Ref')
    contract_id = fields.Many2one('cn.outsourcing.contract', required=True, string='Contract')
    period = fields.Char(required=True, string='Period (YYYY-MM)')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved & Billed')
    ], string='State', default='draft')
    
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    subtotal_amount = fields.Float(compute='_compute_totals', string='Subtotal', store=True)
    vat_amount = fields.Float(compute='_compute_totals', string='VAT Amount', store=True)
    total_amount = fields.Float(compute='_compute_totals', string='Total Payable', store=True)
    
    vendor_bill_id = fields.Many2one('account.move', string='Vendor Bill', readonly=True)
    line_ids = fields.One2many('cn.outsourcing.settlement.line', 'settlement_id', string='Settlement Lines')

    @api.depends('line_ids.line_subtotal', 'contract_id.vat_rate')
    def _compute_totals(self):
        for record in self:
            subtotal = sum(record.line_ids.mapped('line_subtotal'))
            record.subtotal_amount = subtotal
            record.vat_amount = subtotal * record.contract_id.vat_rate
            record.total_amount = subtotal + record.vat_amount

    def action_generate_lines(self):
        self.ensure_one()
        from datetime import datetime, timedelta
        self.line_ids.unlink() # clear existing
        
        mode = self.contract_id.contract_type
        lines_data = []
        
        # Determine start/end date bounds of the period (YYYY-MM)
        year, month = map(int, self.period.split('-'))
        period_start = fields.Date.from_string(f"{year}-{month:02d}-01")
        if month == 12:
            period_end = fields.Date.from_string(f"{year}-12-31")
        else:
            period_end = fields.Date.from_string(f"{year}-{month+1:02d}-01") - timedelta(days=1)
        
        # Search for assignments active for this contract
        assignments = self.env['cn.outsourcing.assignment'].search([
            ('contract_id', '=', self.contract_id.id),
        ])
        
        for assignment in assignments:
            # Check overlap between assignment dates and the billing period
            start_overlap = max(period_start, assignment.date_start)
            end_overlap = period_end
            if assignment.date_end:
                end_overlap = min(period_end, assignment.date_end)
                
            if start_overlap > end_overlap:
                continue # No overlap this period
                
            employee = assignment.employee_id
            attendance = self.env['cn.attendance.summary'].search([
                ('employee_id', '=', employee.id),
                ('period', '=', self.period)
            ], limit=1)
            
            # 1. Base initialization
            line_vals = {
                'employee_id': employee.id,
                'attendance_hours': attendance.total_work_hours if attendance else 0.0,
            }
            
            # 2. Dispatch specific pulling
            if mode == 'dispatch':
                payslip = self.env['cn.payslip'].search([
                    ('employee_id', '=', employee.id),
                    ('period', '=', self.period),
                ], limit=1)
                
                # Fetch SIHF
                enrollment = self.env['mi.enrollment'].search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'enrolled')
                ], limit=1)
                
                # Extract IIT and Gross
                iit_amount = 0.0
                if payslip:
                    iit_line = payslip.line_ids.filtered(lambda l: l.code == 'IIT')
                    iit_amount = abs(iit_line.amount) if iit_line else 0.0
                
                line_vals.update({
                    'gross_salary': payslip.base_wage_amount if payslip else 0.0,
                    'sihf_employer': enrollment.amount_employer if enrollment else 0.0,
                    'sihf_employee': enrollment.amount_employee if enrollment else 0.0,
                    'iit_withheld': iit_amount,
                    'admin_fee': self.contract_id.admin_fee_per_head,
                })
            
            lines_data.append((0, 0, line_vals))
            
        self.write({'line_ids': lines_data})

    def action_approve_and_bill(self):
        self.ensure_one()
        if self.state != 'draft':
            return
            
        journal = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Vendor Bills Journal',
                'code': 'BILL',
                'type': 'purchase',
            })
            
        # Create vendor bill
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.contract_id.agency_id.id,
            'journal_id': journal.id,
            'invoice_date': fields.Date.today(),
            'ref': self.name,
            'invoice_line_ids': [
                (0, 0, {
                    'name': f"Labor Outsourcing Settlement for Period {self.period}",
                    'quantity': 1.0,
                    'price_unit': self.subtotal_amount,
                })
            ]
        })
        
        self.write({
            'state': 'approved',
            'vendor_bill_id': move.id,
        })


class CnOutsourcingSettlementLine(models.Model):
    _name = 'cn.outsourcing.settlement.line'
    _description = 'Outsourcing Monthly Settlement Line'

    settlement_id = fields.Many2one('cn.outsourcing.settlement', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', required=True, string='Worker')
    
    attendance_hours = fields.Float(default=0.0)
    gross_salary = fields.Float(default=0.0)
    sihf_employer = fields.Float(default=0.0)
    sihf_employee = fields.Float(default=0.0)
    iit_withheld = fields.Float(default=0.0)
    admin_fee = fields.Float(default=0.0)
    
    line_subtotal = fields.Float(compute='_compute_subtotal', store=True)

    @api.depends('settlement_id.contract_id.contract_type', 'attendance_hours', 'settlement_id.contract_id.hourly_rate', 'gross_salary', 'sihf_employer', 'sihf_employee', 'iit_withheld', 'admin_fee')
    def _compute_subtotal(self):
        for line in self:
            mode = line.settlement_id.contract_id.contract_type
            if mode == 'service_rate':
                line.line_subtotal = line.attendance_hours * line.settlement_id.contract_id.hourly_rate
            elif mode == 'dispatch':
                line.line_subtotal = line.gross_salary + line.sihf_employer + line.sihf_employee + line.iit_withheld + line.admin_fee
            else:
                line.line_subtotal = 0.0