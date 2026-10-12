# AW8 — E2E y certificación: preflight bloqueado

AW8 = BLOCKED

Evaluación: 2026-10-09 21:42:15 UTC. Únicamente AW8; no fase posterior, READY, commit, push, tag ni release.

## 1. Baseline preservado

Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`. Working tree heredado AW0–AW7 dirty, staging vacío. Se congelaron 2.292 archivos antes de esta tarea; ninguno cambió. Cinco tags intactos.

AW7 = PASS permanece intacto: `docs/active_web_v1/aw7/manifest.json`, SHA-256 `68460552d16b664a850146b477d02d7c996fd927735e98b30b72b41be499fa37`. No se reabre ni recalifica ninguna certificación Core/Security/Memory/Knowledge/AW0–AW7.

Arquitectura SHA-256 `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`, sin modificaciones. Auditoría y findings siguen siendo contexto técnico.

## 2. Alcance normativo y criterio de cierre

§35 AW8 enumera nueve entregables: real browser deterministic tasks, multi-step, stale refs, approval, unknown outcome, network denial, download/upload, manual takeover boundary y cleanup; prohíbe reutilizar K8/SCF.

No contiene una frase autónoma `Cierre:` para AW8. Se evalúan literalmente esos entregables junto con las fronteras heredadas, sin inventar un threshold numérico o exigir calidad LLM que la sección no define:

- §3.2: `model request → ToolRegistry → Policy → Approval (si aplica) → Grant → claim → revalidación → BrowserRuntime → receipt/audit`.
- §23: se reutiliza el loop actual, no un segundo AgentRuntime.
- §18.3: si el adapter no demuestra ausencia de bypass relevante, Active Web Core no se anuncia disponible.
- §25 y AW-INV-007–008: UNKNOWN no es true; engine/broker instalados no bastan para anunciar tools.
- §37.30: E2E real debe cubrir navegación multi-step, formularios, approvals, stale refs y outcomes.

No se declara READY global en esta tarea.

## 3. Componentes reutilizables, sin confundirlos con E2E terminado

Existen BrowserSessionManager, opaque Page/Observation/Element refs, BrowserActions/Policy, ToolRuntime/ApprovalGate/GrantIssuer, broker, adapter real Playwright/Chromium, transfers/staging, takeover host opaco, frontend projections y SecurityAudit.

Las suites AW5–AW7 ejecutan Chromium real y algunas acciones por ToolRuntime; esto es evidencia válida de componentes/integración sintética. Los fixtures usan un descriptor explícitamente `ContractOnlyBrowserTool` y planes privados instalados por el host. No constituyen certificación del loop/producto completo.

## 4. Bloqueos concretos

### AW8-PREFLIGHT-001 — PRODUCT_INTEGRATION_GAP

El registro productivo `get_default_tools` contiene:

`bash, read, write, edit, glob, grep, web_fetch, todo_write, ask_user`.

Número de tools `browser_*`: **0**. En Application, `active_web_factory` es un seam opcional de composición host; no existe caller productivo que registre la superficie browser del modelo. Las constantes/routing names de BrowserActions no son tool registrations.

El contrato histórico `test_unimplemented_browser_name_has_no_generic_legacy_authority_path` pasa porque `browser_open` se **deniega sin efecto**, no porque se pueda abrir un browser desde el agente.

Esto impide certificar §23 como E2E productivo. Utilizar el descriptor test-only/ceiling sintético y presentar esa composición como soporte productivo omitiría la identidad del producto bajo prueba.

### AW8-PREFLIGHT-002 — CERTIFICATION_PREREQUISITE_UNKNOWN

La caracterización real, sin sustitución de admission del broker, observó:

| Campo | Estado / valor |
|---|---|
| engine | KNOWN / PLAYWRIGHT_CHROMIUM |
| engineVersion | KNOWN / 1.63.0 |
| browserVersion | KNOWN / 153.0.8010.12 |
| networkBroker | KNOWN / true |
| publicOnly | UNKNOWN / engine exclusive egress not certified |
| available | UNKNOWN / AW5 adapter is not ACTIVE_WEB_CORE READY |
| controlClass | KNOWN / HOST_UNISOLATED |
| Conexiones upstream de la prueba | 0 |
| Probe broker | BROWSER_EGRESS_DESTINATION_DENIED |
| Cleanup del contexto/worker | confirmado |

El componente broker y el engine funcionan; no hay evidencia de bypass real. Lo pendiente es la prueba completa de exclusividad egress y su composición/capability discovery productiva. El probe actual de denial loopback no demuestra esa exclusividad.

No se modificó UNKNOWN a true ni se ofreció fallback network best-effort. La sesión Application normal conserva `browserSession=null` y capabilities UNKNOWN.

### Decisión de alcance

No existe contradicción entre documentos ni una OPEN DECISION normativa nueva: las reglas de seguridad ya son claras. Existe una brecha material de implementación/prerrequisitos para la certificación final.

Se detiene antes de modificar producto o expandir AW8 hacia activación pública/composición browser/probes no terminados de las dependencias. Esto no contradice los PASS scoped anteriores, cuyas limitaciones estaban explícitamente documentadas.

## 5. Evaluación individual AW8

| Requisito §35 | Evidencia componente existente | Estado de certificación AW8 |
|---|---|---|
| real browser deterministic tasks | Chromium real en baseline y probe nativo | BLOCKED: sin ruta productiva anunciable |
| multi-step | Driver sintético AW5–7 / host ToolRuntime | BLOCKED: no E2E del AgentLoop productivo |
| stale refs | Contratos y tests nativos heredados pasan | NOT_EVALUATED en campaña AW8 |
| approval | ToolRuntime/host actor/exact binding heredados | NOT_EVALUATED en campaña AW8 |
| unknown outcome | Timeout/cancel/no-retry heredados | NOT_EVALUATED en campaña AW8 |
| network denial | Broker real rechaza loopback; baseline AW4–5 | PARTIAL: exclusividad egress pendiente |
| download/upload | Tests nativos AW6 pasan | NOT_EVALUATED en campaña AW8 |
| manual takeover boundary | Tests host-opaco/headful AW6 pasan | NOT_EVALUATED en campaña AW8; no claim humano real |
| cleanup | Contexto, worker y broker cerrados en probe | PASS del preflight; no sustituye campaña completa |

Ningún test con double o driver host se presenta como calidad real LLM ni E2E productivo. No se creó corpus/scorer/campaña AW8 para ejecutarla contra una identidad incompleta. K8/SCF no se usaron.

## 6. Verificaciones ejecutadas

1. Baseline pertinente, antes de cambios: AW4 network/proxy, AW5 engine, AW6 engine, AW7 engine/frontends y test HOME histórico.
   **172 PASS / 1 FAIL / 0 ERROR / 0 SKIP**, exit 1, 173 casos, 39.82 s.
2. Contrato directo de browser_open no implementado:
   **1 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, exit 0, 0.58 s.
3. CI inventory actual: **PASS**, 4.018 funciones, unclassified=0; sin ejecución de producto/inferencia.
4. Runtime preflight real: engine instalado, broker productivo, Application con tools default y provider sin inferencia; capabilities truthfully UNKNOWN; no conexiones upstream; cleanup confirmado.
5. Integridad: 2.292 pins del baseline sin drift, 288 artefactos externos históricos verificados sin drift; tags/HEAD/staging intactos.

Fallo que sigue visible:

`tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`

Clasificación: `PREEXISTING_CORE_HARNESS_DEBT`, HOME privado frente a USERPROFILE PowerShell. Reproducido antes de AW8; producto, test, runner/assertion sin cambios. **No es la causa del bloqueo AW8**, no se recalifica como PASS ni se añade skip/xfail/filtro.

Un primer comando de caracterización tuvo ImportError por importar ApplicationCommand desde Core en vez de Application. Se conserva en `preflight_runtime.json` como HARNESS_BUG de diagnóstico; ocurrió antes de iniciar browser/inferencia. Se corrigió únicamente el import del comando externo y se usó otro directorio. No hubo cambio de producto, assertions ni retry de calidad.

No regresiones masivas adicionales: no se modificó producto/tests/CI/harness; al detectarse la brecha se detuvo la implementación. Se reutiliza la evidencia AW7 íntegra sin presentarla como una nueva campaña AW8 verde.

## 7. XML y runtime

Output externo nuevo:

`C:/Users/joseh/AppData/Local/Temp/nova-aw8-20261009213551Z`

- `baseline/tests.xml`: SHA-256 `a02622e25650038a28f1df1f4b89b4ca4e8cb2f8caf3eb753ba8878326409cdd`.
- `missing-tool-contract/tests.xml`: SHA-256 `d3ff767a7eb1383b09bc5f3adec3f5e91cc9a362573771956c6c8c45f6a2f8fc`.

Comandos exactos, JUnit timestamps, exit codes, denominadores e integridad en `tests_integrity.json`. Runtime/DTO completo y límites en `preflight_runtime.json`. Python 3.14.6 explícito, pytest 9.1.1, venv AW5 existente; Windows 11 + NTFS local + HOST_UNISOLATED. Profiles/basetemp/output fuera de Git; sin modelos, sitios externos, configuración global ni descargas.

## 8. Archivos y continuación requerida

Sólo se crean evidencias nuevas en este directorio: baseline_freeze.json, preflight.json, preflight_runtime.json, tests_integrity.json, resultados.md y manifest.json. Cero archivos productivos/tests/CI/harness/arquitectura modificados. No nuevos skips/xfails/exclusiones ni cambio de histórico.

Para reanudar, debe resolverse primero la composición productiva/capability-gated browser del loop existente y la prueba real de mediación exclusiva PUBLIC_ONLY. Después podrá congelarse y ejecutar una campaña AW8 independiente. No se propone alterar invariantes ni activar tools UNKNOWN como workaround.

AW8 = BLOCKED. Detención para revisión humana, sin READY, commit, push, tag, release ni fase siguiente.
