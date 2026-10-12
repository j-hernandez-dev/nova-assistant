# AW2 — Observation y refs

**AW2 = PASS** — cierre de fase contractual; no Active Web READY global.

## Baseline y alcance

Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`. Working tree previo sucio: 2 cambios tracked heredados y 24 archivos untracked de audit/AW0/AW1. Se conserva íntegro; staging vacío. [Freeze inicial](baseline_freeze.json).

Arquitectura normativa: `NOVA_ACTIVE_WEB_ARQUITECTURA_V1.md`, SHA-256 `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`. Se aplica literalmente §35 AW2, con §§7.3–7.4, 10 (sólo seam de epoch), 11–14 y 19. Contexto: auditoría previa y findings; no prevalecen sobre arquitectura. No contradicción material ni OPEN DECISION bloqueante encontrada. Prerrequisito AW1 PASS conservado, incluyendo su evidencia de deuda Core; AW0 original PARTIAL y su cierre aditivo PASS permanecen distintos e intactos.

Se reutilizan DTOs/refs AW0, ownership/leases/cancel/cleanup AW1, CancellationController, SecretRedactor y Core ContextManager/TokenCounter/ContextPolicy. No se modifica Core budgeting, Security Policy/schema/grants, Memory, Knowledge, Desktop, dependencias o workflows.

## Implementación y trazabilidad

| Requisito AW2 | Componente/evidencia | Resultado |
|---|---|---|
| BrowserObservation | CapturedPage/Element y BrowserObservationService; DTO público AW0 schema 1 intacto | PASS |
| Element registry | Ref Nova → binding privado con session/page/context/nav/observation/version/origin/fingerprint/capabilities | PASS |
| Freshness | Estado atómico bajo lifecycle lock; captura pre/post; supersession e invalidación de página/contexto | PASS |
| Stale rejection | STALE_TARGET por mismatch; proof fresco read-only; sin heurística/rebind/retry | PASS |
| Context projection/budget | PreparedContext final de Core; framing fijo, rol tool, filas completas, caps y current user preservados | PASS |
| **“Cierre: modelo nunca usa selectors libres.”** | Schema rechaza CSS/XPath/JS/node IDs/coordenadas/bindings; refs inventadas rechazadas antes del adapter | **PASS** |

Cada requisito → test concreto está en [manifest](manifest.json) y los 50 AW-INV se conservan en [matriz](invariant_matrix.json). Las filas NOT_IMPLEMENTED_IN_AW2 no se presentan como PASS runtime de fases posteriores.

La captura produce versiones monotónicas y refs nuevas; mantiene sólo el último registry por página. Los targets quedan ligados al contexto del host y no son grants. `validated_target` comprueba proof/origin/fingerprint/capability, conserva lease/lock y entrega el binding **sólo host-side**, dentro de un scope; no ejecuta acciones. Se invalidan conservadoramente refs antes de cualquier potencial uso de elemento; un nuevo observe es necesario. Leases potencialmente effectful/navigation invalidan antes del trabajo; los demás cambios usan el seam explícito del host. No se implementan clicks/input/submit/navegación/history/popup/takeover, sólo sus contratos de invalidación.

La proyección prioriza binding/estado de página → elementos completos relevantes → metadata secundaria → texto/dialogs. Cada candidato se admite usando el contexto **real completo** de Core. Si Core clippea una fila, se omite entera; si ni el framing/estado mínimo cabe, error typed. El resultado es el PreparedContext final, no una fila destinada a clipping posterior con otro presupuesto. Se prueban ventanas efectivas 4K/8K/16K/32K/64K, tool continuity, shared MEMORY/RAG y tokenizer fallback. Ningún cap aumenta y current user no se sacrifica.

La entrada del adapter contiene sólo resumen visible y campos estructurados: no fuente DOM, cookies, auth headers, storage ni valores de input. Se omiten hidden/password/OTP/recovery/card/CVV y elementos sensibles; se aplica redaction de valores conocidos antes de bounds. URLs publicadas sin userinfo/fragment y queries sensibles redactadas; internas se omiten y no tienen targets. **Sanitizar no autoriza red ni reemplaza el broker AW4. SecretRedactor no es DLP universal.**

## Tests y regresión

Runtime explícito Python 3.14.6 / pytest 9.1.1, venv offline reutilizado de AW0. Private config/plugin autoload deshabilitados. Todos los outputs/runtime están fuera de Git en:

`C:/Users/joseh/AppData/Local/Temp/nova-aw2-20261009T173150Z`

[Registro completo](test_results.json): comandos exactos, XML/hash, timestamps/duración JUnit, exit codes, denominadores y skips. [Freeze del producto antes de regresión](product_freeze.json).

| Gate final | PASS | FAIL | ERROR | SKIP |
|---|---:|---:|---:|---:|
| Focal AW0/AW1/AW2 + Core contexto | 320 | 0 | 0 | 0 |
| AW2 dentro de focal y Core (no sumar doble) | 91 | 0 | 0 | 0 |
| Core actual aplicable | 3017 | **1 heredado** | 0 | 7 heredados |
| Security | 615 | 0 | 0 | 0 |
| Memory | 791 | 0 | 0 | 0 |
| Knowledge | 1015 | 0 | 0 | 0 |
| Desktop | 68 | 0 | 0 | 0 |

Core además 53 subtests PASS (contados aparte). Total Python final de las cuatro selecciones actuales: **5438 PASS / 1 FAIL / 0 ERROR / 7 SKIP**, 5446 parameter instances + 53 subtests. Focal no se suma de nuevo. TypeScript `tsc --noEmit` exit 0; warnings Node Experiment/ModuleTypeless preexistentes, sin cambios cosméticos.

Se ejecutaron los cuatro jobs actuales `ci/run_contracts.py --job core|security|memory|knowledge`, con output externo fresco. No reruns de campañas históricas/modelos, no categorías host-real especiales ni exclusiones nuevas. Inventario positivo: 3898 contratos base; 40 AW2 nuevos portables, todas sus 91 parametrizaciones ejecutadas. Los 3858 anteriores, reglas y selecciones se recuperan byte-a-byte al retirar sólo el delta AW2, SHA `f31fec5878d51d4f6433ae15af85c345d4ff8d9621055bfcf83df6c5306fe408`. No runner/workflow modificado.

### Deuda Core explícita, no ocultada

`tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`

**PREEXISTING_CORE_HARNESS_DEBT / NON_BLOCKING_FOR_AW2**. Baseline antes de AW2: 229 PASS / 1 FAIL; final Core reproduce exactamente el fallo HOME/USERPROFILE ya documentado en AW0/AW1. El runner configura HOME y USERPROFILE privados distintos; PowerShell $HOME corresponde a USERPROFILE. Producto/test/runner/assertion relacionados intactos. **Core job exit 1, no green/PASS ficticio del test.**

`newFailures=0`, `newSkips=0`, `newXfails=0`. Los 7 IDs de skips y sus motivos coinciden con AW1, salvo el path del output privado: 3 symlink sin privilegio, 2 POSIX mode, 2 legacy monitor retirado. No skip/xfail/filtro/retry nuevo. El gate literal AW2 exige refs/selector contracts coherentes y ausencia de regresiones introducidas; no exige resolver deuda ajena. Ese gate está demostrado sin reinterpretar certificaciones previas.

### Historia del desarrollo AW2

Corridas iniciales conservadas, no sustituidas:
- inicial: 265 PASS / 8 FAIL; cinco falsos positivos de fixture binding `"0"`, dos defectos del proyector y una lectura incorrecta de capability en el test nuevo;
- segunda: 272 PASS / 1 FAIL, assertion de suffix adversarial no admitido por 4K;
- focal posterior: 315 PASS; focal definitivo extendido: 320 PASS.

Clasificación/corrección completa en test_results.json. No assertions históricas, thresholds, skips ni xfails alterados. El test de injection usa 8K para que la cadena adversarial realmente llegue a la proyección, conservando su assertion; todos los contratos 4K/atomicidad/clipping siguen presentes. Dos verificadores read-only de evidencia interrumpidos por quoting/keys fueron corregidos sin tocar tests o raws.

## Integridad y límites

[Integridad](integrity.json): tracked bytes preservados salvo inventario aditivo; única fuente heredada cambiada es el manager AW1 para los seams mínimos AW2. Arquitectura/audit/findings, evidencia AW0/AW1, fixtures/tests previos, tags y certificaciones heredadas intactos. Cero drift del freeze de producto después de regresión; index vacío.

Evidencia **contractual con fake**, no motor/modelo/network/LLM real. No browser disponible ni herramientas nuevas: capability UNKNOWN; ACTIVE_WEB_VISION_PROFILE=NOT_CERTIFIED. Real-engine preemption, render visibility, fingerprint proof y validación+dispatch atómico deberán demostrarse con el adapter real en fases posteriores. No se afirma sandbox/process isolation: HOST_UNISOLATED permanece. Memory/Document semantic profiles no se recertifican.

No hay gate de latencia/quality de motor real en AW2; duración focal final 1.92 s incluye pytest y fake. Deadlines/cancel se validan con clock/port deterministas, no como performance real de Chromium. No nuevos modelos, downloads, probes, servicios cloud o configuración global.

## Entrega y detención

Archivos nuevos: Core active_web_observation.py, Application browser_observation.py, tests test_aw2_observation.py y evidencia aw2. Cambios mínimos: Application active_web.py y el inventario CI. Sin schema/persistencia/migración nuevos fuera de los DTOs públicos AW0 ya versionados; contratos internos frozen, errores typed.

**AW2 = PASS**. Sin commit/push/tag/release/READY, sin AW3. Se detiene para revisión humana. AW3 sólo como referencia: Policy/effects/approvals, no implementados.

