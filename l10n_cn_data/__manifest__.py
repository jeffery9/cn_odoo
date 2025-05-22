# -*- coding: utf-8 -*-  
{  
    'name': '中国本地化基础数据',  
    'version': '1.0',  
    'category': 'Localization/China',  
    'summary': '中国企业常用的基础数据',  
    'description': """  
中国本地化基础数据  
=================  
  
此模块提供中国企业常用的基础数据：  
  
* 产品类别：原材料类、半成品类、产成品类等  
* 进口成本类别：到岸成本、国际运费、关税等  
* 仓储类别：高频率-大型、中频率-小型等  
* 包装类型：小纸箱、标准托盘、木箱等  
* 费用报销类别：差旅费、交通费、餐饮费等  
* 付款条件：30天、45天、60天等  
* 其他中国本地化基础数据  
  
适用于中国企业的日常业务管理。  
    """,  
    'author': 'genin IT, 亘盈信息技术, jeffery <jeffery9@gmail.com>',
    'website': 'http://www.geninit.cn', 
    'depends': [  
        'uom',
        'hr_expense',
        'stock',  
        'stock_account',  
        'stock_landed_costs',  
    ],  
    'data': [  
        'data/account_payment_terms.xml',  
        'data/product_categories.xml',  
        'data/product_landed_cost.xml',  
        'data/product_hr_expense.xml',  
        'data/storage_categories.xml',
        'data/package_types.xml'
        'data/uom.xml'
    ],  
    'demo': [],  
    'installable': True,  
    'application': False,  
    'auto_install': False,  
    'license': 'LGPL-3',  
}