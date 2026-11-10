# Despliegue automático (GitHub → AWS)

SmallDev conecta GitHub con AWS. Este documento es el **contrato** entre el repositorio y el pipeline: qué se construye, cómo se arranca y qué configuración necesita. Sirve para CodePipeline/CodeBuild, GitHub Actions con OIDC, App Runner, ECS o Amplify.

## Flujo de ramas

- Claude desarrolla en ramas `claude/*` y **nunca hace push a `main`**.
- Cada cambio llega a `main` mediante una **pull request con el CI en verde** (`.github/workflows/ci.yml`: lint y tests del backend, build del frontend y comprobación del addon).
- **El pipeline despliega al fusionar en `main`.** Recomendado: que solo despliegue si el CI de ese commit ha pasado, y una aprobación manual si más adelante hay un entorno de producción aparte.

## Qué se construye

| Artefacto | Cómo | Notas |
|---|---|---|
| **Imagen backend** | `docker build backend/` (`backend/Dockerfile`) | Una imagen para la API, el scheduler y las migraciones |
| **Frontend, opción A: imagen** | `docker build frontend/` (`frontend/Dockerfile`, Caddy) | Sirve la app y reenvía `/api/*` a `SDT_API_UPSTREAM` |
| **Frontend, opción B: estático** | `cd frontend && npm ci && npm run build` → `frontend/dist/` | Para S3 + CloudFront o Amplify. Requiere *SPA fallback*: rutas desconocidas → `index.html` (incluida `/sso/odoo`) |

## Procesos en ejecución

| Proceso | Comando | Instancias | Recursos orientativos |
|---|---|---|---|
| API | Por defecto (uvicorn en `$PORT`, 8000 si no se indica) | 1 o más | 0,25 vCPU / 512 MB |
| Scheduler (sincroniza Odoo) | `python -m app.cli scheduler` | **Exactamente 1** | 0,25 vCPU / 384 MB |
| Frontend (opción A) | Por defecto (Caddy en el puerto 80) | 1 o más | 0,25 vCPU / 128 MB |

- **Health check:** `GET /health` devuelve 200 en la API. La imagen también trae un `HEALTHCHECK`.
- **Migraciones:** dos maneras, ambas seguras:
  - `SDT_RUN_MIGRATIONS=true` en la API: migra al arrancar. Si arrancan varias réplicas a la vez, un bloqueo de PostgreSQL las pone en fila.
  - O una tarea puntual antes del despliegue: `alembic upgrade head`, con la misma imagen.
- **Rutas con un balanceador delante:** `/api/*` y `/health` van a la API y el resto al frontend. Si el frontend se sirve aparte (opción B en otro dominio), compilar con `VITE_API_BASE=https://<api>` y poner ese origen en `SDT_CORS_ORIGINS`.

## Variables de entorno (backend: API y scheduler)

| Variable | Obligatoria | Valor |
|---|---|---|
| `SDT_ENV` | Sí | `prod` (o `staging`). Desactiva el login de desarrollo |
| `SDT_JWT_SECRET` | Sí | 32 o más caracteres aleatorios. La API **no arranca** sin ella fuera de dev |
| `SDT_DATABASE_URL` | Sí | `postgresql+psycopg://sdt_app:<pw>@<host>:5432/sdtreasury` (rol de la app, **sin** ser dueño de las tablas) |
| `SDT_MIGRATION_DATABASE_URL` | Para migrar | `postgresql+psycopg://sdtreasury:<pw>@<host>:5432/sdtreasury` (dueño del esquema) |
| `SDT_RUN_MIGRATIONS` | No | `true` para migrar al arrancar la API |
| `SDT_CORS_ORIGINS` | Si el frontend está en otro dominio | `["https://tesoreria.smalldev.es"]` |
| `SDT_SYNC_INTERVAL_SECONDS` | No | Por defecto `900` (15 min) |
| `PORT` | No | Puerto de la API (por defecto 8000) |
| `ODOO_<CLIENTE>_API_KEY`, `ODOO_<CLIENTE>_SSO_SECRET` | Por cliente | Secretos de cada Odoo, referenciados como `env:NOMBRE`. Alternativa: guardarlos en Secrets Manager y referenciarlos como `aws:<arn>`, con permiso `secretsmanager:GetSecretValue` en el rol de la tarea |

Frontend (opción A): `SDT_DOMAIN=:80` detrás de un balanceador (o el dominio, si Caddy termina TLS) y `SDT_API_UPSTREAM=<host:puerto de la API>`.

**Los secretos se inyectan desde el servicio de AWS**, nunca desde el repositorio.

## Base de datos

- PostgreSQL 13 o superior (recomendado 16).
- Una sola vez, como superusuario o usuario maestro de RDS: `deploy/mvp/setup-db.sql`. Crea la base `sdtreasury` y los roles `sdtreasury` (dueño) y `sdt_app` (la aplicación). **La aplicación no debe conectar como dueño ni como superusuario**: el aislamiento entre clientes (Row-Level Security) depende de ello.

## Red

- Los usuarios llegan por HTTPS público, normalmente redirigidos desde su Odoo.
- La API y el scheduler deben poder llamar a la **API de cada Odoo** (`/jsonrpc`), idealmente por red privada.

## Para que salga barato

- Lo que más encarece AWS en un MVP es el **NAT Gateway** (unos 35 $/mes) y los **balanceadores** (unos 20 $/mes cada uno). Si podéis, usad subredes públicas o la infraestructura que ya tenéis.
- Frontend estático en S3 + CloudFront o Amplify: prácticamente gratis con este tráfico.
- Para el backend vale cualquier cómputo pequeño (ECS sobre una EC2 existente, App Runner, Lightsail Containers). Basta con 1 instancia de la API y 1 del scheduler.

## Tras el primer despliegue (una vez por cliente)

Con una tarea puntual de la imagen backend (o ECS Exec):

```bash
python -m app.cli create-tenant --name "Small Development" --slug smalldev --odoo-url <url-interna-odoo> --odoo-db <base> --odoo-login sdtreasury-api@smalldev.es --secret-ref env:ODOO_SMALLDEV_API_KEY
```

```bash
python -m app.cli set-sso-secret --tenant smalldev --secret-ref env:ODOO_SMALLDEV_SSO_SECRET && python -m app.cli test-connection --tenant smalldev && python -m app.cli sync --tenant smalldev && python -m app.cli grant --tenant smalldev --modules liquidity
```

En Odoo, en *Contabilidad → Ajustes → SD Treasury*: la URL pública de la plataforma, el identificador `smalldev` y el mismo secreto de SSO.
