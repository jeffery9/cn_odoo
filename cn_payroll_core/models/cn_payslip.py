# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

class CnPayslip(models.Model):
    _name = 'cn.payslip'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Employee Payslip'

    employee_id = fields.Many2one('hr.employee', required=True, tracking=True)
    structure_id = fields.Many2one('cn.salary.structure', required=True, tracking=True)
    period = fields.Char(required=True, tracking=True, help="Format: YYYY-MM")
    base_wage_amount = fields.Float(string="Base Wage", required=True)
    local_minimum_wage = fields.Float(string='Local Monthly Minimum Wage', default=2690.0)
    
    line_ids = fields.One2many('cn.payslip.line', 'slip_id', string='Salary Lines', cascade='delete')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid')
    ], default='draft', required=True, tracking=True)
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True, copy=False)

    def _get_eval_context(self):
        # Locate attendance summary for variables
        summary = self.env['cn.attendance.summary'].search([
            ('employee_id', '=', self.employee_id.id),
            ('period', '=', self.period)
        ], limit=1)

        late_minutes = summary.late_minutes if summary else 0
        personal_leave_days = summary.personal_leave_days if summary else 0.0
        sick_leave_days = summary.sick_leave_days if summary else 0.0
        absent_days = summary.absent_days if summary else 0.0

        # Retrieve mi enrollment record
        enrollment = self.env['mi.enrollment'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['pending', 'enrolled']),
        ], limit=1)
        sihf_personal = enrollment.amount_employee if enrollment else 0.0
        sihf_employer = enrollment.amount_employer if enrollment else 0.0

        # Compute pre-makeup net pay (base wage minus personal SIHF)
        pre_net = self.base_wage_amount - sihf_personal
        makeup = max(0.0, self.local_minimum_wage - pre_net)

        return {
            'BASIC': self.base_wage_amount,
            'late_minutes': late_minutes,
            'personal_leave_days': personal_leave_days,
            'sick_leave_days': sick_leave_days,
            'absent_days': absent_days,
            'SIHF_PERSONAL': sihf_personal,
            'SIHF_EMPLOYER': sihf_employer,
            'MINIMUM_WAGE_MAKEUP': makeup,
            'result': 0.0,
        }

    def action_compute_sheet(self):
        self.ensure_one()
        self.line_ids.unlink()

        # Gather base evaluation variables dictionary
        eval_context = self._get_eval_context()

        # Evaluate in items order
        for item in self.structure_id.item_ids:
            amount = 0.0
            if item.code == 'BASIC':
                amount = self.base_wage_amount
            elif item.python_code:
                local_context = dict(eval_context)
                try:
                    safe_eval(item.python_code, globals_dict={}, locals_dict=local_context, mode='exec', nocopy=True)
                    amount = local_context.get('result', 0.0)
                except Exception as e:
                    raise ValidationError(_("Error evaluating salary item %s: %s") % (item.name, e))
            
            # Record result back in evaluation context for subsequent items
            eval_context[item.code] = amount
            
            self.env['cn.payslip.line'].create({
                'slip_id': self.id,
                'item_id': item.id,
                'code': item.code,
                'amount': amount,
            })

    def action_post_journal_entry(self):
        self.ensure_one()
        if self.move_id:
            raise ValidationError(_("Accounting entry has already been generated for this payslip!"))

        move_lines = []
        # Locate mapped journal on lines, fall back to general journal
        journal = self.line_ids.mapped('item_id.journal_id')
        if not journal:
            journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        else:
            journal = journal[0]

        if not journal:
            raise ValidationError(_("Please configure an accounting journal to generate salary postings!"))

        for line in self.line_ids:
            if line.amount == 0.0:
                continue
            item = line.item_id
            if not item.debit_account_id or not item.credit_account_id:
                continue

            amt = abs(line.amount)
            if line.amount > 0:
                move_lines.append((0, 0, {
                    'name': f"{self.employee_id.name} - {item.name}",
                    'account_id': item.debit_account_id.id,
                    'debit': amt,
                    'credit': 0.0,
                }))
                move_lines.append((0, 0, {
                    'name': f"{self.employee_id.name} - {item.name}",
                    'account_id': item.credit_account_id.id,
                    'debit': 0.0,
                    'credit': amt,
                }))
            else:
                move_lines.append((0, 0, {
                    'name': f"{self.employee_id.name} - {item.name}",
                    'account_id': item.credit_account_id.id,
                    'debit': amt,
                    'credit': 0.0,
                }))
                move_lines.append((0, 0, {
                    'name': f"{self.employee_id.name} - {item.name}",
                    'account_id': item.debit_account_id.id,
                    'debit': 0.0,
                    'credit': amt,
                }))

        if move_lines:
            move = self.env['account.move'].create({
                'journal_id': journal.id,
                'date': fields.Date.today(),
                'ref': f"Payroll {self.period} - {self.employee_id.name}",
                'move_type': 'entry',
                'line_ids': move_lines,
            })
            # Post the journal entry directly to update ledgers
            move.action_post()
            self.write({
                'move_id': move.id,
                'state': 'approved',
            })

class CnPayslipLine(models.Model):
    _name = 'cn.payslip.line'
    _description = 'Payslip Salary Line'

    slip_id = fields.Many2one('cn.payslip', ondelete='cascade', required=True)
    item_id = fields.Many2one('cn.salary.item', required=True)
    code = fields.Char(related='item_id.code', store=True)
    amount = fields.Float()
