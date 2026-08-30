# -*- coding: utf-8 -*-
from odoo import models, api, _
import json

class MiPolicy(models.Model):
    _inherit = 'mi.policy'

    def action_sync_policy_bases(self):
        self.ensure_one()
        
        # Simulate querying local government municipal database
        new_limits = {
            'medical': {'min': 6800.0, 'max': 36500.0},
            'pension': {'min': 6500.0, 'max': 34500.0},
            'housing_fund': {'min': 3500.0, 'max': 38000.0},
        }
        
        updated = False
        payload_changes = []
        for line in self.line_ids:
            if line.insurance_type in new_limits:
                limits = new_limits[line.insurance_type]
                old_min, old_max = line.base_min, line.base_max
                line.write({
                    'base_min': limits['min'],
                    'base_max': limits['max']
                })
                updated = True
                payload_changes.append({
                    'insurance_type': line.insurance_type,
                    'old_limits': {'min': old_min, 'max': old_max},
                    'new_limits': limits
                })
        
        # Log transaction
        tx_id = f"TX-POLICY-SYNC-{self.id}"
        self.env['mi.api.log'].create({
            'name': tx_id,
            'request_data': json.dumps({'policy_id': self.id, 'region': self.region_id.name}, ensure_ascii=False),
            'response_data': json.dumps({'status': 'synced', 'changes': payload_changes}, ensure_ascii=False),
            'state': 'success',
            'res_model': 'mi.policy',
            'res_id': self.id
        })
        
        return updated
