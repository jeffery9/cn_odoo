# -*- coding: utf-8 -*-
{
    "name": "China tax cllassification/中国税目",
    "summary": """
    tax base 

        """,
    "description": """

     

    """,
    "author": "genin IT, 亘盈信息技术, jeffery <jeffery9@gmail.com>",
    "website": "http://www.geninit.cn",
    "category": "Utility",
    "version": "0.1",
    "depends": ["account", "sale", "purchase"],
    "external_dependencies": {
        "python": [ ],
    },
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/views.xml",
        "views/templates.xml",
    ],
    "application": True,
    
    "license": "AGPL-3",
}
