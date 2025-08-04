{
    "name": "Financial Reports",
    "summary": "A dynamic financial reports for Odoo Community Edition.",
    "version": "1.0.0",
    "category": "Accounting/Accounting",
    "author": "genin IT, 亘盈信息技术, jeffery <jeffery9@gmail.com>",
    "website": "http://www.geninit.cn",
    "license": "AGPL-3",
    "depends": ["account", "analytic"],
    "data": [
        "security/ir.model.access.csv",
        "views/financial_report_views.xml",
        "views/menu_items.xml",
        "views/account_report_config_views.xml",
        "report/financial_report_pdf.xml",
        "report/financial_report_templates.xml",
        "data/balance_sheet_template.xml",
        "data/income_statement_template.xml",
        "data/cash_flow_template.xml",
        "data/ir_cron_data.xml",
        "data/report_menu_entries.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "financial_reports/static/src/css/financial_reports.css",
            "financial_reports/static/src/js/financial_report_viewer.js",
            "financial_reports/static/src/js/report_components.js",
            "financial_reports/static/src/js/chart_integration.js",
        ],
        "web.assets_qweb": [
            "financial_reports/static/src/xml/templates.xml",
        ],
    },
    "external_dependencies": {
        "python": ["xlsxwriter"],
    },
    "installable": True,
    "application": True,
}
