# SD Treasury: propuesta de arquitectura y plan por fases (v4)

Objetivo: un sistema de gestión de tesorería (TMS) que complemente Odoo y cubra el perímetro funcional de Agicap.

> **v3 (10/11/2026):** ajustada a las condiciones de partida:
> - **Producto para clientes** de SmallDev (no uso interno).
> - De entrada, **solo Odoo 18 y 19 Enterprise**, siempre desplegado en **AWS**.
> - **A largo plazo, otros ERPs.**
>
> Esto cambia la arquitectura de la v2 (addons nativos de Odoo) a una **plataforma propia independiente del ERP con un conector para Odoo**. El análisis funcional de Agicap (sección 1) se mantiene de la v2.
>
> **v4 (10/11/2026):** incorpora las decisiones tomadas (sección 7):
> - Los Odoo de los clientes están en el AWS de SmallDev y se accede por API.
> - Una sola plataforma compartida.
> - Piloto: Small Development.
> - Cobro por sociedad y módulo.
> - Segundo ERP aplazado sin fecha.
>
> Se añaden las secciones 3.6 (red), 3.7 (modelo comercial) y 4.1 (piloto).

---

## 1. Qué ofrece Agicap

Agicap se organiza en cinco grandes productos más una capa transversal:

| Producto Agicap | Funcionalidades que anuncia |
|---|---|
| **Gestión de liquidez** | Sincronización con más de 300 bancos, categorización automática con reglas avanzadas, real vs. presupuesto, conciliación bancaria sugerida, saldo diario, cash pooling, previsión a 13 semanas |
| **Previsión de tesorería** | Previsión multihorizonte (diaria, 13 semanas, anual), conversor presupuesto/PyG → plan de tesorería a 12 meses, escenarios vinculables, análisis de desviaciones, previsión multifuente (bancos + AP/AR + salarios, alquileres, impuestos, deuda), exposición a divisa y simulación de coberturas |
| **Conectividad bancaria y ERP** | EDITRAN, EBICS TS, SWIFT, Host-to-Host, PSD2 (vía Salt Edge, finAPI…), N43/CSV/XLSX, integración bidireccional con ERP por API/SFTP, API pública |
| **Pagos (Payment Factory)** | Remesas multibanco y multidivisa ISO 20022, firma simple o doble, gestión segura de beneficiarios con alertas de cambios, recepción de estados de pago (PSR), historial de firmas, validación desde el móvil |
| **Gestión de gastos / AP** | OCR de facturas y tickets, pedidos y cotejo a tres bandas, flujos de aprobación por importe/proveedor/centro de coste, presupuestos por centro de coste, tarjetas corporativas, notas de gastos, precontabilidad |
| **Gestión de cobros** | Antigüedad de deuda, DSO consolidado de grupo, límites de crédito por cliente, recordatorios automáticos con enlace de pago, litigios que pausan recordatorios, previsión basada en el comportamiento real de pago, diario de ventas y cobros |
| **Automatización contable** | Asientos de banco automáticos, sugerencia de contrapartidas, conciliación con umbrales de tolerancia, detección de flujos intragrupo, exportación de asientos al ERP |
| **Financiación e inversiones** | Préstamos, leasing y pólizas con cuadros de amortización, intereses variables con EURIBOR diario, KPIs de deuda (principal pendiente, servicio de la deuda, deuda neta), covenants, posición financiera neta, coberturas Cap/Swap, simulación y seguimiento de inversiones |
| **Grupo** | Consolidación multientidad y multidivisa, cuadro de saldos, cash pooling con sugerencias de barrido enviadas a pagos, préstamos intragrupo con cálculo de intereses |
| **Reporting** | Plantillas: pool bancario y auditoría de comisiones, cash burn y runway, desviaciones, deuda, excedentes y rendimientos, DSO. Exportación a PDF y Excel, resumen semanal cada lunes |
| **IA y MCP** | Clasificación, conciliación y actualización de previsiones en segundo plano; preguntas en lenguaje natural; detección de anomalías; previsión con ML; **servidor MCP** para Claude/ChatGPT con los permisos del usuario |
| **App móvil** | Saldos, aprobación de pagos y gastos, notificaciones push, paneles en PDF |
| **Facturación electrónica** | Preparación para la Ley 18/2022 «Crea y Crece» y el SII; Agicap está registrada como plataforma de facturación electrónica |

---

## 2. Qué aporta Odoo Enterprise y qué construimos

Al ser siempre Enterprise, podemos **apoyarnos en Odoo para los datos de origen** desde el día uno. Aun así, la lógica de tesorería vive en nuestra plataforma, para que siga funcionando cuando el ERP sea otro.

| Área | Odoo 18/19 Enterprise | Papel en SD Treasury |
|---|---|---|
| Sincronización bancaria PSD2 | ✅ Odoo Online Sync (Salt Edge, Ponto…) | **Al principio leemos los extractos de Odoo.** PSD2 propio en la Fase 6, para no depender del ERP |
| Import N43 / CAMT | ✅ Localización ES | Leemos el resultado desde Odoo; import propio cuando haya otro ERP |
| Conciliación | ✅ Modelos de conciliación | Se queda en Odoo; nosotros leemos el estado conciliado |
| Facturas, pedidos, gastos, nóminas | ✅ ERP | Datos de origen de la previsión (solo lectura) |
| OCR, cotejo a tres bandas, aprobaciones de compra | ✅ | Se quedan en Odoo (fuera del producto) |
| Seguimiento de cobros (follow-up) | ✅ básico | **Nuestro módulo de cobros** (riesgo, DSO de grupo, litigios); el cobro se registra en Odoo |
| SEPA y lotes de pago | ✅ `account_sepa`, `account_batch_payment` | **Generación y gobierno de remesas en la plataforma** (firmas, antifraude, PSR); el pago se registra en Odoo |
| Préstamos | 🟡 Gestión de préstamos (a verificar en 18 y 19) | Financiación completa en la plataforma (EURIBOR, covenants, inversiones) |
| Multicompañía e intercompañía | ✅ | Consolidación, intragrupo y cash pooling en la plataforma |
| Categorías, previsión, escenarios, desviaciones, reporting, IA, MCP | ❌ | **Núcleo del producto** |
| Facturación electrónica, SII, Verifactu | ✅ Localización ES | No se duplica |

**Principio:** el ERP es la fuente de verdad de los **documentos contables** (facturas, pagos, extractos, asientos). La plataforma es la fuente de verdad de **categorías, previsiones, escenarios, presupuestos de caja, financiación, remesas y su gobierno**.

---

## 3. Arquitectura recomendada

### 3.1 Decisión: plataforma SaaS propia + conector para Odoo

| Opción | Ventajas | Inconvenientes | Veredicto |
|---|---|---|---|
| A. Addons nativos de Odoo (v2) | Lo más rápido para Odoo; sin sincronización | **Atado a Odoo**: otro ERP obliga a reescribir. Hay que instalar y actualizar en cada Odoo de cada cliente (18 y 19). Las licencias (LGPL/OPL) y el modelo de producto quedan supeditados a Odoo | ❌ No encaja con el objetivo |
| **B. Plataforma independiente (backend Python + frontend React) + conectores por ERP** | Un solo producto para todos los ERPs, despliegue centralizado, modelo SaaS por suscripción, independiente de la versión de Odoo | Hay que sincronizar los datos y gestionar la autenticación | ✅ **Recomendada** |

**Stack:**
- **Backend en Python:** FastAPI, SQLAlchemy 2 y Alembic, Pydantic v2, y workers asíncronos (Celery o Dramatiq). Python además encaja con el ML de previsión (pandas, statsforecast, scikit-learn).
- **Frontend en React + TypeScript:** Vite, TanStack Query/Router, ECharts para los gráficos y AG Grid para el plan de tesorería tipo hoja de cálculo. Diseño responsive (PWA) para la aprobación móvil.
- **Conector Odoo:** un addon ligero `sd_treasury_connector` para Odoo 18 y 19, más un adaptador Python dentro de la plataforma.

### 3.2 Vista general

```
                    ┌─────────────── Clientes (Odoo 18/19 Enterprise en AWS) ───────────────┐
                    │  Odoo cliente A            Odoo cliente B           Odoo cliente C    │
                    │  └ sd_treasury_connector   └ sd_treasury_connector  └ …               │
                    │     · menú «Tesorería» (UI embebida + SSO)                            │
                    │     · webhooks de cambios (facturas, pagos, extractos)                │
                    │     · endpoints de escritura (registrar pagos/remesas)                │
                    └──────────────────────────┬────────────────────────────────────────────┘
                                               │ HTTPS · API key por cliente · firma HMAC
┌──────────────────────────────── SD Treasury Platform (AWS, multi-tenant) ───────────────────────────┐
│                                                                                                     │
│  Frontend React (S3 + CloudFront)              API Gateway / ALB                                    │
│                                                     │                                               │
│  ┌──────────────────────── API FastAPI (ECS Fargate) ──────────────────────────┐                    │
│  │ tenants · usuarios/roles · categorías · flujos · previsión · escenarios     │                    │
│  │ cobros · pagos · financiación · grupo · reporting · alertas                 │                    │
│  └───────────────┬────────────────────────────────────────────┬────────────────┘                    │
│                  │                                            │                                     │
│  ┌───────────────┴────────── Workers (ECS Fargate) ───────────┴───────────────┐                     │
│  │ sync/      conectores ERP: OdooConnector (18 → JSON-RPC, 19 → JSON-2)      │                     │
│  │            [futuro: Holded, Sage, A3, Business Central…]                   │                     │
│  │ banking/   PSD2 (Fase 6), EURIBOR del BCE, ficheros N43/CAMT/pain          │                     │
│  │ engine/    cálculo de flujos, previsión, escenarios, alertas               │                     │
│  │ ml/ ai/    categorización, anomalías, asistente (Claude API), servidor MCP │                     │
│  └────────────────────────────────────────────────────────────────────────────┘                     │
│                                                                                                     │
│  RDS PostgreSQL (multi-AZ, RLS por tenant) · ElastiCache Redis · SQS · EventBridge (crons)          │
│  S3 (ficheros, informes) · Secrets Manager + KMS (credenciales ERP/bancos) · Cognito (auth)         │
│  CloudWatch + Sentry · WAF · backups y PITR                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Capa de conectores ERP: lo que permite crecer a otros ERPs

Toda la lógica trabaja sobre un **modelo canónico** independiente del ERP. Cada conector solo traduce:

```python
class ErpConnector(Protocol):
    # Lectura (incremental por cursor/fecha de modificación)
    def companies(self) -> list[Company]: ...
    def bank_accounts(self) -> list[BankAccount]: ...
    def bank_transactions(self, since: Cursor) -> Page[BankTransaction]: ...
    def open_items(self, since: Cursor) -> Page[OpenItem]: ...      # facturas cliente/proveedor pendientes
    def orders(self, since: Cursor) -> Page[Order]: ...             # pedidos venta/compra sin facturar
    def partners(self, since: Cursor) -> Page[Partner]: ...
    def recurring_costs(self) -> list[RecurringItem]: ...           # nóminas, gastos…
    # Escritura
    def register_payment(self, batch: PaymentBatch) -> ErpRef: ...
    def post_journal_entry(self, entry: JournalEntry) -> ErpRef: ...
    def capabilities(self) -> set[Capability]: ...                  # qué soporta este ERP/versión
```

**Conector Odoo:**
- **Odoo 18:** JSON-RPC o XML-RPC con API key de un usuario técnico por cliente.
- **Odoo 19:** nueva API **JSON-2** (`/json/2/<modelo>/<método>`). XML-RPC y JSON-RPC están marcados como obsoletos en 19, así que el adaptador abstrae ambas versiones desde el principio.
- **Sincronización:** carga inicial completa, luego incremental por `write_date`, más **webhooks** emitidos por el addon (o reglas de automatización de Odoo) para un tiempo casi real. Upserts idempotentes por (`tenant`, `erp`, `modelo`, `id`). Reconciliación nocturna para corregir divergencias.
- **Addon `sd_treasury_connector`:** menú «Tesorería» en Odoo que abre la app embebida con SSO (token firmado de corta duración), emite los webhooks, expone endpoints de escritura controlados y un asistente de configuración (URL, API key, empresas a sincronizar). **Sin lógica de negocio**, para que sea fácil de mantener en 18 y 19 y publicable en Odoo Apps.

### 3.4 Multi-tenant y seguridad
- **Tenant = cliente.** Un tenant puede tener varias sociedades (multicompañía de Odoo) y, en el futuro, varios ERPs.
- **Aislamiento:** base de datos compartida con `tenant_id` en todas las tablas y **Row-Level Security de PostgreSQL**. Opción de base dedicada para clientes grandes.
- **Autenticación:** Cognito (o Keycloak) con roles (Administrador, Tesorero, Aprobador, Lectura) y permisos por sociedad. SSO desde Odoo.
- **Secretos:** API keys de Odoo y tokens PSD2 en Secrets Manager, cifrados con KMS.
- **Cumplimiento:** RGPD; **región AWS en la UE** (`eu-south-2` España o `eu-west-3` París); registro de auditoría inmutable de firmas, cambios de beneficiarios y escenarios; camino hacia ISO 27001 (Agicap la tiene y los clientes la pedirán).
- **Infraestructura como código:** Terraform. CI/CD con GitHub Actions y entornos dev, staging y producción.

### 3.5 Modelo de datos canónico (resumen)

```
tenant, company, bank_account, partner                       (espejo del ERP)
bank_transaction, open_item, order, recurring_item           (espejo del ERP, solo lectura)
category, category_rule                                      (propio)
flow            TABLA CENTRAL: fecha, importe, divisa, company, bank_account, category,
                estado (real | comprometido | previsto), origen, erp_ref, scenario_id
forecast_recurring, budget, scenario, scenario_adjustment, forecast_snapshot
collection_case, dunning_step, dispute                        (cobros)
payment_batch, payment_line, signature, beneficiary_change   (pagos)
debt, debt_schedule, covenant, investment, rate_index        (financiación)
cash_pool, sweep_proposal, intercompany_loan                 (grupo)
alert_rule, alert_event, report_template, audit_log
```

### 3.6 Red y acceso a los Odoo (todo en el AWS de SmallDev)

Como todos los Odoo de los clientes están en la infraestructura AWS de SmallDev, **la plataforma se conecta a ellos por red privada**, sin exponer la API de Odoo a internet:

- **Cuenta AWS propia para la plataforma** dentro de la misma AWS Organization. Aísla costes, permisos y el alcance de las auditorías. La conexión con las VPC de los Odoo va por **Transit Gateway o VPC peering**, con DNS privado (`odoo-cliente.internal`).
- **De la plataforma a Odoo:** llamadas a la API de Odoo (JSON-RPC en 18, JSON-2 en 19) por red privada, con **un usuario técnico por cliente** y API key en Secrets Manager. El addon crea un grupo de permisos mínimo: lectura de contabilidad, ventas, compras y partners; escritura solo de pagos y notas.
- **De Odoo a la plataforma (webhooks):** un ALB interno, con firma HMAC por tenant.
- **Usuarios:** solo el frontend (CloudFront) y la API pública (ALB con WAF) salen a internet. El menú «Tesorería» de Odoo abre la app con SSO.
- **Protección de los Odoo de cliente:** límite de peticiones por instancia, sincronizaciones pesadas en horario valle y paginación, para no penalizar el rendimiento del ERP del cliente.
- **Ventaja operativa:** al controlar también los Odoo, SmallDev puede instalar y actualizar el addon conector en todos los clientes de forma centralizada (por ejemplo, con el pipeline de despliegue de los Odoo).

### 3.7 Modelo comercial: suscripción por sociedad y módulo

Cada módulo comercial corresponde a una fase del plan, así que lo que se construye se puede vender en cuanto se entrega:

| Módulo | Contenido | Fase | Notas |
|---|---|---|---|
| **Liquidez** (base) | Cockpit, categorías, conciliación con Odoo, previsión a 13 semanas, alertas, resumen del lunes | 1 | Obligatorio |
| **Previsión** | Multihorizonte, conversor de presupuesto, escenarios, desviaciones | 2 | Requiere Liquidez |
| **Cobros** | DSO, riesgo, recordatorios, litigios | 3 | |
| **Pagos** | Propuestas, firmas, antifraude, SEPA, PSR | 4 | |
| **Financiación** | Préstamos, pólizas, EURIBOR, covenants, inversiones | 5 | |
| **Grupo** | Consolidación, intragrupo, cash pooling | 5 | Requiere 2 o más sociedades con el módulo |
| **IA** | Asistente, anomalías, ML, MCP | 6 | |
| **Bancos directos** | Conexión PSD2 propia | 6 | Coste del proveedor PSD2 repercutido por cuenta |

**Implementación técnica (desde la Fase 0):**
```
plan              (catálogo: módulo, precio por sociedad/mes)
subscription      (tenant, estado, fecha de facturación, método de pago)
entitlement       (tenant, company_id, module, valid_from, valid_to, trial)
usage_snapshot    (tenant, mes, sociedades activas por módulo)  → base de la factura
```
- La API comprueba el acceso **por sociedad** en cada endpoint (`require_module("collect", company_id)`). El frontend oculta o muestra como «bloqueado, disponible» los módulos no contratados (útil para la venta).
- Las vistas consolidadas solo incluyen las sociedades con el módulo Grupo.
- Periodos de prueba por módulo (`trial`) y una consola interna para que SmallDev active o desactive módulos por cliente.
- La facturación se hace al principio con un export mensual desde `usage_snapshot`. La **integración con Stripe Billing** (cantidad = número de sociedades por módulo) llega en la Fase 7.

---

## 4. Plan por fases

Supone un equipo de 2–3 desarrolladores (backend Python, frontend React y una persona funcional de Odoo y tesorería a tiempo parcial). Cada fase se puede usar en producción por sí sola, con un **cliente piloto** desde el final de la Fase 1.

### Fase 0: cimientos de la plataforma (4–5 semanas)
- Infraestructura AWS con Terraform (VPC, ECS Fargate, RDS, Redis, SQS, S3/CloudFront, Cognito, Secrets Manager); entornos dev, staging y producción.
- Esqueleto de FastAPI (multi-tenant, RLS, auth, auditoría) y de la app React (layout, auth, selector de sociedad).
- Modelo canónico e interfaz `ErpConnector` (solo se implementa el conector Odoo; la interfaz deja la puerta abierta a otros ERPs).
- Red privada hacia los Odoo (cuenta AWS de la plataforma, Transit Gateway o peering, ALB interno para webhooks).
- **Suscripciones y módulos por sociedad** (`plan`, `subscription`, `entitlement`) y consola interna de activación.
- **Conector Odoo v1 (solo lectura)**, primero para la versión del piloto y después para la otra (18 o 19): sociedades, cuentas, extractos, facturas pendientes, pedidos y partners; carga inicial, incremental y webhooks.
- Addon `sd_treasury_connector`: configuración, SSO y menú embebido.
- CI/CD, tests contra instancias Odoo 18 y 19 en Docker, observabilidad.

### Fase 1: liquidez, el MVP (5–6 semanas) → cliente piloto
- Categorías y reglas con plantilla española; categorización automática con sugerencia de reglas.
- Motor de `flow`: real (extractos de Odoo), comprometido (facturas con fecha ajustada por el retraso medio de cada partner) y previsto (pedidos, recurrentes).
- **Cockpit**: saldo por banco y sociedad, entradas y salidas por categoría, evolución diaria, cuadro de saldos.
- **Previsión a 13 semanas**; real vs. presupuesto básico; exportación a Excel y PDF.
- **Resumen del lunes** por correo y alertas de saldo bajo umbral.

### Fase 2: previsión y escenarios (4–5 semanas)
- Multihorizonte: diario, 13 semanas y 12–24 meses.
- **Conversor de presupuesto o PyG → plan de tesorería** (plazos de cobro y pago por categoría, IVA trimestral, impuestos 303/111/115/200, nóminas y Seguridad Social).
- **Escenarios** vinculables y comparación entre ellos; snapshots y **análisis de desviaciones**.

### Fase 3: cobros (4–5 semanas)
- Antigüedad de deuda, DSO por sociedad y de grupo, puntuación de riesgo, límites de crédito (leídos de Odoo).
- Secuencias de recordatorio con plantillas y **enlace de pago** (portal de Odoo).
- **Litigios** que pausan los recordatorios.
- La previsión usa el comportamiento real de pago de cada cliente.
- Escritura en Odoo: notas o actividades en la factura y el partner.

### Fase 4: pagos (5–6 semanas)
- **Propuestas de pago** según vencimientos y caja disponible.
- **Firma simple o doble**, historial de firmas y aprobación móvil.
- **Antifraude de beneficiarios**: los cambios de IBAN detectados en la sincronización se bloquean hasta validarlos.
- Generación **pain.001 / pain.008** en la plataforma; import de **pain.002 (PSR)**.
- **Escritura en Odoo**: registro de pagos o lote de pagos y conciliación posterior con el extracto.

### Fase 5: financiación, inversiones y grupo (6–7 semanas)
- Préstamos, leasing y pólizas con cuadro de amortización; **EURIBOR diario** (API del BCE); KPIs de deuda y **covenants**.
- Inversiones y depósitos: excedente invertible, simulación y seguimiento.
- **Consolidación** multisociedad y multidivisa; **intragrupo** (detección, préstamos con intereses).
- **Cash pooling** con sugerencias de barrido que pasan a remesas de la Fase 4.
- Biblioteca de **informes**: pool bancario y comisiones, burn y runway, desviaciones, deuda, DSO.

### Fase 6: conectividad bancaria propia e IA (6–8 semanas)
- **PSD2 propio** (GoCardless Bank Account Data o Salt Edge), necesario para independizarse del ERP y para clientes cuyo ERP no sincroniza bancos.
- ML: categorización con nivel de confianza, previsión estadística de flujos no facturados, **detección de anomalías** (duplicados, importes atípicos).
- **Asistente en lenguaje natural** (Claude API): preguntas, explicación de desviaciones y recategorización en bloque con revisión previa.
- **Servidor MCP de SD Treasury** (OAuth, con los permisos del usuario): posición, previsión, desviaciones, DSO.

### Fase 7: producto (continua)
- Facturación automática con Stripe Billing (por sociedad y módulo), alta de clientes en autoservicio y panel de administración de tenants.
- Opcional: EDITRAN, EBICS o H2H; coberturas de divisa y tipos; app móvil nativa.

### Futuro, sin fecha: otros ERPs
- La interfaz `ErpConnector` y el modelo canónico ya lo permiten. Cuando haya demanda se elige el ERP (candidatos en España: Holded, Sage 200, A3ERP, Business Central) y se implementa solo su conector.

**Total orientativo: 9–11 meses** para las Fases 0–6.

### 4.1 Piloto: Small Development

Revisión de solo lectura de su Odoo (10/11/2026):

| Dato | Valor | Implicación |
|---|---|---|
| Sociedades | 1 (Small Development SL, EUR) | El MVP encaja; el módulo **Grupo no se puede validar** con el piloto |
| Bancos | Santander y CaixaBank, ambos con **sincronización online de Odoo** | La Fase 1 no necesita PSD2 propio: se leen los extractos de Odoo |
| Diario «Préstamos» | Sí | Caso real para el módulo **Financiación** (Fase 5) |
| Movimientos bancarios | unos 1.500 al año (2025 y 2026) | Volumen cómodo; suficiente histórico para entrenar la categorización |
| Facturas pendientes | unas 60 de cliente y 140 de proveedor | Buen caso para la previsión a 13 semanas, Cobros y Pagos |

**Para validar Grupo y multidivisa** hará falta un segundo entorno multisociedad: una instancia demo con varias sociedades y una UTE (como Demo11), o un cliente con grupo de empresas como segundo piloto.

---

## 5. Estructura del repositorio (monorepo)

```
sdtreasury/
├── backend/                    FastAPI + workers (Python 3.12)
│   ├── app/
│   │   ├── api/                routers por dominio
│   │   ├── domain/             lógica: flows, forecast, scenarios, collect, payments, financing, group
│   │   ├── connectors/
│   │   │   ├── base.py         ErpConnector + modelo canónico
│   │   │   └── odoo/           v18 (JSON-RPC), v19 (JSON-2)
│   │   ├── banking/            psd2, n43, camt, pain
│   │   ├── ml/  ai/  mcp/
│   │   └── workers/
│   ├── migrations/             Alembic
│   └── tests/
├── frontend/                   React + TypeScript (Vite)
├── odoo/
│   └── sd_treasury_connector/  addon ligero (ramas o manifests para 18.0 y 19.0)
├── infra/terraform/            AWS
├── docker-compose.yml          dev: api + workers + postgres + redis + odoo18 + odoo19
├── docs/
└── .github/workflows/
```

## 6. Riesgos y cómo mitigarlos

| Riesgo | Mitigación |
|---|---|
| Divergencia de datos entre Odoo y la plataforma | Upserts idempotentes, webhooks más incremental, reconciliación nocturna e indicador de «última sincronización» visible |
| Cambios de API entre Odoo 18, 19 y 20 | Adaptador por versión y tests de contrato contra contenedores de cada versión en CI |
| Volumen de datos de clientes grandes | Sincronización paginada en workers; `flow` indexada y particionada por tenant y fecha |
| Seguridad (datos financieros, pagos) | Row-Level Security, KMS, firma doble, auditoría inmutable, pentest antes de vender, camino a ISO 27001 |
| Dependencia de la sincronización bancaria de Odoo | PSD2 propio en la Fase 6 |

## 7. Decisiones tomadas

| Tema | Decisión |
|---|---|
| ERP de partida | Odoo **18 y 19 Enterprise** |
| Alojamiento | AWS de SmallDev (plataforma y Odoo de clientes); acceso a Odoo **por API** y red privada |
| Despliegue | **Una sola plataforma** compartida por todos los clientes |
| Stack | Backend Python (FastAPI) + frontend React (TypeScript) + addon conector ligero en Odoo |
| Piloto | **Small Development** |
| Modelo comercial | Suscripción **por sociedad y módulo** |
| Otros ERPs | A largo plazo y sin fecha; solo se deja preparada la abstracción |

## 8. Estado de la Fase 0

**Decidido (10/11/2026):** versión del piloto **Odoo 18 Enterprise**; cuenta AWS la aporta SmallDev ([`AWS_REQUISITOS.md`](AWS_REQUISITOS.md)); precios por definir (no bloquea); equipo: desarrollo incremental entre Rafael y Claude.

| Entregable | Estado |
|---|---|
| Backend FastAPI: tenants, RLS, autenticación (dev/Cognito), roles | ✅ Primera versión |
| Suscripción por sociedad y módulo (`entitlement`) | ✅ Primera versión, sin consola |
| Modelo canónico + `ErpConnector` + conector **Odoo 18** de solo lectura (sociedades, bancos, saldos, movimientos, facturas pendientes) | ✅ Primera versión, falta probarlo contra el Odoo del piloto |
| Sincronización incremental idempotente + refresco de facturas abiertas | ✅ |
| Conector demo con datos ficticios | ✅ |
| Frontend React: login de desarrollo y posición de caja | ✅ Mínimo |
| Addon `sd_treasury_connector` (menú, ajustes, grupos) | ✅ Esqueleto, sin probar en Odoo |
| CI (GitHub Actions), docker-compose | ✅ |
| SSO desde Odoo, webhooks, colas (SQS) | ⏳ Siguiente |
| Terraform AWS (staging) | ⏳ Pendiente de los datos de `AWS_REQUISITOS.md` |
| Consola interna de módulos | ⏳ |
