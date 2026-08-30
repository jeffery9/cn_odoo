# -*- coding: utf-8 -*-  
  
from odoo import models, fields, api, _  
from odoo.exceptions import UserError  
from datetime import datetime  
import calendar  
  
class AccountMove(models.Model):  
    _inherit = 'account.move'  
      
    invoice_currency_rate = fields.Float(  
        string='Invoice Currency Rate',  
        digits=(12, 6),  
        default=1.0,  
    )

    inverse_currency_rate = fields.Float(  
        string='Inverse Currency Rate',  
        compute='_compute_inverse_currency_rate',  
        digits=(12, 6),  
        readonly=True,  
    )  
      
    @api.depends('invoice_currency_rate')  
    def _compute_inverse_currency_rate(self):  
        for move in self:  
            if move.invoice_currency_rate and move.invoice_currency_rate != 0:  
                move.inverse_currency_rate = 1.0 / move.invoice_currency_rate  
            else:  
                move.inverse_currency_rate = 0.0

    def _check_currency_rate_current_month(self):  
        """检查外币发票的汇率是否在当月1号到开票日期之间"""  
        self.ensure_one()  
        if self.currency_id == self.company_id.currency_id:  
            # 如果使用公司本位币，无需检查  
            return True  
              
        # 获取当月1号和发票日期  
        invoice_date = self.invoice_date or self.date or fields.Date.context_today(self)  
        first_day_of_month = invoice_date.replace(day=1)  
          
        # 查找该币种在当月1号到发票日期之间的最新汇率  
        latest_rate = self.env['res.currency.rate'].search([  
            ('currency_id', '=', self.currency_id.id),  
            ('company_id', '=', self.company_id.id),  
            ('name', '>=', first_day_of_month),  
            ('name', '<=', invoice_date)  
        ], order='name desc', limit=1)  
          
        if not latest_rate:  
            raise UserError(_(  
                "未找到币种 %s 在当月1号(%s)到发票日期(%s)之间的汇率记录。"  
                "请在确认此发票前更新汇率。"  
            ) % (self.currency_id.name, first_day_of_month, invoice_date))  
              
        return True  
      
    def action_post(self):  
        """重写以添加汇率验证"""  
        for move in self.filtered(lambda m: m.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')):  
            # 只检查外币发票  
            if move.currency_id != move.company_id.currency_id:  
                move._check_currency_rate_current_month()  
        return super(AccountMove, self).action_post()  
      
    def action_refresh_currency_rate(self):  
        """手动刷新汇率，使用发票日期"""  
        self.ensure_one()  
        if self.currency_id == self.company_id.currency_id:  
            # 如果使用公司本位币，无需更新  
            return {  
                'type': 'ir.actions.client',  
                'tag': 'display_notification',  
                'params': {  
                    'title': _('提示'),  
                    'message': _('本位币发票无需更新汇率。'),  
                    'sticky': False,  
                    'type': 'info',  
                }  
            }  
              
        # 使缓存失效并触发重新计算  
        self.invalidate_recordset(['amount_total', 'amount_residual', 'invoice_currency_rate']) 
        self._compute_amount()
          
        return {  
            'type': 'ir.actions.client',  
            'tag': 'display_notification',  
            'params': {  
                'title': _('成功'),  
                'message': _('汇率已按发票日期更新为最新值。'),  
                'sticky': False,  
                'type': 'success',  
            }  
        }