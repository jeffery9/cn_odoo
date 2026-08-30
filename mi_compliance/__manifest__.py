# -*- coding: utf-8 -*-
{
    'name': 'Medical Insurance Compliance',
    'version': '17.0.1.0.0',
    'summary': 'Compliance risk assessment and penalty computations',
    'depends': ['mi_core', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/report_evidence.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
