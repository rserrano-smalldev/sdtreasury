# Qué necesito en AWS

Plataforma SD Treasury: lo que tenéis que dar o crear vosotros y lo que crearé yo con Terraform.

## A. Lo que necesito de vosotros

### A1. Ya, para conectar con el piloto (Small Development, Odoo 18)

1. **Usuario técnico en el Odoo de Small Development**, por ejemplo `sdtreasury-api@smalldev.es`:
   - Tipo usuario interno, con acceso a la sociedad Small Development SL.
   - Grupo **SD Treasury / API de la plataforma** (lo crea el addon `sd_treasury_connector`). Si aún no está instalado el addon, sirve temporalmente *Contabilidad → Solo lectura* (Auditor).
   - Una **API key** de ese usuario (Preferencias → Seguridad de la cuenta → Nueva clave API).
2. **URL interna y nombre de la base de datos** de ese Odoo (por ejemplo `http://odoo-smalldev.internal:8069`, base `smalldev`).
3. **Guardar la API key en Secrets Manager** (no por chat ni en el repositorio), por ejemplo como `sdtreasury/tenants/smalldev/odoo-api-key`. Solo necesito el nombre o ARN del secreto.

### A2. Para desplegar staging

| Qué | Para qué | Detalle |
|---|---|---|
| **Cuenta AWS** de la plataforma | Aislar costes, permisos y auditoría | Dentro de vuestra AWS Organization |
| **Región** | Residencia de datos en la UE | Recomiendo `eu-south-2` (España). Si los Odoo están en otra región, mejor la misma |
| **Rol IAM para GitHub Actions (OIDC)** | Que el CI despliegue sin claves de larga duración | Confianza en `token.actions.githubusercontent.com`, condicionada al repo `rserrano-smalldev/sdtreasury`. Al principio con permisos amplios en esa cuenta; los acotaremos |
| **Bucket S3 y tabla DynamoDB** para el estado de Terraform | Estado remoto con bloqueo | O dejadme crearlos con un primer `terraform apply` manual |
| **Dominio** | URL de la app | Por ejemplo `tesoreria.smalldev.es` (staging: `tesoreria-stg.smalldev.es`). Zona en Route 53 o delegación del subdominio |
| **Datos de red de los Odoo** | Conexión privada plataforma → Odoo | IDs y rangos CIDR de las VPC de los Odoo, y si usáis Transit Gateway. Necesito un **CIDR libre** para la VPC de la plataforma (por ejemplo `10.60.0.0/16`) |
| **Regla de entrada en los Odoo** | Permitir llamadas desde la plataforma | Puerto 443/8069 desde el CIDR de la plataforma en el security group o ALB de cada Odoo |
| **SES (correo)** | Resumen del lunes y alertas | Verificar el dominio remitente y salir del sandbox de SES |

## B. Lo que crearé yo con Terraform (`infra/terraform`)

| Recurso | Staging (orientativo) | Producción |
|---|---|---|
| VPC con 2 zonas, subredes privadas y NAT | 1 NAT | 2 NAT |
| Conexión a las VPC de los Odoo (Transit Gateway o peering) | ✓ | ✓ |
| ECR (imágenes `api` y `worker`) | ✓ | ✓ |
| ECS Fargate: servicios `api` y `worker` | 1 tarea de cada | 2 o más con autoescalado |
| ALB público con WAF (API) y ALB interno (webhooks de Odoo) | ✓ | ✓ |
| RDS PostgreSQL 16 | `db.t4g.small`, single-AZ | `db.t4g.medium` o superior, Multi-AZ y PITR |
| S3 + CloudFront (frontend) | ✓ | ✓ |
| Cognito (usuarios de la plataforma) | ✓ | ✓ |
| Secrets Manager + KMS | ✓ | ✓ |
| SQS y EventBridge (colas y sincronizaciones programadas) | Fase 0 bis | ✓ |
| CloudWatch (logs, alarmas) y presupuesto con alertas | ✓ | ✓ |

Coste orientativo de **staging: 120–200 USD al mes**, sobre todo NAT, RDS, ALB y Fargate. Producción depende del número de clientes.

## C. Orden propuesto

1. **A1**: con eso conecto ya el piloto en desarrollo y validamos datos reales.
2. **A2**: cuenta, región, rol OIDC, dominio y CIDR. Escribo el Terraform de staging y lo aplicáis o lo aplica el CI.
3. Red privada hacia el Odoo del piloto y primer despliegue en staging.
