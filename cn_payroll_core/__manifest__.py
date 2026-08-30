# -*- coding: utf-8 -*-
{
    'name': 'China Payroll Core',
    'version': '17.0.1.0.0',
    'summary': 'Chinese Salary and Attendance Adaptors for Odoo 17',
    'depends': [
        'base',
        'hr',
        'hr_attendance',
        'hr_holidays',
        'mail',
        'mi_core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_department_views.xml',
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
