# Qué necesito en AWS

Hay dos etapas:
1. **MVP a coste 0 €**: reutilizar el servidor y el PostgreSQL que ya tenéis. Es lo que montamos ahora.
2. **Arquitectura objetivo** (ECS, RDS, Cognito…): cuando haya varios clientes de pago o se necesite alta disponibilidad.

El código es el mismo en las dos: solo cambia dónde se ejecuta.

---

## 1. MVP de bajo coste (recomendado ahora)

### Cómo queda

```
           Internet (HTTPS, Let's Encrypt)
                     │
┌────────────── EC2 existente (p. ej. la del Odoo de Small Development) ──────────────┐
│  docker compose (deploy/mvp)                                                        │
│   ├─ web        Caddy: sirve la app React, TLS automático, proxy /api → api         │
│   ├─ api        FastAPI (2 workers, ≤512 MB)                                        │
│   └─ scheduler  sincroniza Odoo cada 15 min (≤384 MB)                               │
│                                                                                     │
│  Odoo 18 (ya existe) ◄── API JSON-RPC por red local/privada                         │
│  PostgreSQL (ya existe) ◄── base de datos nueva "sdtreasury" con sus propios roles  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Por qué cuesta 0 € (o casi)

| Pieza del plan objetivo | Coste aprox. | En el MVP | Coste |
|---|---|---|---|
| ECS Fargate (api + worker) | ~25 $/mes | Contenedores Docker en una EC2 existente | 0 € |
| RDS PostgreSQL | ~30 $/mes | Base de datos nueva en el PostgreSQL existente | 0 € |
| NAT Gateway | ~35 $/mes | No hace falta (mismo servidor o misma VPC) | 0 € |
| ALB + WAF | ~25 $/mes | Caddy (o vuestro nginx actual) | 0 € |
| Transit Gateway o peering | ~40 $/mes | No hace falta (mismo servidor o misma VPC) | 0 € |
| Cognito | 0–? $ | **Inicio de sesión desde Odoo** (SSO ya implementado) | 0 € |
| Secrets Manager | 0,40 $/secreto | Fichero `.env` en el servidor (permisos 600) | 0 € |
| SQS + EventBridge | céntimos | Contenedor `scheduler` con un bucle | 0 € |
| SES | céntimos | El servidor de correo saliente que ya usa Odoo (Fase 1) | 0 € |
| Certificado TLS | 0 € (ACM) | Let's Encrypt automático con Caddy | 0 € |
| Copias de seguridad | — | `pg_dump` diario a S3 (`backup.sh`) | < 1 €/mes |

Consumo esperado: unos 300–600 MB de RAM y CPU casi nula fuera de las sincronizaciones.

> **Si el servidor de Odoo va justo de recursos:** una EC2 `t4g.small` aparte cuesta unos 12–15 $/mes, y una `t4g.micro` unos 6 $/mes. Las cuentas nuevas de AWS tienen además créditos de capa gratuita.

### Lo que necesito de vosotros

1. **Qué servidor usamos.** Por ejemplo, la EC2 del Odoo de Small Development. Necesito saber:
   - si tiene Docker (o se puede instalar);
   - cuánta RAM libre tiene;
   - si delante de Odoo hay ya un nginx o un ALB en los puertos 80/443. Si lo hay, Caddy escucha en otro puerto y añadís un bloque `server` en vuestro nginx.
2. **PostgreSQL:** ejecutar `deploy/mvp/setup-db.sql` como superusuario. Crea la base de datos `sdtreasury` y los roles `sdtreasury` (dueño) y `sdt_app` (la aplicación).
3. **DNS:** un registro A o CNAME, por ejemplo `tesoreria.smalldev.es`, apuntando al servidor (o a vuestro proxy).
4. **Odoo de Small Development:**
   - Instalar el addon `odoo/sd_treasury_connector`.
   - Crear el usuario técnico `sdtreasury-api@smalldev.es`, con el grupo *SD Treasury / API de la plataforma* y una **API key**.
   - Asignar *SD Treasury / Responsable* a quien vaya a usar la tesorería.
5. **Rellenar `deploy/mvp/.env`** en el servidor (plantilla en `.env.example`) con la API key y el secreto de SSO. Los secretos van en ese fichero, **no por chat**.
6. **Opcional:** un bucket S3 para las copias de seguridad.

### Puesta en marcha (cuando tengamos lo anterior)

```bash
cd deploy/mvp && cp .env.example .env && chmod 600 .env
```

```bash
cd deploy/mvp && docker compose up -d --build && docker compose run --rm migrate
```

```bash
cd deploy/mvp && docker compose exec api python -m app.cli create-tenant --name "Small Development" --slug smalldev --odoo-url http://host.docker.internal:8069 --odoo-db <base> --odoo-login sdtreasury-api@smalldev.es --secret-ref env:ODOO_SMALLDEV_API_KEY
```

```bash
cd deploy/mvp && docker compose exec api python -m app.cli set-sso-secret --tenant smalldev --secret-ref env:ODOO_SMALLDEV_SSO_SECRET && docker compose exec api python -m app.cli sync --tenant smalldev && docker compose exec api python -m app.cli grant --tenant smalldev --modules liquidity
```

En Odoo, en *Contabilidad → Ajustes → SD Treasury*: URL `https://tesoreria.smalldev.es`, identificador `smalldev` y el mismo secreto de SSO.

### Limitaciones asumidas en el MVP
- **Un solo servidor**, sin alta disponibilidad: si cae la EC2, caen Odoo y la tesorería a la vez.
- Recursos compartidos con Odoo (de ahí los límites de memoria en `docker-compose.yml`).
- Secretos en un fichero `.env` en lugar de Secrets Manager.
- Copias de seguridad por `pg_dump` diario en lugar de PITR.

**Cuándo pasar a la arquitectura objetivo:** con 3–5 clientes de pago, cuando un cliente pida SLA o ISO 27001, o si la sincronización empieza a afectar al rendimiento de Odoo.

---

## 2. Arquitectura objetivo (más adelante)

| Recurso | Staging (orientativo) | Producción |
|---|---|---|
| Cuenta AWS propia en la Organization, región `eu-south-2` | ✓ | ✓ |
| VPC con 2 zonas, subredes privadas y NAT | 1 NAT | 2 NAT |
| Conexión a las VPC de los Odoo (Transit Gateway o peering) | ✓ | ✓ |
| ECR + ECS Fargate (`api`, `worker`) | 1 tarea de cada | 2 o más con autoescalado |
| ALB público con WAF y ALB interno (webhooks) | ✓ | ✓ |
| RDS PostgreSQL 16 | `db.t4g.small` | Multi-AZ y PITR |
| S3 + CloudFront (frontend), Cognito, Secrets Manager + KMS, SQS/EventBridge, SES, CloudWatch | ✓ | ✓ |
| Despliegue desde GitHub Actions con rol OIDC | ✓ | ✓ |

Coste orientativo de staging: **120–200 USD al mes**. Se escribirá en Terraform (`infra/terraform`) cuando llegue el momento.
