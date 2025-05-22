# -*- coding: utf-8 -*-  
  
from odoo import models, fields, api, _  
  
class StockWarehouse(models.Model):  
    _inherit = 'stock.warehouse'  
      
    has_initialized_locations = fields.Boolean(  
        string="Has Initialized Locations",  
        compute="_compute_has_initialized_locations",  
        store=True,  
    )  
      
    @api.depends('view_location_id.child_ids')  
    def _compute_has_initialized_locations(self):  
        """Check if the warehouse has already initialized custom locations"""  
        for warehouse in self:  
            # Consider initialized if there are more than the default locations  
            # Default locations typically include input, output, stock, etc.  
            child_locations = self.env['stock.location'].search([  
                ('location_id', '=', warehouse.view_location_id.id)  
            ])  
            # Typically warehouses have at least 3 default locations  
            warehouse.has_initialized_locations = len(child_locations) > 3  
      
    def action_initialize_locations(self):  
        """Initialize common warehouse locations for Chinese businesses"""  
        self.ensure_one()  
          
        # Only proceed if not already initialized  
        if self.has_initialized_locations:  
            return  
              
        # Create common locations  
        common_locations = [  
            {'name': '原材料区', 'usage': 'internal', 'barcode_prefix': 'RM'},  
            {'name': '半成品区', 'usage': 'internal', 'barcode_prefix': 'WIP'},  
            {'name': '成品区', 'usage': 'internal', 'barcode_prefix': 'FG'},  
            {'name': '不良品区', 'usage': 'internal', 'barcode_prefix': 'DEF'},  
            {'name': '退货区', 'usage': 'internal', 'barcode_prefix': 'RET'},  
            {'name': '待检区', 'usage': 'internal', 'barcode_prefix': 'QC'},  
        ]  
          
        for loc_vals in common_locations:  
            self.env['stock.location'].create({  
                'name': loc_vals['name'],  
                'usage': loc_vals['usage'],  
                'location_id': self.view_location_id.id,  
                'company_id': self.company_id.id,  
                'barcode': f"{loc_vals['barcode_prefix']}-{self.code}",  
            })  
              
        # Invalidate cache to refresh the computed field  
        self.invalidate_recordset(['has_initialized_locations'])  
          
        return {  
            'type': 'ir.actions.client',  
            'tag': 'display_notification',  
            'params': {  
                'title': _('Success'),  
                'message': _('Warehouse locations have been initialized.'),  
                'sticky': False,  
                'type': 'success',  
            }  
        }