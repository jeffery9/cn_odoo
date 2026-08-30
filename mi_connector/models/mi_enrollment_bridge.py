# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import uuid
import json

class MiEnrollment(models.Model):
    _inherit = 'mi.enrollment'

    declaration_state = fields.Selection([
        ('draft', 'Not Declared'),
        ('submitting', 'Declaration Pending'),
        ('enrolled', 'Declaration Succeeded'),
        ('rejected', 'Declaration Rejected')
    ], default='draft', string='Declaration Status', tracking=True)
    declaration_receipt_id = fields.Char(string='Receipt ID', readonly=True, copy=False)

    def action_submit_declaration(self):
        self.ensure_one()
        if self.state != 'pending':
            self.write({'state': 'pending'})
        
        # Create a unique transaction code
        tx_id = f"TX-SSB-{uuid.uuid4().hex[:12].upper()}"
        
        # Build the payload
        payload = {
            'citizen_id': self.employee_id.identification_id or f"ID-{self.employee_id.id:06d}",
            'employee_name': self.employee_id.name,
            'base_amount': self.base_amount,
            'start_date': str(self.start_date),
            'insurance_lines': [
                {
                    'insurance_type': line.insurance_type_group,
                    'base_amount': line.base_amount
                } for line in self.line_ids
            ]
        }
        
        # Create API Log
        self.env['mi.api.log'].create({
            'name': tx_id,
            'request_data': json.dumps(payload, ensure_ascii=False),
            'response_data': json.dumps({'status': 'processing', 'message': 'Declaration uploaded to SSB. Awaiting processing.'}, ensure_ascii=False),
            'state': 'pending',
            'res_model': 'mi.enrollment',
            'res_id': self.id
        })
        
        # Transition state
        self.write({
            'declaration_state': 'submitting',
            'declaration_receipt_id': tx_id
        })
        
        # Log to Chatter
        self.message_post(body=_(
            "Medical Insurance declaration uploaded successfully to State SSB Bureau.<br/>"
            "<b>Transaction ID:</b> %s<br/>"
            "<b>Status:</b> Awaiting asynchronous approval.",
            tx_id
        ))
        return True

    @api.model
    def cron_poll_mi_declaration_status(self):
        """
        Cron polling daemon:
        Scans for pending submissions, queries mock SSB gateway (85% success, 15% fail),
        and updates Odoo records accordingly.
        """
        import random
        pending_logs = self.env['mi.api.log'].search([
            ('state', '=', 'pending'),
            ('res_model', '=', 'mi.enrollment')
        ])
        for log in pending_logs:
            enrollment = self.env['mi.enrollment'].browse(log.res_id)
            if not enrollment.exists():
                log.write({
                    'state': 'failed',
                    'response_data': '{"error": "Associated enrollment record deleted"}'
                })
                continue
            
            # Simulate mock gateway check
            is_success = True
            error_msg = ""
            
            if "Reject" in enrollment.employee_id.name or enrollment.base_amount > 50000.0:
                is_success = False
                error_msg = "Declaration rejected: Citizen ID mismatch or base wage exceeds municipal limits."
            else:
                if self.env.context.get('test_force_fail'):
                    is_success = False
                    error_msg = "Declaration rejected by SSB validator: Document upload signature mismatch."
                elif self.env.context.get('test_force_success'):
                    is_success = True
                else:
                    is_success = random.random() < 0.85
                    error_msg = "Declaration rejected: citizen status validation failed at Bureau level."

            if is_success:
                log.write({
                    'state': 'success',
                    'response_data': json.dumps({'status': 'approved', 'registry_code': f"SSB-REG-{uuid.uuid4().hex[:8].upper()}"}, ensure_ascii=False)
                })
                enrollment.write({
                    'declaration_state': 'enrolled',
                    'state': 'enrolled'
                })
                enrollment.message_post(body=_(
                    "<b>State SSB Bureau Declaration Approved!</b><br/>"
                    "The employee's Medical Insurance enrollment is now active.<br/>"
                    "<b>Registration Code:</b> %s",
                    json.loads(log.response_data).get('registry_code', 'N/A')
                ))
            else:
                log.write({
                    'state': 'failed',
                    'response_data': json.dumps({'status': 'rejected', 'reason': error_msg}, ensure_ascii=False)
                })
                enrollment.write({
                    'declaration_state': 'rejected',
                    'state': 'draft' # Revert to draft for correction
                })
                enrollment.message_post(body=_(
                    "<b>State SSB Bureau Declaration REJECTED.</b><br/>"
                    "<b>Reason:</b> <span style='color: red;'>%s</span><br/>"
                    "Enrollment reverted to Draft state for HR correction.",
                    error_msg
                ))
