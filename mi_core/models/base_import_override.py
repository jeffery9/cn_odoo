# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class Import(models.TransientModel):
    _inherit = 'base_import.import'

    def execute_import(self, fields, columns, options, dryrun=False):
        results = super(Import, self).execute_import(fields, columns, options, dryrun=dryrun)
        if self.res_model == 'mi.enrollment':
            messages = results.setdefault('messages', [])
            seen_active_employees = set()
            try:
                input_file_data, import_fields = self._convert_import_data(fields, options)
                input_file_data = self._parse_import_data(input_file_data, import_fields, options)
            except Exception:
                return results

            employee_idx = next((i for i, f in enumerate(fields) if f and f.startswith('employee_id')), None)
            policy_idx = next((i for i, f in enumerate(fields) if f and f.startswith('policy_id')), None)
            base_amount_idx = next((i for i, f in enumerate(fields) if f and f.startswith('base_amount')), None)
            state_idx = next((i for i, f in enumerate(fields) if f and f.startswith('state')), None)
            line_group_idx = next((i for i, f in enumerate(fields) if f and f.startswith('line_ids/insurance_type_group')), None)
            line_base_idx = next((i for i, f in enumerate(fields) if f and f.startswith('line_ids/base_amount')), None)

            current_policy = self.env['mi.policy']

            for row_idx, row in enumerate(input_file_data):
                # Resolve current parent policy
                if policy_idx is not None and len(row) > policy_idx and row[policy_idx]:
                    policy_val = row[policy_idx]
                    current_policy = self._resolve_relation('mi.policy', policy_val)

                # 1. Main Base Bounds Validation
                if base_amount_idx is not None and len(row) > base_amount_idx and row[base_amount_idx]:
                    base_amount_val = row[base_amount_idx]
                    try:
                        base_amount = float(base_amount_val) if base_amount_val is not None else 0.0
                    except (ValueError, TypeError):
                        base_amount = 0.0
                    if current_policy:
                        for line in current_policy.line_ids:
                            if base_amount < line.base_min:
                                messages.append({
                                    'type': 'error',
                                    'message': _("The base_amount (%s) is below policy lower limit (%s) for policy %s.") % (base_amount, line.base_min, current_policy.name),
                                    'record': row_idx,
                                    'field': 'base_amount',
                                })
                                results['ids'] = False
                            elif base_amount > line.base_max:
                                messages.append({
                                    'type': 'error',
                                    'message': _("The base_amount (%s) is above policy upper limit (%s) for policy %s.") % (base_amount, line.base_max, current_policy.name),
                                    'record': row_idx,
                                    'field': 'base_amount',
                                })
                                results['ids'] = False

                # 2. Sub-line Base Bounds Validation
                if line_group_idx is not None and line_base_idx is not None:
                    if len(row) > line_group_idx and len(row) > line_base_idx and row[line_group_idx] and row[line_base_idx]:
                        group_val = row[line_group_idx]
                        base_val = row[line_base_idx]
                        try:
                            line_base = float(base_val)
                        except (ValueError, TypeError):
                            line_base = 0.0
                        
                        if current_policy:
                            matched_types = []
                            if group_val == 'pension':
                                matched_types = ['pension']
                            elif group_val == 'medical':
                                matched_types = ['medical']
                            elif group_val in ['housing_fund', 'housing_fund_sep']:
                                matched_types = ['housing_fund', 'supp_housing_fund']
                            elif group_val == 'social_security':
                                matched_types = ['pension', 'medical', 'unemployment', 'injury', 'maternity']

                            for line in current_policy.line_ids:
                                if line.insurance_type in matched_types:
                                    if line_base < line.base_min:
                                        messages.append({
                                            'type': 'error',
                                            'message': _("The sub-line base (%s) is below policy lower limit (%s) for %s under policy %s.") % (line_base, line.base_min, line.insurance_type, current_policy.name),
                                            'record': row_idx,
                                            'field': 'line_ids/base_amount',
                                        })
                                        results['ids'] = False
                                    elif line_base > line.base_max:
                                        messages.append({
                                            'type': 'error',
                                            'message': _("The sub-line base (%s) is above policy upper limit (%s) for %s under policy %s.") % (line_base, line.base_max, line.insurance_type, current_policy.name),
                                            'record': row_idx,
                                            'field': 'line_ids/base_amount',
                                        })
                                        results['ids'] = False

                # 3. Active Overlap Validation
                if employee_idx is not None and len(row) > employee_idx and row[employee_idx]:
                    employee_val = row[employee_idx]
                    state_val = row[state_idx] if state_idx is not None and len(row) > state_idx and row[state_idx] else 'draft'
                    employee = self._resolve_relation('hr.employee', employee_val)
                    if employee and state_val in ['pending', 'enrolled']:
                        duplicates = self.env['mi.enrollment'].search([
                            ('employee_id', '=', employee.id),
                            ('state', 'in', ['pending', 'enrolled'])
                        ])
                        if duplicates:
                            messages.append({
                                'type': 'error',
                                'message': _("This employee (%s) already has an active or pending enrollment record!") % employee.name,
                                'record': row_idx,
                                'field': 'employee_id',
                            })
                            results['ids'] = False
                        elif employee.id in seen_active_employees:
                            messages.append({
                                'type': 'error',
                                'message': _("This employee (%s) already has an active or pending enrollment record in this import file!") % employee.name,
                                'record': row_idx,
                                'field': 'employee_id',
                            })
                            results['ids'] = False
                        seen_active_employees.add(employee.id)
        return results

    def _resolve_relation(self, model_name, val):
        if not val:
            return self.env[model_name]
        if isinstance(val, int):
            return self.env[model_name].browse(val)
        if isinstance(val, str):
            val_clean = val.strip()
            if not val_clean:
                return self.env[model_name]
            if val_clean.isdigit():
                return self.env[model_name].browse(int(val_clean))
            if '.' in val_clean:
                try:
                    record = self.env.ref(val_clean, raise_if_not_found=False)
                    if record and record._name == model_name:
                        return record
                except Exception:
                    pass
            records = self.env[model_name].name_search(name=val_clean, operator='=')
            if records:
                return self.env[model_name].browse(records[0][0])
            if 'name' in self.env[model_name]._fields:
                record = self.env[model_name].search([('name', '=', val_clean)], limit=1)
                if record:
                    return record
        return self.env[model_name]
