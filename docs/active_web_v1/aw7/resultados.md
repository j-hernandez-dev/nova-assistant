# AW7 — Frontends, audit y CI: resultados

AW7 = PASS

Fecha de cierre: 2026-10-09 UTC. Alcance: exclusivamente §35 AW7 de la arquitectura aprobada, con §§26–27 y los AW-INV aplicables. No es READY ni certificación AW8.

## 1. Baseline y preflight

- Branch: `main`.
- HEAD evaluado y final: `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.
- Working tree inicial: cambios heredados AW0–AW6, sin staging. Se conservaron; no limpieza/restauración.
- Prerrequisito AW6 = PASS: manifest SHA-256 `142f14a6d03231b8e6a46cd1310e94f7fb3fe964702300271cffc87cbf965652`.
- Arquitectura SHA-256: `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`, intacta.
- Auditoría y findings conservados como contexto técnico, sin reinterpretar certificaciones.
- Freeze inicial: 2.274 archivos del repositorio; 251 artefactos históricos externos verificados.
- Baseline antes de modificar: 675 PASS / 1 FAIL / 0 ERROR / 0 SKIP; exit 1. El único fallo es la deuda HOME/USERPROFILE detallada en §5.
- No contradicción normativa material ni OPEN DECISION necesaria para AW7.

El inventario inicial, comando exacto, contratos reutilizados y archivos previstos están en `preflight.json` y `baseline_freeze.json`.

## 2. Alcance implementado y trazabilidad

| Requisito | Componente | Evidencia | Estado |
|---|---|---|---|
| §26.1: 16 eventos correlacionados | EventKind, BrowserFrontendProjection, SessionEventStream, servicios browser | Todos los tipos de evento, owner fencing, correlación, límites y snapshot defensivo | PASS |
| §27: DTOs Application comunes CLI/JSONL/Desktop | SessionCoordinator y binding host opcional; CLI, bridge y Desktop client | Un mismo backend/snapshot; comando browser paralelo rechazado; proyección no ejecutable | PASS |
| §27.2: Desktop proyecta estado, approvals, takeover, metadata y outcomes | DTO shared, client y App | Node, TypeScript y contrato de fuente; sin iframe/webview/páginas en renderer privilegiado | PASS |
| §26.2: audit durable antes de efectos | ToolRuntime + SecurityAuditService + JsonlSecurityAudit existentes | Flush anterior al SDK, append/flush failure deniega, binding completo, terminal durable | PASS |
| AW7: clasificación positiva CI | contract_inventory, run_contracts, pytest_contracts y workflow | 4.018 funciones clasificadas; selección/collection guard; contratos existentes conservados | PASS |
| AW7: fake y real-browser suites | test_aw7_frontends y test_aw7_engine | 31 instancias portables + 3 con Chromium real; sin skips nuevos | PASS |
| Cierre literal: frontend no crea authority path | Proyección read-only, ToolRuntime/Policy/Approval/Grant existentes, host actor opaco | Approvals exactas requieren host; JSONL no crea comandos browser; Desktop sólo consume DTOs | PASS |
| Compatibilidad heredada | Core, Security, Memory, Knowledge y Desktop | Regresiones actuales; 0 nuevos fallos/skips/xfails/exclusiones | PASS, con deuda Core heredada visible |

Se reutilizan BrowserSessionManager, BrowserObservationService, BrowserActions, BrowserTakeover, BrowserPolicyEngine, ApprovalGate, GrantIssuer, ToolRuntime, SecurityAudit, SessionSnapshot/event stream y transportes existentes.

### Proyecciones

Se añaden los 16 eventos normativos. BrowserActionStarted/NavigationStarted/BrowserUploadStarted representan acknowledgement real del engine, no intención de dispatch de ToolRuntime. Los eventos no sustituyen auditoría ni terminan por sí solos una Operation.

La proyección contiene sólo metadata allowlisted, sanitized y acotada: tres páginas, tres solicitudes takeover y 32 receipts; snapshots por copia defensiva, owner-session fence y referencias opacas. No contiene bodies, credenciales, engine handles, payloads de formularios, cookies ni paths privados. UNKNOWN sigue UNKNOWN; disconnect no reenvía acciones; cancel no equivale a rollback.

Application admite únicamente una composición opcional instalada por el host. No se añaden tool registrations públicas, grants, permisos ni ampliaciones del ceiling. Sin esa composición el snapshot declara capacidad UNKNOWN, no un browser disponible.

Desktop mantiene approvals por el canal host existente; takeover es una solicitud de interacción humana en Chromium separado, no una operación de login desde React. No se crea UI embebida ni un nuevo canal frontend para terminar takeover, seleccionar upload refs o aceptar downloads.

### Auditoría

El binding confiable de la acción browser registra IDs, epochs/version, fingerprint y payload digest dentro de `observationScope`, campo normativo existente. Origin se sanea; action/effect, approvals/grants y outcome se conservan por la ruta actual. No se amplía `SecurityAuditRecord.DATA_KEYS` ni el schema Security.

Antes del SDK se exige audit/flush durable. Si append/flush falla, no hay dispatch. Los tests cubren también UNKNOWN después de STARTED, audit gap terminal honesto, approvals host exactas y prohibición de retry. La evidencia demuestra el contrato JsonlSecurityAudit actual, no una garantía universal de fsync/disco/energía.

## 3. CI

Workflow nuevo: `.github/workflows/nova_active_web_v1.yml`.

- Push/PR: contratos positivos portables `--job active-web` en Windows/Linux/macOS; 202 funciones base por host. No engine ni modelo real.
- Manual explícito: `workflow_dispatch.native_browser=true`, Windows, `--job active-web-native --special`; dos funciones / tres instancias nuevas con engine real. La instalación del engine sólo está en ese job manual, no en push/PR.
- Desktop: workflow Knowledge conserva siete suites y añade la suite Active Web; TypeScript existente se mantiene.
- Permisos `contents: read`, checkout/config de line endings a nivel proceso y convenciones existentes. No nueva configuración global/caching.
- Inventario 4.018: 3.834 CURRENT_PORTABLE_CI, 26 LOCAL_CAPABILITY_CONTRACT, 89 HISTORICAL_CERTIFICATION_ARTIFACT y 69 SPECIAL_INFRASTRUCTURE_JOB. Ningún contrato previo se eliminó/reclasificó para esconder resultados.
- Las selecciones adicionales Active Web no retiran contratos del job Core. No filtros por resultado, skip/xfail nuevo ni retries.
- Runtime, perfiles, staging y basetemp están fuera del checkout Git.

Después de las ejecuciones se realizó un único delta de retención de artefactos del workflow: upload restringido a run/selection/nodeids/XML/log. No se suben perfiles/staging/private runtime. `product_freeze.json` se conserva; `product_freeze_ci_retention_v2.json` captura aditivamente ese delta. La reversión exacta del bloque recupera el SHA original; comandos, jobs, permisos, tests y producto runtime no cambiaron. La comprobación está en `ci_retention_check.json` e `integrity.json`.

Las ejecuciones CI locales fueron Windows. GitHub-hosted/Linux/macOS = NOT_EVALUATED; su selección está configurada/verificada estáticamente. No se afirma certificación host-real cross-platform.

## 4. Pruebas y resultados exactos

| Campaña final | Denominador | PASS | FAIL | ERROR | SKIP | Exit |
|---|---:|---:|---:|---:|---:|---:|
| AW7 focused antes del freeze, repetido en las suites finales | 34 | 34 | 0 | 0 | 0 | 0 |
| Active Web AW0–AW7 completa | 600 | 600 | 0 | 0 | 0 | 0 |
| CI Active Web portable actual | 572 | 572 | 0 | 0 | 0 | 0 |
| CI native AW7, Chromium real | 3 | 3 | 0 | 0 | 0 | 0 |
| Core actual | 3.319 instancias + 53 subtests | 3.311 + 53 subtests | 1 | 0 | 7 | 1 |
| SECURITY V1.2 actual | 615 | 615 | 0 | 0 | 0 | 0 |
| MEMORY actual | 791 | 791 | 0 | 0 | 0 | 0 |
| Knowledge actual | 1.015 | 1.015 | 0 | 0 | 0 | 0 |
| Desktop, ocho suites Node | 71 | 71 | 0 | 0 | 0 | 0 |
| TypeScript --noEmit | una comprobación | PASS | 0 | 0 | 0 | 0 |

Las selecciones se solapan: no sumar filas como tests independientes. Core JUnit contiene 3.372 entradas al incluir los 53 subtests; no convertirlos en 53 funciones nuevas.

Python 3.14.6, pytest 9.1.1; runtime de validación AW5 existente con Playwright 1.63.0; Chromium 153.0.8010.12/rev1243. Host Windows 11, C: NTFS local, HOST_UNISOLATED. Node 24.16.0 local. Tests reales usan un origen sintético sustituido en el adapter; no sitios públicos, modelo LLM ni credenciales/human-login.

Comandos exactos, denominadores, exit codes, fallos/skips, XML SHA-256 y duraciones: `test_results.json`. Timestamps JUnit, hashes de 37 artefactos estables y audit JSONL nativo: `runtime_evidence.json`. Outputs externos preservados:

`C:/Users/joseh/AppData/Local/Temp/nova-aw7-20261009205259Z`

La retención externa local es necesaria para reproducir los raw; no se copian perfiles/runtime privados al repositorio.

### Desarrollo preservado

Se conservan development-1 (7/27 PASS, 20 FAIL), development-2 (27 PASS), development-3 (30/31 PASS), development-4 (31 PASS) y development-5 (34 PASS). Los defectos nuevos de proyección origin/cleanup se corrigieron antes del freeze. Los errores de fixtures nuevos (JSONL helper, acción SCROLL no soportada por el link y nombre del API Desktop) se clasifican en `test_results.json`; no se debilitaron contratos históricos ni capacidades.

No son quality retries ni rescoring de campañas históricas; todas las ejecuciones y hashes previos permanecen.

## 5. Deuda Core preexistente, no escondida

Test que sigue fallando:

`tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`

Clasificación: `PREEXISTING_CORE_HARNESS_DEBT`, `NON_BLOCKING_FOR_AW7`.

La incompatibilidad HOME privado/USERPROFILE de PowerShell se reproduce en el baseline anterior a cambios AW7 y en Core final. Test, assertion y BashTool no cambiaron. Aunque run_contracts incorpora selección positiva adicional, su AST `private_environment` sigue igual.

Core conserva exit 1; no se informa como suite verde. La obligación de regresión de esta fase se satisface por ausencia de regresiones introducidas por AW7, no por eliminar deuda heredada. Esto es coherente con el cierre aditivo AW0 y no modifica sus históricos. No se añade skip, xfail ni filtro para ese test.

Los siete skips son exactamente los de AW6 (symlink/privilegio Windows, POSIX mode y monitor legacy retirado). Lista y razones íntegras en `test_results.json`.

`newFailures=0; newSkips=0; newXfails=0; newExclusions=0`.

## 6. Integridad y fronteras

- 18 deltas sobre archivos existentes y cinco archivos nuevos de implementación/test/CI: todos dentro de los 23 pins autorizados AW7.
- Resto del baseline sin drift; arquitectura, auditoría, findings, evidencia histórica y 251 artefactos externos históricos intactos.
- Freeze final sin drift, HEAD y cinco tags anteriores iguales, staging vacío.
- DATA_KEYS Security intacto; producto Memory y Knowledge sin cambios; PASSIVE_WEB separado.
- Los 50 AW-INV se trazan en `invariant_matrix.json` con estado scoped/preserved. No se presentan como 50 certificaciones globales nuevas. AW-INV-027 conserva el capability gate; egress global sigue sin certificar.
- No cambio de configuración global, modelos, datos reales de usuario ni descargas en esta ejecución.

Archivos de implementación/test/CI modificados o creados: lista completa y hashes en `product_freeze_ci_retention_v2.json`; audit de deltas en `integrity.json`. La evidencia propia AW7 se añade en este directorio y está referenciada por `manifest.json`.

## 7. Evaluación literal del cierre y limitaciones

Texto normativo §35:

> Cierre: frontend no crea authority path.

PASS: CLI/JSONL/Desktop sólo consumen DTOs/eventos del mismo Application; no crean grants ni Policy, no dispatchan browser actions por rutas paralelas ni alojan páginas no confiables en el renderer privilegiado. La auditoría durable y las suites fake/real demuestran el camino existente ToolRuntime/Policy/Approval/Grant. Los cuatro entregables AW7 existen y las regresiones introducidas son cero.

AW7 = PASS no significa Active Web V1 READY. `available/publicOnly = UNKNOWN` permanece honesto; la prueba de exclusividad egress global, activación pública y la campaña AW8 no están certificadas por esta fase. Vision, persistent session, private network y automated credential profiles no se certifican. MEMORY SEMANTIC_PROFILE permanece NOT_CERTIFIED.

No se afirma sandbox/process isolation, DLP universal, calidad de sitios reales, login real, GUI Desktop E2E, calidad LLM ni ejecución CI hosted. No nuevo schema de persistencia ni migraciones.

Se detiene para revisión humana. AW8 es sólo la siguiente referencia normativa; no implementada ni ejecutada. Sin commit, push, tag ni release.
