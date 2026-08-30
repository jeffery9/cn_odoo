# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CnOutsourcingAssignment(models.Model):
    _name = 'cn.outsourcing.assignment'
    _description = 'Labor Outsourcing Assignment'

    contract_id = fields.Many2one('cn.outsourcing.contract', required=True, ondelete='cascade', string='Contract')
    employee_id = fields.Many2one('hr.employee', required=True, string='Worker')
    date_start = fields.Date(required=True, string='Start Date', default=fields.Date.today)
    date_end = fields.Date(string='End Date')

    company_id = fields.Many2one('res.company', string='Company', store=True, related='contract_id.company_id', readonly=True)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_end and rec.date_start > rec.date_end:
                raise ValidationError("Start date cannot exceed end date.")

    @api.constrains('employee_id', 'contract_id', 'date_start')
    def _check_worker_qualifications(self):
        from datetime import date
        
        for rec in self:
            contract = rec.contract_id
            employee = rec.employee_id
            
            # 1. Validate Age if birthday is configured
            if employee.birthday:
                b_date = fields.Date.from_string(employee.birthday)
                ref_date = fields.Date.from_string(rec.date_start) or date.today()
                
                # Compute age
                age = ref_date.year - b_date.year - ((ref_date.month, ref_date.day) < (b_date.month, b_date.day))
                
                if age < contract.age_min:
                    raise ValidationError(
                        f"Compliance Error: Worker {employee.name} (Age: {age}) is under "
                        f"the minimum age requirement of {contract.age_min} defined in contract '{contract.name}'."
                    )
                if age > contract.age_max:
                    raise ValidationError(
                        f"Compliance Error: Worker {employee.name} (Age: {age}) exceeds "
                        f"the maximum age requirement of {contract.age_max} defined in contract '{contract.name}'."
                    )
                    
            # 2. Validate Experience
            if employee.experience_years < contract.required_experience_years:
                raise ValidationError(
                    f"Compliance Error: Worker {employee.name} has only {employee.experience_years} years of experience, "
                    f"which fails to meet the contract's minimum requirement of {contract.required_experience_years} years."
                )

            # 3. Validate against Enterprise Blacklist
            domain = []
            if employee.barcode:
                domain.append(('barcode', '=', employee.barcode))
            if employee.identification_id:
                domain.append(('id_card_num', '=', employee.identification_id))
            if employee.mobile_phone:
                domain.append(('mobile', '=', employee.mobile_phone))
                
            if domain:
                if len(domain) > 1:
                    domain = ['|'] * (len(domain) - 1) + domain
                domain = [('active', '=', True)] + domain
                if len(domain) > 1:
                    domain = ['&'] + domain
                
                blacklist_rec = self.env['cn.outsourcing.blacklist'].search(domain, limit=1)
                if blacklist_rec:
                    raise ValidationError(
                        f"Compliance Violation: Worker {employee.name} is on the Enterprise Blacklist! "
                        f"Reason: {blacklist_rec.reason}. Assignment is strictly rejected."
                    )

            # 4. Check 10% Labor Dispatch workforce ratio limit under Chinese Labor Law
            self.env['cn.outsourcing.assignment'].flush_model()
            active_assignments_count = self.env['cn.outsourcing.assignment'].search_count([
                ('date_start', '<=', fields.Date.today()),
                '|', ('date_end', '=', False), ('date_end', '>=', fields.Date.today())
            ])
            active_outsourced_ids = self.env['cn.outsourcing.assignment'].search([
                ('date_start', '<=', fields.Date.today()),
                '|', ('date_end', '=', False), ('date_end', '>=', fields.Date.today())
            ]).mapped('employee_id.id')
            
            total_formal = self.env['hr.employee'].search_count([
                ('id', 'not in', active_outsourced_ids)
            ])
            
            total_workforce = total_formal + active_assignments_count
            if total_workforce > 0:
                ratio = (active_assignments_count / total_workforce) * 100.0
                if ratio > 10.0:
                    raise ValidationError(
                        f"Compliance Breach: Total labor dispatch workforce ratio is {ratio:.2f}%, "
                        f"which exceeds the Chinese Labor Law mandatory legal limit of 10.00%. "
                        f"Assignment of worker {employee.name} is blocked to avoid audit fines."
                    )
