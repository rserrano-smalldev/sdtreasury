# SD Treasury: notas para trabajar en el repo

- Producto SaaS multi-tenant de tesorería para clientes de SmallDev. ERP inicial: **Odoo 18 Enterprise**
  (los Odoo están en el AWS de SmallDev; acceso por su API externa). Otros ERPs: futuro.
- Plan y decisiones: `docs/PROPUESTA_ARQUITECTURA.md`. Documentación para el usuario en **español**;
  código, identificadores y comentarios en inglés.

## Reglas de arquitectura
- La lógica de negocio solo consume el **modelo canónico** (`backend/app/connectors/base.py`), nunca
  datos de Odoo directamente. Cada ERP/versión es un `ErpConnector`.
- El addon `odoo/sd_treasury_connector` es **delgado**: menú, permisos, webhooks y endpoints de escritura.
  Nada de lógica de tesorería en Odoo.
- Odoo es la fuente de verdad de los documentos contables; la plataforma, de categorías, previsiones,
  escenarios, remesas y financiación.
- **Multi-tenant con RLS**: toda tabla de un tenant hereda `TenantOwned`, se añade a `TENANT_TABLES`
  y su migración activa RLS (copiar el patrón de `0001`). La app se conecta como `sdt_app`
  (sin ser dueño de las tablas, sin BYPASSRLS). Las sesiones fijan `app.tenant_id`.
- **Cobro por sociedad y módulo**: cada endpoint de un módulo filtra o comprueba con
  `app/services/entitlements.py`. El rol `admin` del cliente nunca implica `platform_admin`.
- Secretos: solo referencias (`env:` / `aws:`) en base de datos.
- Autenticación: la plataforma emite sus propios JWT (HS256, `SDT_JWT_SECRET`). En el MVP se entra
  **desde Odoo** (`app/core/sso.py` ↔ `odoo/.../controllers/main.py`, mismo formato de token). Odoo
  solo puede conceder roles de tenant. El login de desarrollo solo existe con `SDT_ENV` dev/test.
- **Despliegue automático**: SmallDev conecta GitHub con AWS y se despliega al fusionar en `main`.
  Contrato del pipeline (imágenes, comandos, variables): `docs/DESPLIEGUE.md`. Mantenerlo al día
  si cambian procesos, variables o puertos. Nunca hacer push a `main`: todo por PR con el CI en verde.
- Las migraciones deben ser seguras de ejecutar al arrancar (bloqueo en `migrations/env.py`) y
  compatibles con la versión anterior del código mientras dura el despliegue.
- MVP barato: no añadir dependencias de servicios AWS de pago sin consultarlo.

## Comandos
- Backend: `cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest -q`
  (necesita PostgreSQL con los roles `sdtreasury` y `sdt_app`; ver `backend/docker/init-db.sql`).
- Frontend: `cd frontend && npm run build`.
