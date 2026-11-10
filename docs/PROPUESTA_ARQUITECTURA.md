# SD Treasury: propuesta de arquitectura y plan por fases (v2)

Objetivo: un sistema de gestión de tesorería (TMS) que complemente Odoo y cubra el perímetro funcional de Agicap.

> **v2 (10/11/2026):** rehecha a partir de las páginas de producto de agicap.com/es: liquidez, previsión, conectividad bancaria/ERP, pagos, gastos, cobros, automatización contable, financiación, consolidación, cash pooling, deuda, reporting, IA, servidor MCP, app móvil y facturación electrónica.

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

## 2. Análisis de cobertura: qué ya hace Odoo y qué construimos

Clave: ✅ lo cubre Odoo u OCA (lo reutilizamos) · 🟡 parcial (lo ampliamos) · ❌ no existe (lo construimos) · ⏸ fuera de alcance o fase opcional

> La disponibilidad exacta depende de la versión (17/18/19) y la edición. Se verifica en la Fase 0 sobre vuestra instancia.

| Área | Odoo / OCA hoy | SD Treasury |
|---|---|---|
| Sincronización bancaria PSD2 | 🟡 Enterprise (Odoo Online Sync); Community no | Import N43/CAMT/XLSX desde el inicio; PSD2 propio en el engine (Fase 6) |
| EDITRAN / EBICS / SWIFT / H2H | ❌ | ⏸ Opcional (Fase 7): requiere contrato con cada banco o un partner |
| Conciliación con tolerancias | ✅ Modelos de conciliación | Reutilizar; añadir sugerencias ML (Fase 6) |
| **Categorías de tesorería** | ❌ (solo cuentas contables y analítica) | ❌ → **núcleo, Fase 1** |
| **Posición de caja y cockpit** | 🟡 Dashboard contable básico | ❌ → **Fase 1** |
| **Previsión multihorizonte** | ❌ | ❌ → **Fases 1–2** |
| **Conversor presupuesto/PyG → caja** | ❌ | ❌ → **Fase 2** |
| **Escenarios y desviaciones** | ❌ | ❌ → **Fase 2** |
| Seguimiento de cobros | 🟡 Enterprise `account_followup`; OCA `account_credit_control` | Ampliar: DSO de grupo, riesgo, litigios, previsión por comportamiento (**Fase 3**) |
| Límite de crédito por cliente | ✅ Odoo 17+ (límite en el partner) | Integrarlo en la puntuación de riesgo |
| Enlace de pago en recordatorios | ✅ Portal + proveedores de pago | Reutilizar |
| Remesas SEPA pain.001 / pain.008 | 🟡 Enterprise `account_sepa`; OCA `account_payment_order` + `l10n_es` (N19, N34, confirming) | Ampliar: firma doble, antifraude de beneficiarios, PSR (**Fase 4**) |
| Pedidos y cotejo a tres bandas | ✅ Compras (control de facturas por cantidad recibida) | Reutilizar |
| OCR de facturas | ✅ Enterprise (digitalización IAP) | Reutilizar |
| Aprobaciones | 🟡 `approvals` / OCA `tier_validation` | Reutilizar para pagos (Fase 4) |
| Notas de gastos | ✅ `hr_expense` | Reutilizar; reflejarlas en la previsión |
| Presupuesto por centro de coste | 🟡 Presupuestos analíticos (Enterprise) | **Presupuesto de caja** por categoría (Fase 2) |
| Tarjetas corporativas | ❌ | ⏸ Fuera de alcance (requiere entidad de dinero electrónico) |
| Préstamos y leasing | 🟡 Enterprise 18+ (préstamos); OCA `account_loan` | Ampliar: EURIBOR, covenants, KPIs de deuda (**Fase 5**) |
| Inversiones y depósitos | ❌ | ❌ → **Fase 5** |
| Multicompañía | ✅ | **Consolidación de tesorería** multidivisa (**Fase 5**) |
| Intragrupo y cash pooling | 🟡 Transacciones intercompañía (Enterprise) | Detección de flujos, préstamos intragrupo con intereses, sugerencias de barrido (**Fase 5**) |
| Coberturas de divisa y tipo | ❌ | ⏸ Opcional (Fase 7) |
| Reporting de tesorería | 🟡 Pivot/hojas de cálculo | Plantillas de tesorería y resumen del lunes (Fases 1 → 5) |
| IA / lenguaje natural / anomalías | ❌ | **Fase 6** |
| Servidor MCP | 🟡 Ya usáis un MCP de Odoo genérico | **MCP de tesorería** con herramientas de alto nivel (Fase 6) |
| App móvil | 🟡 App Odoo (web responsive) | Vistas móviles del cockpit, aprobación de pagos y notificaciones |
| Facturación electrónica / Verifactu / SII | ✅ Localización española (Facturae, SII, Verifactu según versión) | No duplicar; solo leer el estado de cobro |

**Conclusión:** casi todo lo que en Agicap es *gestión de gastos* y *automatización contable* ya lo hace Odoo, porque Odoo es el ERP. Nuestro valor está en la **capa de tesorería**: categorías, previsión, escenarios, cobros avanzados, gobierno de pagos, financiación, grupo, reporting e IA.

---

## 3. Arquitectura

### Decisión: Python, con Odoo como núcleo

No recomiendo Node.js + React porque Odoo ya tiene los datos (facturas, pagos, extractos, pedidos, nóminas, analítica), los permisos y la multicompañía. Una app externa tendría que sincronizarlo todo y rehacer la seguridad. OWL, el framework de interfaz de Odoo, se parece mucho a React y cubre los paneles necesarios.

```
┌──────────────────────────────── Odoo 17/18/19 ─────────────────────────────────┐
│  Reutiliza: account, purchase, hr_expense, approvals, follow-up, SEPA/OCA,     │
│             localización ES (N43, N19/N34, Facturae, SII)                      │
│                                                                                │
│  sd_treasury_base        Categorías, reglas, treasury.flow, posición de caja   │
│  sd_treasury_bank        Import N43/CAMT/XLSX, mapeo de cuentas, comisiones    │
│  sd_treasury_forecast    Multihorizonte, conversor de presupuesto, escenarios, │
│                          desviaciones                                          │
│  sd_treasury_collect     Riesgo, DSO, litigios, previsión de cobro real        │
│  sd_treasury_payment     Propuestas, firmas, beneficiarios, PSR (pain.002)     │
│  sd_treasury_financing   Préstamos, pólizas, EURIBOR, covenants, inversiones   │
│  sd_treasury_group       Consolidación, intragrupo, cash pooling, divisas      │
│  sd_treasury_report      Plantillas, export PDF/Excel, resumen del lunes       │
│  sd_treasury_dashboard   Cockpit OWL (escritorio y móvil)                      │
└───────────────▲────────────────────────────────────────────────────────────────┘
                │ API REST interna (HMAC) + webhooks + queue_job
┌───────────────┴──────────── sd-treasury-engine (FastAPI, Python) ──────────────┐
│  connectors/   PSD2 (GoCardless Bank Account Data, Salt Edge…), BCE/EURIBOR    │
│  ml/           Categorización, conciliación sugerida, previsión (statsforecast),│
│                anomalías                                                       │
│  ai/           Asistente en lenguaje natural (Claude API) + servidor MCP de    │
│                tesorería (OAuth con los permisos del usuario de Odoo)          │
│  workers/      Celery/RQ + Redis · PostgreSQL propio (datos crudos y tokens)   │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Por qué un engine separado** (a partir de la Fase 6): tokens PSD2 aislados de Odoo, librerías pesadas de ML sin cargar Odoo ni chocar con las restricciones de Odoo.sh, procesos largos fuera de los workers de Odoo y un servidor MCP con su propio ciclo de despliegue. Las Fases 1 a 5 funcionan **solo con Odoo**.

### Modelo de datos principal

```
treasury.category         Árbol de categorías (entrada/salida), cuenta contable por defecto
treasury.category.rule    Reglas: concepto / IBAN / partner / importe / diario → categoría
treasury.flow             TABLA CENTRAL. fecha, importe, divisa, empresa, cuenta bancaria,
                          categoría, estado (real | comprometido | previsto),
                          origen (extracto, factura, pedido, nómina, gasto, préstamo,
                          recurrente, presupuesto, manual), res_model/res_id, escenario
treasury.forecast.recurring  Previsiones recurrentes (alquiler, nóminas, cuotas)
treasury.budget           Presupuesto de caja por categoría y periodo (y conversor desde PyG)
treasury.scenario         Escenario + ajustes; un escenario puede heredar de otro
treasury.snapshot         Foto de una previsión en una fecha, para medir desviaciones
treasury.payment.batch    Remesa: firmas, estado del banco (PSR), historial
treasury.beneficiary.log  Cambios de IBAN de proveedores (antifraude)
treasury.debt             Préstamo, leasing o póliza: tipo fijo/variable, índice y diferencial,
                          cuadro de amortización, covenants
treasury.investment       Depósito o inversión: importe, tipo, vencimiento, interés devengado
treasury.pool             Cash pool: cuenta centralizadora, umbrales, propuestas de barrido
treasury.alert            Reglas de alerta e historial
```

`treasury.flow` unifica lo **real** (extractos), lo **comprometido** (facturas pendientes, con fecha ajustada por el retraso medio de cada partner) y lo **previsto** (pedidos sin facturar, nóminas, impuestos, cuotas de préstamos, gastos, presupuesto). Así una sola consulta da la posición en cualquier horizonte, por empresa, categoría o escenario.

---

## 4. Plan por fases

Cada fase entrega algo utilizable en producción. Las duraciones suponen 1–2 desarrolladores.

### Fase 0: preparación y análisis sobre vuestra instancia (1–2 semanas)
- Confirmar la versión y edición de Odoo y los módulos instalados (Enterprise y OCA); cerrar la tabla de cobertura de la sección 2.
- Repositorio, Docker (Odoo + PostgreSQL), CI (pre-commit, pylint-odoo, tests) y datos demo.
- Árbol de categorías por defecto (plantilla PYME y grupo español).

### Fase 1: liquidez (5–6 semanas), el MVP
*Equivale a «Gestión de liquidez» y «Seguimiento de tesorería» de Agicap.*
- Categorías y reglas; categorización automática de extractos y facturas, con sugerencia de crear una regla cuando el usuario recategoriza a mano.
- `treasury.flow` alimentado por extractos, facturas, pedidos y gastos.
- Import **N43, CAMT.053 y XLSX** (reutilizando OCA `l10n-spain` y `bank-statement-import` si encajan).
- **Cockpit**: saldo por banco y empresa, entradas y salidas por categoría, evolución diaria, cuadro de saldos actuales y futuros.
- **Previsión a 13 semanas** (vencimientos + recurrentes).
- Real vs. presupuesto básico; exportación a Excel.
- **Resumen del lunes** por correo y alertas de saldo bajo umbral.
- Seguridad: grupos Usuario y Responsable de tesorería, reglas multicompañía.

### Fase 2: previsión y escenarios (4–5 semanas)
*Equivale a «Previsión de tesorería».*
- **Multihorizonte**: diario (corto plazo), semanal (13 semanas) y mensual (12–24 meses).
- **Conversor de presupuesto o PyG previsto → plan de tesorería**: cada línea con su categoría y su plazo de cobro o pago (por ejemplo, IVA trimestral o ventas a 60 días).
- Previsiones automáticas de nóminas, Seguridad Social, impuestos (calendario de modelos 303, 111, 115, 200…) y alquileres.
- **Escenarios** vinculables (base → pesimista → «nueva contratación») y comparación lado a lado.
- **Análisis de desviaciones**: real vs. previsto (usando snapshots) y plan vs. plan, por categoría, empresa y periodo.

### Fase 3: cobros (4 semanas)
*Equivale a «Gestión de cobros».*
- Antigüedad de deuda, DSO por empresa y de grupo, segmentación por prioridad.
- Puntuación de riesgo (importe × retraso histórico × límite de crédito) y bloqueo al superar el límite.
- Recordatorios escalonados con plantillas y **enlace de pago**, sobre `account_followup` o OCA si están instalados.
- **Litigios**: marcar una factura en disputa pausa sus recordatorios.
- La previsión usa el **comportamiento real de pago** de cada cliente.

### Fase 4: pagos y control de pagos (4–5 semanas)
*Equivale a «Pagos / Payment Factory». La parte de AP y gastos se queda en Odoo.*
- **Propuestas de pago** según vencimientos, prioridad y caja disponible en cada banco.
- **Firma simple o doble** según importe o empresa, con historial de firmas y aprobación desde el móvil (vista responsive).
- **Antifraude de beneficiarios**: los cambios de IBAN de proveedores se registran, se bloquean hasta validarlos y generan una alerta.
- Generación **pain.001 / pain.008** (y N34/N19/confirming vía OCA `l10n-spain`).
- Import de **estados de pago pain.002 (PSR)** para actualizar el estado de cada remesa.

### Fase 5: financiación, inversiones y grupo (6–7 semanas)
*Equivale a «Financiación e inversiones», «Consolidación», «Cash pooling» y «Gestión de deudas».*
- Préstamos, leasing y pólizas de crédito, a tipo fijo o variable, con **cuadro de amortización** automático que alimenta la previsión.
- **EURIBOR diario** desde la API pública del BCE para recalcular los intereses variables.
- KPIs de deuda (principal pendiente, intereses pagados y por pagar, servicio de la deuda, deuda neta) y **covenants** con alertas.
- Inversiones y depósitos: excedente invertible, simulación por horizonte, intereses devengados.
- **Consolidación** de grupo multidivisa (vista grupo ↔ entidad).
- **Intragrupo**: detección automática de flujos entre sociedades del grupo, préstamos y cuentas corrientes intragrupo con cálculo de intereses.
- **Cash pooling**: pools, cuentas centralizadoras y umbrales; sugerencias de barrido que se convierten en remesas de la Fase 4.
- **Reporting**: plantillas de pool bancario y comisiones, cash burn y runway, desviaciones, deuda, excedentes y DSO; exportación a PDF y Excel.

### Fase 6: conectividad PSD2 e IA (6–8 semanas)
*Equivale a «Agicap AI», «MCP» y la agregación bancaria.*
- Engine FastAPI con conector **PSD2** (GoCardless Bank Account Data como primera opción, Salt Edge como alternativa) que sincroniza diariamente con `account.bank.statement.line`.
- **ML**: categorización automática con umbral de confianza, sugerencias de conciliación y previsión estadística de flujos no facturados.
- **Detección de anomalías**: pagos duplicados, importes atípicos, desviaciones bruscas.
- **Asistente en lenguaje natural** (Claude API) que responde y explica desviaciones con datos de `treasury.flow`, y permite recategorizar en bloque con revisión antes de aplicar.
- **Servidor MCP de tesorería** con herramientas de alto nivel (`posicion_caja`, `prevision`, `desviaciones`, `dso`, `recategorizar`) que respetan los permisos del usuario de Odoo. Permite automatizar el «informe del CEO del lunes» o el pack para el consejo.

### Fase 7 (opcional, según demanda)
- Conectividad bancaria corporativa **EDITRAN / EBICS / H2H** (directa o mediante un partner).
- Exposición a divisa y simulación de coberturas (forwards, Cap, Swap).
- App móvil nativa con notificaciones push, si la vista responsive no basta.

**Total orientativo: 7–9 meses** para las Fases 0–6.

---

## 5. Estructura del repositorio

```
sdtreasury/
├── addons/
│   ├── sd_treasury_base/  sd_treasury_bank/  sd_treasury_forecast/
│   ├── sd_treasury_collect/  sd_treasury_payment/  sd_treasury_financing/
│   ├── sd_treasury_group/  sd_treasury_report/  sd_treasury_dashboard/
├── engine/                 (Fase 6) app/{api,connectors,ml,ai,mcp,workers}
├── docker-compose.yml      odoo + postgres (+ engine + redis)
├── docs/
└── .github/workflows/ci.yml
```

## 6. Decisiones técnicas clave
- **Rendimiento:** `treasury.flow` materializada e indexada (fecha, empresa, categoría, estado, escenario), actualizada por hooks y un cron de reconciliación; agregaciones con `read_group`/SQL.
- **Trazabilidad:** cada flujo apunta a su documento origen para el drill-down; el chatter audita escenarios, firmas y beneficiarios.
- **Seguridad:** tokens PSD2 cifrados solo en el engine; Odoo ↔ engine con HMAC sobre HTTPS; MCP con OAuth y los permisos del usuario.
- **No duplicar Odoo:** detectar módulos Enterprise u OCA instalados y apoyarse en ellos (`follow-up`, `sepa`, `payment_order`, préstamos).
- **Tests:** unitarios por modelo, tours OWL del cockpit, datos demo de un grupo con varias sociedades.

## 7. Preguntas abiertas
1. ¿Qué **versión y edición** de Odoo tenéis en producción, y qué módulos OCA usáis?
2. ¿Despliegue en **Odoo.sh** u on-premise? Odoo Online no admite módulos propios.
3. ¿Es para **uso interno** o un **producto para clientes** de SmallDev? Afecta a la licencia (LGPL u OPL) y a si el engine debe dar servicio a varios clientes.
4. ¿Cuántas sociedades, bancos y divisas? ¿Hay UTEs o holding con préstamos intragrupo?
5. ¿Qué es más urgente después del MVP: previsión, cobros, pagos o financiación?
