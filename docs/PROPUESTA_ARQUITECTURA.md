# SD Treasury: propuesta de arquitectura y plan por fases

Objetivo: un módulo de gestión de tesorería que complemente lo que ya trae Odoo y cubra el perímetro funcional de herramientas tipo Agicap: previsión de caja, conexión multibanco, categorización, escenarios, cobros, pagos, multisociedad y reporting.

---

## 1. Decisión de stack: Python, dentro de Odoo

**Recomendación: un addon nativo de Odoo (Python + OWL) como núcleo, más un microservicio Python (FastAPI) solo para lo que no conviene ejecutar dentro de Odoo.**

Descarto Node.js + React como base por estas razones:

| Criterio | Addon Odoo (Python/OWL) | App externa (Node + React) |
|---|---|---|
| Acceso a facturas, pagos, extractos, pedidos | Directo con el ORM, en tiempo real | Por XML-RPC/JSON-RPC: latencia y sincronización |
| Permisos, multicompañía, auditoría | Los hereda (`ir.rule`, `company_ids`, chatter) | Hay que rehacerlos |
| UX para el usuario | Integrada en el menú de Contabilidad | Otra aplicación y otro login |
| Despliegue | Un módulo más (Odoo.sh o on-premise) | Infraestructura aparte |
| Gráficos y dashboards avanzados | OWL + Chart.js (los incluye Odoo) | React, más libre |

El único punto donde React gana es la libertad para el frontend, y OWL (el framework de Odoo, muy parecido a React) lo cubre de sobra.

### Arquitectura objetivo

```
┌──────────────────────────── Odoo (17/18/19) ────────────────────────────┐
│                                                                          │
│  sd_treasury_base       Modelos: cuentas, categorías, flujos, reglas      │
│  sd_treasury_forecast   Previsión, escenarios, presupuesto vs. real        │
│  sd_treasury_bank       Import N43/CAMT.053, conciliación asistida         │
│  sd_treasury_collect    Cobros: priorización, recordatorios, DSO           │
│  sd_treasury_payment    Pagos: propuestas, aprobación, SEPA pain.001       │
│  sd_treasury_dashboard  Cliente OWL: cockpit, gráficos, drill-down         │
│                                                                          │
│        ▲ REST interno (token) / cola de trabajos (queue_job)             │
└────────┼─────────────────────────────────────────────────────────────────┘
         │
┌────────┴──────────── sd-treasury-engine (FastAPI, Python) ───────────────┐
│  · Agregación bancaria PSD2 (GoCardless Bank Account Data / Tink /       │
│    Salt Edge): consentimientos, refresco, webhooks                        │
│  · Motor ML: categorización automática y previsión estadística           │
│    (scikit-learn / statsforecast)                                        │
│  · Workers (Celery/RQ + Redis), PostgreSQL propio para datos crudos      │
└──────────────────────────────────────────────────────────────────────────┘
```

**Por qué un microservicio aparte para banca y ML:**
- Las credenciales y consentimientos PSD2 quedan fuera de la base de Odoo y se aíslan mejor.
- Librerías pesadas (pandas, statsforecast) sin cargar los workers de Odoo ni chocar con las restricciones de Odoo.sh.
- Los procesos largos (refresco de bancos, reentrenar modelos) no bloquean Odoo.
- Es **opcional en las primeras fases**: la Fase 1 funciona solo con Odoo.

---

## 2. Qué ya cubre Odoo y qué añadimos

| Funcionalidad tipo Agicap | Odoo Community | Odoo Enterprise | SD Treasury añade |
|---|---|---|---|
| Sincronización bancaria | ✗ | ✓ (Odoo Online Sync / Ponto / Salt Edge) | Import Norma 43 y CAMT; PSD2 propio opcional; vista multibanco consolidada |
| Conciliación | Básica | ✓ buena | Reglas de categorización de tesorería (no contable) |
| Categorización de flujos | ✗ | ✗ (solo cuentas contables) | **Árbol de categorías de tesorería**, reglas y ML |
| Previsión de caja | ✗ | Informe básico | **Previsión a 13 semanas / 12–24 meses**, por categoría |
| Escenarios (what-if) | ✗ | ✗ | **Escenarios** optimista/pesimista/personalizados |
| Presupuesto vs. real | ✗ | `account_budget` (contable) | Presupuesto **de caja** por categoría y desviaciones |
| Cobros | Seguimiento básico | Follow-up | Priorización por riesgo, previsión de fecha real de cobro, DSO |
| Pagos | Pagos manuales | SEPA y lotes | Propuestas de pago según caja, flujo de aprobación |
| Multisociedad / consolidación | Multicompañía | Multicompañía | **Vista consolidada de grupo**, intercompañía, multidivisa |
| Alertas | ✗ | ✗ | Umbrales de saldo, desviaciones, vencimientos |
| Dashboards | Pivot/graph | Spreadsheet | **Cockpit de tesorería** con drill-down |

> La arquitectura detecta si existen módulos Enterprise (`account_online_synchronization`, `account_sepa`, `account_followup`) y los reutiliza en lugar de duplicarlos.

---

## 3. Modelo de datos principal

```
treasury.category          Árbol de categorías (Ventas, Nóminas, Impuestos, Financiación…)
                           tipo: entrada/salida, padre, empresa, cuenta contable por defecto
treasury.category.rule     Reglas: texto/IBAN/partner/importe → categoría (con prioridad)
treasury.account           Agrupa diario bancario + saldo + banco + divisa + empresa
treasury.flow              Línea UNIFICADA de flujo de caja (tabla central)
                           fecha, importe, divisa, empresa, categoría, estado
                           (real | comprometido | previsto), origen (extracto,
                           factura, pedido, nómina, manual, recurrente), res_model/res_id
treasury.forecast.line     Previsiones manuales/recurrentes (ej.: alquiler mensual)
treasury.scenario          Escenario: base + ajustes (% o importe por categoría y periodo)
treasury.budget            Presupuesto de caja por categoría y periodo
treasury.alert             Reglas de alerta y su historial
```

`treasury.flow` es la pieza clave: se alimenta automáticamente de

- **Real:** `account.bank.statement.line` (movimientos bancarios)
- **Comprometido:** `account.move` pendientes (facturas cliente/proveedor) con fecha de vencimiento ajustada por el retraso medio de pago de cada partner
- **Previsto:** `sale.order` / `purchase.order` sin facturar, nóminas, impuestos (modelos 303/111/115 por calendario), préstamos y previsiones manuales o recurrentes

Así una misma consulta devuelve el saldo real, el comprometido y el previsto en cualquier horizonte.

---

## 4. Plan por fases

### Fase 0: preparación (1–2 semanas)
- Confirmar la versión de Odoo y la edición (Community/Enterprise) en producción.
- Repositorio, CI (pre-commit, pylint-odoo, tests con `odoo --test-enable`), entorno de desarrollo con Docker.
- Inventario de datos reales: bancos, número de sociedades, divisas, volumen de movimientos.
- Árbol de categorías de tesorería por defecto (plantilla PYME española).

### Fase 1, MVP: visibilidad de caja (4–6 semanas)
*Objetivo: saber cuánto dinero hay hoy y cuánto habrá en 13 semanas.*
- `sd_treasury_base`: categorías, reglas y `treasury.flow` alimentado por extractos y facturas.
- Import **Norma 43** (AEB) y **CAMT.053**, para usarlo sin Enterprise.
- Categorización por reglas, con aprendizaje simple: al recategorizar a mano se sugiere crear una regla.
- **Cockpit OWL**: saldo consolidado por banco y empresa, entradas/salidas por categoría, gráfico de evolución.
- Previsión a 13 semanas basada en vencimientos y previsiones recurrentes manuales.
- Seguridad: grupos Tesorería/Usuario y Tesorería/Responsable, reglas multicompañía.

### Fase 2: previsión y escenarios (4–5 semanas)
- Previsión a 12–24 meses: pedidos de venta y compra, nóminas, impuestos, préstamos.
- Fecha de cobro realista por cliente (retraso histórico medio).
- **Escenarios** what-if duplicables y comparables (base, optimista, pesimista, "contrato nuevo"…).
- **Presupuesto de caja** por categoría, real vs. previsto vs. presupuesto, desviaciones.
- Export a Excel y PDF; tabla pivotante mensual tipo "plan de tesorería".

### Fase 3: cobros y pagos (4–6 semanas)
- `sd_treasury_collect`: cartera de cobros priorizada (importe × retraso × riesgo), recordatorios automáticos escalonados, DSO y aging, previsión de impacto de cada cobro en la caja. Reutiliza `account_followup` si está instalado.
- `sd_treasury_payment`: propuestas de pago según caja disponible y vencimientos, **flujo de aprobación** (multinivel por importe), remesas **SEPA pain.001** (y pain.008 para adeudos), DPO.
- **Alertas**: saldo bajo umbral, desviación > X %, factura grande vencida, por email o actividad de Odoo.

### Fase 4: conexión bancaria y automatización (5–7 semanas)
- Microservicio `sd-treasury-engine` (FastAPI + Redis + PostgreSQL).
- Agregación **PSD2** con GoCardless Bank Account Data (gratuito o barato y con buena cobertura en España); conector abstracto para añadir Tink o Salt Edge.
- Sincronización diaria de saldos y movimientos hacia `account.bank.statement.line`.
- **Categorización ML**: modelo entrenado con el histórico categorizado (TF-IDF + clasificador) y umbral de confianza.
- Previsión estadística de flujos no facturados (estacionalidad) como capa adicional del escenario base.

### Fase 5: grupo, multidivisa y analítica avanzada (3–5 semanas)
- Consolidación de grupo con eliminación de **intercompañía** (útil para holdings con varias SL y UTEs).
- Multidivisa con tipos de cambio y previsión en divisa de grupo.
- KPIs: runway, burn rate, cash conversion cycle, necesidades de financiación.
- Gestión de **financiación**: pólizas de crédito, préstamos (cuadros de amortización), confirming y factoring.
- Asistente IA opcional (Claude API) para explicar desviaciones y responder preguntas sobre la caja.

**Total orientativo: 5–7 meses** con 1–2 desarrolladores. Cada fase se puede usar en producción por sí sola.

---

## 5. Estructura del repositorio

```
sdtreasury/
├── addons/
│   ├── sd_treasury_base/
│   ├── sd_treasury_bank/
│   ├── sd_treasury_forecast/
│   ├── sd_treasury_collect/
│   ├── sd_treasury_payment/
│   └── sd_treasury_dashboard/      (static/src: componentes OWL)
├── engine/                          (Fase 4: FastAPI)
│   ├── app/{api,connectors,ml,workers}
│   └── Dockerfile
├── docker-compose.yml               (odoo + postgres + engine + redis)
├── docs/
└── .github/workflows/ci.yml
```

---

## 6. Decisiones técnicas clave

- **Rendimiento:** `treasury.flow` como tabla materializada que se actualiza con `write`/`create` hooks y un cron de recálculo; las agregaciones se hacen con `read_group` y SQL indexado (fecha, empresa, categoría), no con cálculos en Python fila a fila.
- **Trazabilidad:** cada flujo apunta a su documento origen (`res_model`/`res_id`) para el drill-down.
- **Seguridad:** tokens PSD2 cifrados en el engine, nunca en Odoo; comunicación Odoo↔engine con token HMAC y HTTPS.
- **Tests:** tests unitarios por modelo, tests de tours OWL para el cockpit y datos demo reproducibles.
- **Compatibilidad:** desarrollar sobre una versión objetivo y aislar las diferencias de API entre versiones.

---

## 7. Preguntas abiertas antes de empezar

1. ¿Qué **versión y edición** de Odoo tenéis en producción (¿Enterprise con sincronización bancaria?).
2. ¿Despliegue en **Odoo.sh**, Odoo Online (SaaS, que no admite módulos propios) u on-premise?
3. ¿Producto para **uso interno** o para **vender a clientes** de SmallDev? Afecta al licenciamiento (LGPL/OPL) y a la necesidad de multi-tenant en el engine.
4. ¿Bancos principales y número de sociedades/divisas a cubrir en el MVP?
5. ¿Prioridad de negocio: previsión (Fases 1–2) o cobros y pagos (Fase 3)?
