# AW8 prerequisite remediation — revision 02

## Resultado

`AW8_PREREQUISITES = PARTIAL`  
`SAFE_TO_RESUME_AW8 = false`

| Prerrequisito | Resultado | Alcance y evidencia |
|---|---|---|
| PRODUCTIVE_BROWSER_TOOL_PATH | PASS | Rama productiva implementada y contratos de wiring verificados. No equivale a E2E ni a disponibilidad nativa certificada. |
| EXCLUSIVE_PUBLIC_ONLY_EGRESS | BLOCKED | Falta prueba exhaustiva del proceso/children, HTTPS confiable y prevención de todos los schemes iniciados por páginas. |
| TRUTHFUL_ACTIVE_WEB_CAPABILITY | PASS | El probe real alimenta la misma factory/snapshot/service. UNKNOWN permanece cerrado y no registra tools. |

Se preservan literalmente el `AW8 = BLOCKED` original y la primera remediación `PARTIAL / SAFE_TO_RESUME_AW8=false`. No se modificó ningún manifest previo ni se ejecutó la campaña AW8 final. No se declara READY.

## Baseline, normas y reutilización

Branch `main`, HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`, working tree heredado sucio y staging vacío. El freeze previo conserva 2309 pins. El delta autorizado tiene 12 archivos existentes y 6 nuevos de código/tests/inventario; listado y hashes completos en [component_freeze.json](component_freeze.json).

Arquitectura: `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`, sin cambios. Aplican §15, §17, §18, §25–27 y AW-INV-007/008/027/028/029/030, junto con owner/refs, exact approval, outcomes y presupuestos heredados. No se detectó contradicción normativa ni se redujo PUBLIC_ONLY.

Se reutilizan AgentSessionCoordinator, AgentLoop existente, ToolRegistry, ToolRuntime, BrowserPolicyEngine, ApprovalGate/GrantIssuer, SecurityAudit, BrowserSessionManager, ObservationService, transfer/takeover AW6, proyección AW7 y BrowserEgressBroker/PlaywrightBrowserAdapter. Core/Security/Memory/Knowledge no se recertifican ni cambian sus schemas.

## Integración productiva

Los roots reales CLI y JSONL (backend también usado por Desktop) incorporan una única `ActiveWebFactory`:

`root → ProductiveBrowserBackend.discover → probe_productive_browser(backend=self) → capability_from_probe → snapshot → ToolRegistry → ToolRuntime → Policy → Approval/Grant → ActiveWebService → BrowserRuntime/broker`

La rama positiva implementa nueve descriptores reales: browser_open, browser_observe, browser_navigate, browser_act, browser_form_submit, browser_upload, browser_download, browser_takeover y browser_close. Su execute directo falla; sólo ToolRuntime puede ejecutarlos. No se registran en get_default_tools, no hay selectors/evalJS ni autoridad browser de fallback.

Application construye el plan desde argumentos tipados, refs/owner/deadline y la intención explícita del usuario del Turn; no consume planes privados del harness. El host incorpora únicamente capabilities browser SESSION acotadas al ceiling existente; mutaciones conservan approval exacta y grants normales. Upload usa selección host autenticada y ref opaca; takeover conserva pausa/epoch; observación usa ContextManager y datos no confiables. CLI/JSONL tienen controles host autenticados, sin browser privilegiado en Electron ni grants emitidos por renderer.

Los 74 contratos enfocados verifican la superficie de nueve tools, ausencia ante UNKNOWN/false, todos los canales obligatorios del gate, error posterior de runtime, mediación/durable audit, exact approval, ownership, rechazo de argumentos spoof, selección upload opaca/idempotente y host JSONL autenticado. El snapshot positivo inyectado es **sintético, sólo wiring**, nunca prueba de este host.

## Capability real: fail-closed

La discovery productiva invoca el mismo backend/broker/configuración del runtime, no un diagnóstico que pueda activar el producto mediante flags o archivos. Sólo se coalescen/cachean resultados cerrados; ninguna prueba usable se reutiliza por esa cache.

[capability_probe.json](capability_probe.json) conserva la ejecución nativa explícita:

- engine KNOWN / PLAYWRIGHT_CHROMIUM;
- SDK 1.63.0; Chromium 153.0.8010.12;
- networkBroker KNOWN / true;
- controlClass KNOWN / HOST_UNISOLATED;
- publicOnly UNKNOWN; available UNKNOWN;
- tools registradas: **0**; misma identidad de backend y snapshot;
- otros metadatos V1 todavía no medidos permanecen UNKNOWN.

Instalar/importar Chromium/Playwright no abre el gate. Fallo o incompletitud del probe/runtime no habilita fallback BEST_EFFORT. El gate completo exige 20 obligaciones de egress y los metadatos V1 requeridos, no sólo presencia de un proxy.

## Egress: qué está y qué no está demostrado

Se agregan hardening process-local de WebRTC/WebTransport/background/DNS y rechazo explícito de service-worker registration además del bloqueo del contexto. No hay cambios globales, firewall externo, CA global, bypass de certificados ni claims de sandbox.

La prueba nativa controlada usa **Chromium real y ToolRuntime real**, pero snapshot positivo sintético y topología pública simulada por resolver/broker hacia endpoints loopback propios. Esto no convierte loopback en autoridad PUBLIC_ONLY real.

Observado:

- HTTP, redirect, subresource y segundo origin atraviesan el broker;
- CONNECT HTTPS atraviesa el broker, pero la página con certificado fixture no confiable se rechaza: **HTTPS renderer confiable NOT_DEMONSTRATED**;
- contexto secure: WS/WSS CLOSED, service-worker registration DENIED, cero workers y ninguna request /ws,/wss,/worker.js; WebRTC/WebTransport undefined;
- las flags QUIC/DNS/proxy bypass son configuración comprobada, **no** prueba exhaustiva de sockets;
- probe productivo separado sin sustitución de endpoints: 7/8 denegaciones privadas exactas observadas; https-metadata quedó UNKNOWN por ausencia de registro de denegación en ese intento, no PASS por ausencia de conexión;
- broker detenido: HTTP/HTTPS fallan y canary TCP loopback alcanzable por host recibe cero conexiones del browser; cleanup confirmado. Alcance limitado, no demuestra ausencia de cualquier fallback UDP/TCP.

Continúan abiertos en AW8-PREFLIGHT-002:

1. observación exhaustiva de conexiones TCP, UDP/QUIC, DNS útil y background de Chromium y children;
2. HTTPS público admitido con renderer confiable y controles intactos;
3. prevención pre-effect de todos los schemes iniciados por la propia página, incluyendo internal/file/javascript/data/custom;
4. prueba nativa completa de metadata V1 y de la denegación https-metadata no concluyente.

El harness actual **no** aporta un canary UDP/proceso-wide ni una traza exhaustiva Windows. No se presenta la ausencia de hits en los endpoints controlados como prueba universal. Flags/API ausente tampoco equivalen a aislamiento o BROKER_ENFORCED certificado.

Detalle y raw preservado: [egress_evidence.json](egress_evidence.json). Por §18.3 y AW-INV-027/029, esos faltantes impiden abrir la capability y reanudar AW8.

## Regresiones finales sobre código congelado

| Gate | Resultado |
|---|---|
| Wiring revision02 | 74 PASS, 0 FAIL/ERROR/SKIP |
| Active Web completo (componentes + nativos) | 691 PASS, 0 FAIL/ERROR/SKIP |
| Security | 615 PASS, 0 FAIL/ERROR/SKIP |
| Memory | 791 PASS, 0 FAIL/ERROR/SKIP |
| Knowledge | 1015 PASS, 0 FAIL/ERROR/SKIP |
| Core/current positive HEAD inventory | 3400 PASS, 1 FAIL histórico, 7 SKIP históricos, 53 subtests PASS, 0 ERROR |
| Desktop | 71 PASS, 0 FAIL/SKIP; TypeScript exit 0 |
| Inventario estático CI | PASS: 4043 contratos clasificados; 0 sin clasificación |

Core: 3408 instancias principales; XML incluye además 53 subtests = 3461 entradas. No se suman suites solapadas como cobertura única. Los siete skips son exactamente los de la primera remediación: tres symlink/privilegios Windows, dos POSIX mode y dos monitor legacy. Sin nuevos skip/xfail/exclusiones.

Único FAIL final: `tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`, **PREEXISTING_CORE_HARNESS_DEBT / NON_BLOCKING_FOR_THIS_REMEDIATION**. PowerShell HOME refleja USERPROFILE privado, mientras el test compara HOME privado. Código/test/runner/assertion asociados permanecen idénticos. No se lo declara PASS ni se lo filtra.

Comandos exactos, denominadores, JUnit timestamps/duración (end derivado), SHA-256, skips, exit codes y trazas están en [test_results.json](test_results.json). Outputs fuera de Git:

`C:/Users/joseh/AppData/Local/Temp/nova-aw8-revision02-20261010/`

Python explícito 3.14.6, pytest 9.1.1; plugin autoload/config privada deshabilitados. CI ordinary sigue sin descargar engines ni realizar inferencia. El inventario agrega 14 contratos portables de wiring y un contrato nativo local ejecutado explícitamente; filas/reglas previas se reconstruyen byte-a-byte con SHA original. No se cambian workflows ni runners en revision02.

## Fallos intermedios preservados

No se borran ni convierten en PASS los runs fallidos. [test_results.json](test_results.json) enumera las clasificaciones:

- setup/config/fixtures de harness corregidos sólo en infraestructura nueva;
- defecto nativo real de service-worker register stub, reparado;
- regresión introducida en diagnóstico console SDK, reparada sin cambiar el test AW5;
- error tipado browser/schema mapeado sin debilitar la assertion;
- primer comando Desktop omitió transform-types y falló 2 tests: log intacto, no aceptado como PASS;
- primer checker de integridad comparó list/string para tags y reserializó JSON con otra whitespace. Output intacto en integrity_initial.json; comparación de refs y reconstrucción literal correcta demuestran preservación.

## Integridad y cierre

[integrity.json](integrity.json): cero drift no autorizado, cero drift del freeze final, 1585 documentos históricos y 372 artefactos externos históricos intactos. HEAD/tags/staging sin cambio. Arquitectura y evidencia original AW8/primera remediación/AW0–AW7 intactas.

AW8-PREFLIGHT-001: **CLOSED para implementación de la ruta condicional**, no anuncio de disponibilidad/E2E.

AW8-PREFLIGHT-002: **OPEN / CERTIFICATION_PREREQUISITE_UNKNOWN**. No se reduce a BEST_EFFORT.

`AW8_PREREQUISITES = PARTIAL`  
`SAFE_TO_RESUME_AW8 = false`

No campaña AW8 final, inferencia LLM, READY, commit, push, tag, release ni avance. Se detiene para revisión humana.
