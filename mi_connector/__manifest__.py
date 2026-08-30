# -*- coding: utf-8 -*-
{
    'name': 'Medical Insurance Connector',
    'version': '17.0.1.0.0',
    'summary': 'Asynchronous API Logging and Communication Isolation',
    'description': """
Medical Insurance Connector
===========================
Provides robust and isolated external communications for the Medical Insurance (MI) system,
including asynchronous API logging, transaction history recording, and payload auditing.
    """,
    'category': 'Human Resources/Payroll',
    'author': 'genin IT, 亘盈信息技术, jeffery <jeffery9@gmail.com>',
    'website': 'http://www.geninit.cn',
    'license': 'LGPL-3',
    'depends': ['base', 'mi_core'],
    'data': [
        'security/ir.model.access.csv',
        'views/mi_connector_views.xml',
        'wizards/mi_enrollment_export_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
