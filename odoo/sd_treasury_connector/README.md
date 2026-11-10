# SD Treasury Connector (Odoo 18 Enterprise)

Thin addon. It holds **no business logic**; the SD Treasury platform reads Odoo through the
external API.

What it does today:
- Adds **Contabilidad → Tesorería**, which opens the SD Treasury web app (URL configured in
  *Contabilidad → Ajustes → SD Treasury*).
- Defines two groups:
  - *SD Treasury / Usuario*: users who see the menu.
  - *SD Treasury / API de la plataforma*: assign it to the **technical user** whose API key
    the platform uses. Implies read-only accounting access.

Coming next: SSO from Odoo into the platform, change webhooks, payment write-back.

## Setting up a client

1. Install the module.
2. Create the technical user (e.g. `sdtreasury-api@<client>`), give it the
   *API de la plataforma* group and access to every company to be synced.
3. Generate an API key for that user (Preferences → Account security → New API key) and
   store it in AWS Secrets Manager.
4. Register the tenant in the platform (`python -m app.cli create-tenant …`).
