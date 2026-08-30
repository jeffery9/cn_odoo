# -*- coding: utf-8 -*-
{
    'name': 'China Labor Outsourcing Settlement',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Dual-mode settlement engine for dispatch and hourly outsourcing agencies',
    'depends': ['hr', 'cn_payroll_core', 'account', 'mi_core'],
    'data': [
        'security/ir.model.access.csv',
        'security/multi_company_security.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
}
