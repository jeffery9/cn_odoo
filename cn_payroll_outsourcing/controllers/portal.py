# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class OutsourcingPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        agency_ids = [partner.id]
        if partner.parent_id:
            agency_ids.append(partner.parent_id.id)
            
        if 'outsourcing_contract_count' in counters:
            values['outsourcing_contract_count'] = request.env['cn.outsourcing.contract'].search_count([
                ('agency_id', 'in', agency_ids)
            ])
        if 'outsourcing_settlement_count' in counters:
            values['outsourcing_settlement_count'] = request.env['cn.outsourcing.settlement'].search_count([
                ('contract_id.agency_id', 'in', agency_ids)
            ])
        return values

    @http.route(['/my/outsourcing/contracts'], type='http', auth="user", website=True)
    def portal_my_contracts(self, **kw):
        partner = request.env.user.partner_id
        agency_ids = [partner.id]
        if partner.parent_id:
            agency_ids.append(partner.parent_id.id)
            
        contracts = request.env['cn.outsourcing.contract'].search([
            ('agency_id', 'in', agency_ids)
        ])
        values = self._prepare_portal_layout_values()
        values.update({
            'contracts': contracts,
            'page_name': 'outsourcing_contract',
        })
        return request.render("cn_payroll_outsourcing.portal_my_contracts", values)

    @http.route(['/my/outsourcing/settlements'], type='http', auth="user", website=True)
    def portal_my_settlements(self, **kw):
        partner = request.env.user.partner_id
        agency_ids = [partner.id]
        if partner.parent_id:
            agency_ids.append(partner.parent_id.id)
            
        settlements = request.env['cn.outsourcing.settlement'].search([
            ('contract_id.agency_id', 'in', agency_ids)
        ])
        values = self._prepare_portal_layout_values()
        values.update({
            'settlements': settlements,
            'page_name': 'outsourcing_settlement',
        })
        return request.render("cn_payroll_outsourcing.portal_my_settlements", values)
