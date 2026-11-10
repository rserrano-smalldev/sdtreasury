from odoo import fields, models

PARAM_URL = "sd_treasury.platform_url"
PARAM_TENANT = "sd_treasury.tenant"
PARAM_SECRET = "sd_treasury.sso_secret"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sd_treasury_platform_url = fields.Char(
        string="SD Treasury URL",
        config_parameter=PARAM_URL,
        help="Base URL of the SD Treasury web app, e.g. https://tesoreria.smalldev.es",
    )
    sd_treasury_tenant = fields.Char(
        string="SD Treasury tenant",
        config_parameter=PARAM_TENANT,
        help="Identifier of this client in SD Treasury (given by SmallDev).",
    )
    sd_treasury_sso_secret = fields.Char(
        string="SD Treasury login secret",
        config_parameter=PARAM_SECRET,
        groups="base.group_system",
        help="Shared secret used to sign logins into SD Treasury (given by SmallDev).",
    )
