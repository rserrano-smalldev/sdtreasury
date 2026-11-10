from odoo import api, fields, models

PARAM_URL = "sd_treasury.platform_url"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sd_treasury_platform_url = fields.Char(
        string="SD Treasury URL",
        config_parameter=PARAM_URL,
        help="Base URL of the SD Treasury web app, e.g. https://tesoreria.smalldev.es",
    )


class SdTreasuryLauncher(models.AbstractModel):
    _name = "sd.treasury.launcher"
    _description = "Opens the SD Treasury web app"

    @api.model
    def sd_treasury_open(self):
        url = self.env["ir.config_parameter"].sudo().get_param(PARAM_URL)
        if not url:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "warning",
                    "message": self.env._(
                        "Configure the SD Treasury URL in Accounting settings first."
                    ),
                },
            }
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}
