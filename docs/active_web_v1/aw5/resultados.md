# AW5 — Playwright/Chromium adapter

**AW5 = PASS** — cierre de fase, no `ACTIVE_WEB_CORE=READY`.

## Baseline y fuente normativa

Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`. Working tree heredado dirty, index vacío, tags intactos. Se preservaron los cambios anteriores y todas las certificaciones/historias; no hubo commit, push, tag ni release.

Fuente de verdad: `NOVA_ACTIVE_WEB_ARQUITECTURA_V1.md`, §35 AW5: «Cierre: real browser local controlled by contracts.» SHA-256: `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`. Auditoría/findings se usaron como contexto, no como override normativo. No se detectó contradicción material ni se modificó arquitectura.

Antes de modificar: 594 PASS / 1 FAIL histórico, 0 ERROR/SKIP. `baseline_freeze.json` conserva 2181 pins tracked y 64 inherited untracked. Se verificaron los pins aplicables AW4 antes del trabajo.

Reutilización: BrowserSessionManager/AW1, BrowserObservationService/AW2, BrowserActions/Policy/Approval/claimed Grant/ToolRuntime/SecurityAudit/AW3 y broker PUBLIC_ONLY/AW4. No segunda sesión/loop, Policy ni ruta frontend.

## Implementación acotada

- Extra opcional `active-web = ["playwright==1.63.0"]`, import lazy, error tipado si falta; no instalación automática desde producto/CI. Licencia Apache-2.0 y Python >=3.10 compatibles con el mínimo declarado Nova; runtime probado Python 3.14.6. [Metadata oficial](https://pypi.org/project/playwright/).
- Adapter privado Infrastructure, worker asyncio acotado por deadline/cancelación. Chromium independiente de Electron, headful por defecto, contextos efímeros sin personal profile/storageState/API de cookies para el agente.
- Navegación HTTP(S), captura renderizada acotada, handles privados/fingerprint/refs opacos, rechazo de stale/detached sin rebinding. Scripts de inspección fijos del adapter, no selectors/JS del modelo.
- Acciones mediante contratos existentes. Tests nativos usan ToolRuntime/Policy/aprobación exacta/Grant y audit durable; input rechazado tiene NONE, submit aprobado produce un POST real sintético.
- Cancelación después de STARTED produce UNKNOWN; no retry ni rollback ni sustitución por un resultado tardío. Cancelación por página; cleanup confirmado sólo si se observa.
- Diálogos dismiss/popups close por defecto; drive-by downloads cancelados. Inputs sensibles y formularios identificados como credentials no se automatizan.
- Broker autenticado obligatorio y probe fresco antes de launch. Service workers bloqueados, WS/WSS rechazados, RTC removido del runtime, QUIC flag fijo. Son controles/fixtures concretos, no certificación universal de egress. [Contratos SDK](https://playwright.dev/python/docs/api/class-browsercontext).

### Interoperabilidad descubierta y corregida

La primera corrida nueva terminó 22 PASS / 6 FAIL nativos: el broker AW4 respondía 403 al cliente sin credenciales; Chromium requiere un challenge para enviar proxy authentication. Fallaba antes de admisión/render; los demás fallos eran consecuencias.

Único delta del broker heredado: 407 con `Proxy-Authenticate` exclusivamente para `BROWSER_EGRESS_CHANNEL_DENIED`. Los otros errores siguen 403; nunca se resuelve DNS ni conecta upstream antes de autenticación. El handshake pre-effect no es retry de una acción STARTED. [RFC 9110 §11.7 y §15.5.8](https://www.rfc-editor.org/rfc/rfc9110.html).

Se reconstruyó byte-a-byte el broker previo quitando exclusivamente ese delta: SHA original `9138eba7d121381e764a87f50809dd6b3423b64797efa8827e9d0e4726bc8570`. La evidencia AW4 original permanece intacta; no se convierte retrospectivamente en certificación de browser real.

CI: sólo clasificación positiva mínima necesaria de los tests nuevos (9 base portables/12 base engine). Workflows/runner/selectores anteriores sin cambios. Engine native se ejecutó explícitamente fuera de CI normal; ausencia de engine falla, no skip. Sin implementación AW7.

## Criterios de cierre

| Requisito §35 AW5 | Evidencia | Estado |
| --- | --- | --- |
| Optional dependency | Import sin engine/installer, capability ausente tipada antes de broker | PASS |
| Launch | Chromium real 153.0.8010.12/rev1243 headful/headless; headful default | PASS |
| Context/page | Ownership/quota heredados, contextos efímeros, cleanup observado | PASS |
| Navigation | Navegación/link/history reales, refs stale y broker productive deny | PASS |
| Observe | Texto acotado/redaction, handles privados, fingerprint, no heuristic rebind | PASS |
| Act | Runtime/Policy/Approval/Grant/audit, input/select/POST, cancel UNKNOWN/no retry | PASS |
| Dialogs/popups | Dismiss/close, refs invalidated, download no solicitado rechazado | PASS |
| Real browser local controlled by contracts | 34/34 focused y regresión sin fallos productivos nuevos | PASS |

Trazabilidad de los 50 AW-INV en `invariant_matrix.json`: distingue evidencia local nueva, preservación heredada y requisitos futuros diferidos. No son 50 certificaciones READY.

## Tests y regresión

Producto congelado antes de la corrida final: `product_freeze.json`. Host Windows 11 build26200, C: Fixed/local NTFS, HOST_UNISOLATED. Python 3.14.6 / pytest9.1.1 / pypdf6.19.0; Playwright1.63.0; Node24.16.0. Runtime, engine, basetemp, private config y raw outputs fuera de Git.

| Corrida final | PASS | FAIL | ERROR | SKIP | Extra |
| --- | ---: | ---: | ---: | ---: | --- |
| AW5 focused | 34 | 0 | 0 | 0 | 21 portable + 13 Chromium real |
| Core completo por selección positiva vigente | 3245 | 1 histórico | 0 | 7 históricos | 53 subtests PASS |
| Security | 615 | 0 | 0 | 0 | Contratos vigentes completos |
| MEMORY, entorno corregido | 791 | 0 | 0 | 0 | Ninguna campaña semantic/modelo |
| Knowledge | 1015 | 0 | 0 | 0 | Ninguna recertificación histórica |
| Desktop | 68 | 0 | 0 | 0 | TypeScript exit0 |

Core/Security/MEMORY/Knowledge: 5666 PASS / 1 FAIL / 7 SKIP, 5674 parámetros normales y 53 subtests. Los 21 portables AW5 ya están dentro de Core; los 13 engine se cuentan aparte, no duplicar los 34 focused.

### Fallos conservados y clasificación

`tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available` permanece **FAIL**, Core exit1. Clasificación `PREEXISTING_CORE_HARNESS_DEBT`, `NON_BLOCKING_FOR_AW5`: mismo HOME/USERPROFILE/assertion antes y después, producto/test/runner sin modificar. No se declara Core totalmente verde ni READY.

Primera regresión MEMORY: 786 PASS / 5 FAIL, exit1, conservada. **ENVIRONMENT**: el nuevo venv omitía NumPy y los fixtures NumpySemanticIndex devolvían EMBEDDING_UNAVAILABLE. Sólo se añadió un .pth al runtime externo para reutilizar NumPy2.5.3 ya utilizado por fases previas; pytest/pypdf/Playwright conservan sus versiones. Nueva salida independiente: 791 PASS. Sin modificar MEMORY, tests ni assertions; doubles no se presentan como calidad semántica real.

Corridas de desarrollo preservadas: 22/6; 29/0; 33/0; 34/0. La final frozen fue 34/0. Todos los XML/hashes, fechas JUnit, tiempos, comandos y exit codes en `test_results.json`. End de JUnit se deriva de timestamp + suite.time, no es medición adicional de teardown externo.

Skips finales: los mismos siete nodeids de AW4 (tres symlinks no autorizados por host, dos modos POSIX incompatibles con Windows, dos monitor legacy retirado). 0 nuevos skips/xfails/exclusiones. No se tocaron sus assertions. Diferencias de collected-nodeid UUID en cuatro parámetros AW2 y uno MEMORY son generación histórica import-time; mismos sources/selectores/denominadores.

### XML finales

Raíz raw externa: `C:/Users/joseh/AppData/Local/Temp/nova-aw5-20261009T194457Z`.

| Output | SHA-256 tests.xml |
| --- | --- |
| focused-final | `a618acb2606057640a7b2e26864a373f5ec378a95c63bb0e8267bea3d4573729` |
| final-core | `a1cd5a9f3a861049eb73e5621c9ece830c445e9be67cb654004d97e154cb1d66` |
| final-security | `b1bcde38878d3d98b22ccb1190b7ac22a89aa3581b6595adad461b575c37ec01` |
| final-memory, ENVIRONMENT FAIL | `c0e897352c832d6407d6b3b17157efe8758244f9ec1061eca888869661157d3d` |
| final-memory-environment-repaired | `1f4943df274998a9e89e32731dcffed9681f945c5c3b8aac35279bdd70c75734` |
| final-knowledge | `f94f533ac18299ea45daadf96bb23b1fbc2c219f60c90244fb58cd492d21301b` |

Comandos completos y setup privado en `test_results.json`; runner inalterado: `<runtime>/python.exe -B ci/run_contracts.py --job core|security|memory|knowledge --output <directorio externo nuevo>`. Plugins/config de usuario deshabilitados; ninguna selección por resultado.

## Integridad, alcance y límites

`integrity.json`: 0 drift inesperado, 0 product drift después del freeze, arquitectura/historia intactas y 194 raw históricos AW0–AW4 verificados sin cambio. Se reconstruyeron hashes anteriores del CI y pyproject quitando sólo adiciones AW5. Inventory3979, unclassified0. Post-run CIM: 0 procesos engine/driver propios bajo la raíz AW5; no se mataron procesos del usuario.

Archivos de producto: `pyproject.toml` (extra), `playwright_adapter.py` (nuevo), `egress_broker.py` (challenge mínimo), `ci/pytest_contracts.json` (adición). Tests nuevos: `test_aw5_contracts.py`, `test_aw5_engine.py`. Evidencia nueva sólo en esta carpeta; Core/Application/Policy existentes y Desktop no cambiaron respecto del baseline.

No nuevos schemas persistidos/migraciones. No umbral de performance nuevo: deadlines/cancelación/quota/bounds probados por contratos, duración de tests no es SLA universal.

**Claims limitados**: motor real local controlado en fixtures deterministas. FixtureAdmission cambia exclusivamente el endpoint numérico del host sintético para positivos; no debilita política productiva. La prueba de loopback usa policy productiva. SW HTTPS es una respuesta sintética cumplida en harness, no certificación TLS/broker. Actor de aprobación sintético, no consentimiento humano real.

`available = UNKNOWN`, `publicOnly = UNKNOWN`. No certificación universal de bypass/protocolos/TLS coalescing/UDP, sandbox/process isolation, DLP perfecto, verdad de transacciones remotas o todos los modelos. Captura no implementa ARIA completa/iframes/vision. Cleanup puede ser UNCONFIRMED ante fallo/crash externo; no garantía física universal.

Sin takeover/login humano/upload/download aprobado/staging (AW6), frontend/bootstrap público/CI engine automático (AW7) ni E2E/certificación global (AW8). Perfiles vision/persistent NOT_CERTIFIED. No se ejecutó LLM ni se reabrió Knowledge/MEMORY READY.

**AW5 = PASS**. Detener aquí para revisión humana; AW6 no implementado.

