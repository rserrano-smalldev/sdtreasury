# SD Treasury

Plataforma de gestión de tesorería (TMS) para clientes de SmallDev, conectada a Odoo 18 Enterprise
y diseñada para admitir otros ERPs en el futuro.

- Propuesta, arquitectura y fases: [`docs/PROPUESTA_ARQUITECTURA.md`](docs/PROPUESTA_ARQUITECTURA.md)
- Qué hace falta en AWS: [`docs/AWS_REQUISITOS.md`](docs/AWS_REQUISITOS.md)

## Estructura

| Carpeta | Contenido |
|---|---|
| `backend/` | API FastAPI, modelo canónico, conectores ERP, sincronización, migraciones (Alembic) |
| `frontend/` | App React + TypeScript (Vite) |
| `odoo/sd_treasury_connector/` | Addon ligero para Odoo 18 Enterprise |
| `deploy/mvp/` | Despliegue de bajo coste con Docker Compose en un servidor existente |
| `infra/` | Terraform de AWS para la arquitectura objetivo (pendiente) |

## Desarrollo local

Requisitos: Python 3.12+, Node 22, PostgreSQL 16 (o Docker).

```bash
docker compose up -d db
```

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

```bash
cd backend && SDT_MIGRATION_DATABASE_URL=postgresql+psycopg://sdtreasury:sdtreasury@localhost:5432/sdtreasury .venv/bin/alembic upgrade head
```

Crear un tenant de demostración con datos ficticios, sincronizarlo y activarle el módulo Liquidez
(la app se conecta como `sdt_app`, el rol sin privilegios sobre el que aplica RLS):

```bash
cd backend && export SDT_DATABASE_URL=postgresql+psycopg://sdt_app:sdt_app@localhost:5432/sdtreasury && .venv/bin/python -m app.cli create-tenant --name Demo --slug demo --kind demo && .venv/bin/python -m app.cli sync --tenant demo && .venv/bin/python -m app.cli grant --tenant demo --modules liquidity
```

```bash
cd backend && SDT_DATABASE_URL=postgresql+psycopg://sdt_app:sdt_app@localhost:5432/sdtreasury .venv/bin/uvicorn app.main:app --reload
```

```bash
cd frontend && npm install && npm run dev
```

Abrir http://localhost:5173 y entrar con el tenant `demo`.

### Conectar un Odoo real

```bash
cd backend && export ODOO_SMALLDEV_KEY=... && .venv/bin/python -m app.cli create-tenant --name "Small Development" --slug smalldev --odoo-url http://odoo.internal:8069 --odoo-db smalldev --odoo-login sdtreasury-api@smalldev.es --secret-ref env:ODOO_SMALLDEV_KEY
```

```bash
cd backend && .venv/bin/python -m app.cli test-connection --tenant smalldev && .venv/bin/python -m app.cli sync --tenant smalldev
```

En AWS, `--secret-ref aws:<nombre o ARN del secreto>`.

### Inicio de sesión desde Odoo

El addon firma un token de 60 segundos y de un solo uso con el secreto compartido y redirige a
`/sso/odoo#token=…`. La plataforma lo verifica (`app/core/sso.py`) y emite su propia sesión con los
roles (`Responsable` → admin, `Usuario` → viewer) y las sociedades permitidas del usuario en Odoo.

```bash
cd backend && .venv/bin/python -m app.cli set-sso-secret --tenant smalldev --secret-ref env:ODOO_SMALLDEV_SSO_SECRET
```

### Despliegue del MVP

Ver [`docs/AWS_REQUISITOS.md`](docs/AWS_REQUISITOS.md), sección 1, y `deploy/mvp/`.

### Tests

```bash
cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q
```

Los tests usan una base PostgreSQL real (`sdtreasury_test`) y se conectan como `sdt_app` para
comprobar el aislamiento entre tenants.
