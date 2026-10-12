# AW3 — Policy, effects y approvals

AW3 = PASS

Cierre contractual de fase, no certificación de un navegador real ni READY global. Fuente normativa: [arquitectura](../../architecture/NOVA_ACTIVE_WEB_ARQUITECTURA_V1.md), §35 AW3: **«Cierre: no action mutating sin policy/approval.»**

## Baseline y preflight

- Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.
- Working tree heredado sucio, sin staging; conservado en `baseline_freeze.json`. Tags Core/Security/Memory/Knowledge intactos.
- Arquitectura SHA-256: `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`.
- Python 3.14.6, pytest 9.1.1; venv nativo offline ya instalado, Node 24.16.0; Windows 11 build 26200, C: NTFS local, HOST_UNISOLATED.
- Regresión **antes** de cambios: 351 PASS / 1 FAIL heredado HOME/USERPROFILE. Sin errores/skips.
- AW0 ejecución original PARTIAL y cierre aditivo PASS permanecen distintos; AW1/AW2 PASS contractuales permanecen históricos. No se reabre ni repinnea una certificación.
- Componentes reutilizados y alcance ausente: `preflight.json`. AW2 manifest/pins coincidían al iniciar; sólo su service de observations recibe la extensión mínima AW3 compatible por defecto.

## Implementación

1. Core puro: taxonomía de efectos mediante enums AW0 existentes, risk facts host-owned, `BrowserDispatchReport` y puerto abstracto. Sin Infrastructure/dependencias/browser engine.
2. `BrowserPolicyEngine` opt-in conserva PolicyEngineV2, ceiling, revisions y subset checks. Click/key inciertos requieren approval; input/select son disclosure; high-impact se deniega. Señales de página sólo pueden aumentar restricción, nunca otorgar autoridad.
3. `GrantRequest.network_intent` existente liga session/page/nav/observation/element/form-target/origin/action/payload/effects/contextEpoch/deadline y fingerprint/version. Ningún schema Security/DataKeys, GrantIssuer ni ApprovalGate fue modificado.
4. Application construye la presentación estructurada redacted y reutiliza la decisión exacta del ledger de ApprovalGate. Un grant mutante claimed sin esa decisión sigue denegado. `--yes`, page data, renderer JSON y falso actor no aprueban.
5. ToolRuntime es la única ruta agentic. Hook opcional deshabilitado por defecto, sin fallback al executor/cache legacy ni nuevos tools en `create_tools`. Nombres/unions de §15 son contratos de routing internos, no capabilities públicas.
6. Revalidación pre/post AW2, invalidación one-use, lease/deadline/token AW1 y audit pre-effect durable existente. Selector libre, state/origin/fingerprint drift, expiry/cancel, owner/child/workspace mismatch y audit failure impiden efecto.
7. Receipts V1 honestos: NOT_STARTED, STARTED sólo en acknowledgement del engine falso, SUCCEEDED_OBSERVED, FAILED_NO_EFFECT_CONFIRMED con prueba explícita, PARTIAL y UNKNOWN. UNKNOWN → Core OUTCOME_UNKNOWN/EffectState.UNKNOWN; no retry ni rollback ficticio; cadena mutante detenida aunque cambien IDs. Reconciliation read exige otra autorización.
8. 31 base contracts nuevos añadidos al inventario CI positivo; todos sus 94 parameter cases se ejecutan en el job Core. Regla nueva exclusivamente sintética/contractual, sin cambiar workflows, selectors anteriores ni exclusiones.

La ejecución contractual cubre targets element-bound emitidos por AW2. No constituye la implementación completa de tools, navegación/observe/act de engine real de AW5. PUBLIC_ONLY aquí es **binding lógico**, no evidencia de un egress broker; disponibilidad real continúa UNKNOWN/no habilitada.

## Historia de desarrollo preservada

- `development-1`: 1 ERROR de fixture (enum APPLIED, no COMMITTED).
- `development-2`: 21 PASS / 54 FAIL: descriptor JSON nuevo sin propiedades y audit fixture dentro de workspace; errores HARNESS_BUG, corregidos al contrato vigente.
- `development-3`: 71 PASS / 4 FAIL: lector de audit confundía header con record; DTO/data-classification inválidos en fixtures; factory sin frontend.
- `development-4`: 74 PASS / 1 FAIL: fixture sin callback requerido.
- `development-5`: 82 PASS / 1 FAIL: disponibilidad es Observation.available, no snapshot.status.
- `development-6/7`: 93 PASS; primeras regresiones completas y `product_freeze.json` se conservan, pero no fundamentan por sí solas el cierre.
- Revisión de integración añadió un contrato de cuota: primera preparación `navigation-quota-pre-fix` registró HARNESS_BUG por acceder a tuple como dict; la caracterización corregida registró **PRODUCT_BUG_AW3, 93 PASS / 1 FAIL: contador de navegación 0 != 1**.
- Reparación mínima: despacho navegación consume cuota/timeout AW1 bajo guard atómico, valida identidad antes de dirtied refs, y traduce errores lifecycle pre-dispatch a denegación tipada sin efecto. AW1 límites/manager permanecen intactos. La captura fresca no rebindea una approval obsoleta.
- `navigation-quota-post-fix`: AW0–AW3 372 PASS. Se preserva freeze inicial; `product_freeze_v2.json` gobierna las regresiones finales. También se evita lock inversion entre gate/plan usando una decisión exacta ya resuelta antes de tomar el plan lock.
- Ningún FAIL se convierte en skip/xfail; no se debilitan assertions/schema. XML, hashes y denominadores completos de **todas** las corridas están en `test_results.json`.

## Criterio por criterio

| Entregable / gate §35 AW3 | Resultado | Evidencia |
|---|---|---|
| BrowserEffectClass | PASS | 16 ActionKinds; clicks/input/host risk; Core puro |
| policy branches | PASS | read acotado, mutation/disclosure approval, high-impact deny, unavailable fail-closed |
| exact approval binding | PASS | target/state/actor/digest/claim; 13 variantes de drift, payload privado y fresh fingerprint |
| action receipts | PASS | states honestos; no éxito/no-effect sin prueba |
| UNKNOWN outcome rules | PASS | timeout/disconnect/cancel/late; no retry, no rollback, mutation-chain stop |
| no action mutating sin policy/approval | PASS | ruta ToolRuntime existente, decisión exacta, claim y audit obligatorios |

Tests concretos y trazabilidad de los 50 AW-INV (sin afirmar 50 PASS reales) en `manifest.json` y `invariant_matrix.json`. Perfiles/transfer/broker/engine posteriores se marcan deferred, no PASS ficticio.

## Regresiones del producto final congelado V2

| Gate | PASS | FAIL | SKIP | SHA-256 JUnit |
|---|---:|---:|---:|---|
| final-v2-core | 3111 | 1 | 7 | c43127d82744755fc09dfd092783fd03da0b0721772a7fca652c3c1aa5a1cd72 |
| final-v2-knowledge | 1015 | 0 | 0 | bd1e0339ea42e65ea4943ad3a1a9b8edebcbc1d1148cbeb9f228b3c5133d5691 |
| final-v2-memory | 791 | 0 | 0 | 70e256fa2adc5f07bc7835e0e6063d56379613bffd619a5003a88c68fec89abe |
| final-v2-security | 615 | 0 | 0 | b4568f28d7cec4a4385da351eb8c9db7fbc2ee05a96fea8015119f1ff9a399df |

- AW3: **94/94 PASS**, incluidos en Core, no sumados otra vez.
- Focal final V2: **445 PASS / 1 FAIL heredado**, 0 ERROR.
- Selecciones completas vigentes: **5532 PASS / 1 FAIL heredado / 0 ERROR / 7 skips históricos**, más **53 subtests PASS**. Denominador 5540 parameter instances, subtests separados.
- Desktop: **68/68 PASS**, 0 skips/cancelled; TypeScript `tsc --noEmit` exit 0. Sources frontend intactas, evidencia aplicable a V2.
- **newFailures=0, newSkips=0, newXfails=0** contra AW2. No nuevos filtros ni retries por calidad.
- Los 7 skips: dos symlinks sin Developer Mode, un symlink WinError1314, dos POSIX mode Windows y dos legacy monitor ya retirado. No son los 11 skips de una antigua selección HEAD distinta.
- Memory contiene un parámetro histórico `new_session_id()` generado al importar: su UUID cambia entre procesos y por tanto cambia el SHA de collected nodeids. Source, selección, denominador y demás IDs no cambian; raw artifacts intactos, no normalizados/repinneados.
- Comandos exactos, runtime, duración/start/end, collection guards, XML/log/selection hashes: `test_results.json`.
- Outputs privados fuera de Git: `C:/Users/joseh/AppData/Local/Temp/nova-aw3-20261009T180059Z`. No SQLite, audit runtime ni caché de prueba incorporados al workspace.

## Deuda Core visible, no nueva regresión

`tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`

**PREEXISTING_CORE_HARNESS_DEBT — NON_BLOCKING_FOR_AW3**. El runner privado separa HOME/USERPROFILE; PowerShell devuelve su HOME basado en USERPROFILE. Reproducido antes/después; test/assertion, BashTool y runner no fueron modificados. El test sigue FAIL y los jobs/focal correspondientes siguen exit 1: **Core no se anuncia verde**.

El gate de fase §35 exige policy/approval y §37.29 mantiene aplicable la regresión heredada: evidencia baseline/final demuestra ausencia de regresiones AW3. No exige borrar deuda histórica ni habilita READY global. Esta evaluación no reescribe AW0 ni sus resoluciones.

## Integridad, límites y siguiente referencia

`integrity_final.json`: architecture/history intactas, aggregate de 2179 tracked archivos fuera del delta autorizado coincide, pins V2 sin drift, raw CI previo reconstruido byte-a-byte, index vacío y tags/HEAD/branch sin cambios.

Limitaciones: adapter y actor browser de tests son doubles; sólo audit de filesystem usa el puerto durable real local. No real-browser/model E2E, certificado Linux/macOS, detector semántico universal de riesgos ni DLP universal. Sin broker/DNS/CONNECT/probes, Playwright, auth/takeover/transfers, nuevos frontends, Memory/Knowledge writes o schemas/migrations/dependencias nuevos.

MEMORY y DOCUMENT SEMANTIC_PROFILE permanecen NOT_CERTIFIED. Browser availability UNKNOWN; no ACTIVE_WEB_CORE READY ni certificación heredada nueva. Ninguna OPEN DECISION material para este scope; decisiones/capabilities de fases posteriores permanecen diferidas.

Siguiente fase lógica: **AW4 — Network broker**, sólo referencia; **no implementada**. No commit, push, tag ni release. Detención para revisión humana.

