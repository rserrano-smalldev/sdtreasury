{
    "name": "SD Treasury Connector",
    "summary": "Connects Odoo with the SD Treasury cash management platform",
    "version": "18.0.0.1.0",
    "category": "Accounting/Accounting",
    "author": "Small Development SL",
    "website": "https://smalldev.es",
    "license": "OPL-1",
    "depends": ["account_accountant"],  # Odoo Enterprise
    "data": [
        "security/security.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
