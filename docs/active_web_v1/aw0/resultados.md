# AW0 — Freeze y contratos

Estado final: **AW0 = PARTIAL**. Fecha: 2026-10-09.

Los entregables contractuales de §35 están implementados y verificados. No se declara cierre completo porque el gate vigente de Core conserva un fallo previo de harness; no se corrigió fuera del alcance ni se convirtió en skip. No existe fallo nuevo demostrado de AW0.

## 1. Preflight y fuente normativa

- Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`; Nova 0.12.6.
- Working tree inicial: ningún cambio tracked/staged; tres archivos proporcionados por el usuario sin tracking: arquitectura Active Web, auditoría y findings.json.
- Freeze previo a cambios: [baseline_freeze.json](baseline_freeze.json). 2181 archivos tracked; agregado raw SHA-256 `b2b7c3c361e8dffdbc778e81b48fab90faf576f86d376733ce91dd99aaa72d1e`. Los 93 pins de la auditoría coincidían.
- Arquitectura SHA-256 `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`, intacta. Se aplica la autorización del usuario para AW0; no se cambia su encabezado histórico «propuesta».
- Windows 11 build 26200; volumen C: NTFS local Fixed/Healthy; HOST_UNISOLATED.
- Python base absoluto 3.14.6; pytest 9.1.1, pypdf 6.19.0 y NumPy 2.5.3 ya disponibles. Node 24.16.0 observado; no afirmar ejecución con el pin hosted 24.19.0.
- Se conservan los cinco tags y todos los estados/históricos heredados. La diferencia documental entre «dependencias cerradas» y el estado Core global registrado por la auditoría no se resuelve reabriendo certificaciones: se preserva literalmente `NOT_DECLARED_IN_REPOSITORY; historical platform gate pending`.
- No contradicción material que impida crear los contratos AW0. El fallo del baseline CI se registra por separado.

## 2. Reutilización y cambios mínimos

| Requisito | Componente / reutilización | Evidencia |
|---|---|---|
| Freeze | HEAD, tags, agregado raw, 93 pins, tres inputs | baseline_freeze.json; integrity.json |
| Corpus AW-INV | 50 cláusulas literales de §33, congeladas antes de tests | invariant_corpus.json; test_frozen_invariants_match_normative_source |
| DTOs/enums | Nuevo local_cli/core/active_web.py; IDs/correlación y EffectState Core | 128 casos sintéticos AW0; codecs schemaVersion=1 |
| Snapshot | BrowserCapabilitySnapshot y extensión aditiva RuntimeCapabilitySnapshot.active_web | Default UNKNOWN, legacy decode, validación boolean/int, broker/metadata, roundtrip |
| CI inventory | Inventario/CollectionGuard actuales; regla ACTIVE_WEB_AW0 en job core | 3821 contratos clasificados, 26 nuevos; todos los 3795 previos intactos |
| No browser todavía | Ningún manager/BrowserPort/adapter/tool/probe/engine/dependencia/workflow nuevo | AST, tool factory intacta, agregado original reconstruido |

Se reutilizarán en sus fases correspondientes AgentSessionCoordinator, ToolRuntime/Policy/Approval/Grant, cancel/deadline, ContextPolicy, audit durable y frontends comunes. **No se integran ni se reimplementan ahora**. El puerto S5 GET pasivo no se presenta como broker browser. MEMORY/Knowledge permanecen dominios independientes.

BrowserCapabilitySnapshot reside en core/contracts.py y se reexporta desde core/active_web.py: así RuntimeCapabilitySnapshot mantiene su contrato stdlib-only sin importar otra capa ni crear un ciclo. El wire aditivo `activeWeb` usa las Observation KNOWN/UNKNOWN existentes; snapshots legacy sin ese campo recuperan UNKNOWN.

## 3. Alcance de contratos

- Refs separados bws/bwp/bwo/bwe/bwd, opacos y con factories UUID. Shape no prueba host issuance, ownership ni freshness; registry/enforcement se difieren a AW1/AW2.
- BrowserObservation y BrowserElement inmutables, sin selectors/JS/bindings del engine ni campos de cookies/passwords/storage/authority. Texto hostil sigue siendo dato; no existe conversión a instrucciones ni proyección de contexto.
- Request exige operationId/turnId/session/page/deadline. Element actions exigen observation/element refs y versiones; data actions exigen digest/classification. No ejecuta acciones.
- Taxonomías §16, outcomes §22 y vocabulary lifecycle §8.3. BrowserPageState utiliza ese vocabulario común; no define un grafo de transiciones de página. UNKNOWN/STARTED no pueden serializar ausencia de efecto. No hay retry engine ni rollback.
- Framing §11 literal preservado como constante contractual, no inyectado como system.
- Capability UNKNOWN no implica true. Un available=true sintético necesita metadata, broker y PUBLIC_ONLY conocidos; no representa un probe real ni una autorización. HOST_UNISOLATED no se confunde con BROKER_ENFORCED. No se anuncia tool browser.
- Formatos DTO schemaVersion=1; errores de DTO BrowserContractError con código, sin eco de inputs. Capabilities conservan los errores ValueError/TypeError de los contratos Core existentes.
- No cuotas runtime, persistencia, manager, stale checks, policy branches, uploads/downloads, broker, browser, fake BrowserPort, nueva sesión/loop, integración de contexto ni interfaz pública Active Web.

El corpus diferencia cobertura contractual/estática de evidencia runtime: **no son 50 invariantes browser certificados**. Todos conservan runtimeStatus NOT_IMPLEMENTED_IN_AW0 y su fase de verificación posterior.

## 4. Tests y regresiones

Salidas/runtime/fixtures externos a Git: `C:/Users/joseh/AppData/Local/Temp/nova-aw0-20261009/`. Comandos, resultados por intento, errores, skips, receipts, paths y SHA de XML/log/selección constan en [test_results.json](test_results.json).

### Baseline y clasificación

Se conserva cada intento, no se reemplaza su resultado:

| Intento | Resultado | Clasificación |
|---|---|---|
| Sandbox Core | 2734 PASS / 6 FAIL / 7 SKIP / 53 subtests PASS | 5 restricciones del entorno; mismo fallo HOME del harness |
| Sandbox Security | 613 PASS / 2 FAIL | hardlink denegado; pytest inaccesible en child |
| Sandbox Memory | 649 PASS / 142 FAIL | resolución de paths del entorno; misma selección luego 791 PASS nativa |
| Sandbox Knowledge | 995 PASS / 20 FAIL | fixtures filesystem/process/HTTP restringidos; misma selección luego 1015 PASS nativa |
| Native Security, runtime original | 614 PASS / 1 FAIL | child no encuentra pytest: PYTHONPATH privado del runner |
| Native Memory, runtime original | 791 PASS | sin cambios/assertions/reclasificación |
| Native offline venv Core | 2739 PASS / 1 FAIL / 7 SKIP / 53 subtests PASS | HARNESS_BUG / PREEXISTING: HOME vs PowerShell |
| Native offline venv Security | 615 PASS | dependencias visibles a child |
| Native offline venv Knowledge | 1015 PASS | mismos contratos completos |

La corrección **exclusivamente del entorno** fue un venv temporal sin pip ni descargas, con .pth hacia dependencias ya presentes. No se cambia runtime global ni producto/tests/runner. Los primeros errores y XML/logs quedan conservados. No hay retry por calidad/inferencia.

### AW0 y final

AW0 focused: **128 PASS / 0 FAIL / 0 ERROR / 0 SKIP**. XML original completo: `C:\Users\joseh\AppData\Local\Temp\nova-aw0-20261009\aw0-focused\tests.xml`; SHA `700cba1eed6f85912321e6082fffebf76e4846392e5531dd1cc57a004581660e`. Los mismos 128 casos vuelven a pasar dentro del job Core completo; no se suman dos veces al total HEAD.

Regresión HEAD aplicable = cuatro selecciones positivas ordinarias actuales, **no** replay K8/SCF/campañas históricas. No se añaden exclusiones ni filtros. Todos los parámetros de cada contrato seleccionado se ejecutan.

| Job final | Casos | PASS | FAIL | ERROR | SKIP | SHA-256 JUnit |
|---|---:|---:|---:|---:|---:|---|
| final-core | 2928 | 2867 | 1 | 0 | 7 | `60516eb63319804f69e8abf33d1fc78f440751a424db5fe2fc009327c6d317b4` |
| final-security | 615 | 615 | 0 | 0 | 0 | `a0094e996eb8cebd09812ff9703129599b4b805d8bc17917ba308467b0fefc7a` |
| final-memory | 791 | 791 | 0 | 0 | 0 | `1d780f0a7592b893618baaa746fa7a6dea404dbfbb3a64188f2475f5f8ec4376` |
| final-knowledge | 1015 | 1015 | 0 | 0 | 0 | `e38df914e1572e9b2037c6b458a87304cf9cbc53b3d6aae26b7d7a66d64b39a8` |

Total Python final: **5288 PASS / 1 FAIL / 0 ERROR / 7 SKIP**, más **53 subtests PASS**. Los siete IDs de skip son idénticos al baseline (symlinks sin privilege, bits POSIX y monitor legacy retirado); 0 nuevos skip/xfail. Los subtests no aumentan los casos JUnit del runner.

Desktop: siete suites ordinarias **68 PASS / 0 FAIL / 0 SKIP**, TypeScript --noEmit exit 0. No GUI, packaging, browser, cloud ni modelos reales. Python 3.10: sintaxis AST comprobada, no ejecución certificada de ese runtime ni de Linux/macOS.

### Único fallo final, no ocultado

`tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`, línea 223.

`ci.private_environment` usa carpetas distintas para HOME y USERPROFILE. BashTool es el alias compatible del shell nativo; en PowerShell `echo $HOME` lee la variable automática de PowerShell derivada de USERPROFILE, no `$env:HOME`. El assertion espera private/home y observa private/userprofile. Reproducido antes y después de AW0, con la misma selección, runtime nativo y código de shell/test/runner intactos.

Clasificación: **HARNESS_BUG / PREEXISTING**, no PRODUCT_BUG de AW0. No se cambió ese contrato, entorno privado, runner ni assertion para verde. Debe reconciliarse en autorización separada. Core final exit code 1 se preserva.

## 5. Integridad y fronteras

[integrity.json](integrity.json): 0 drift tracked inesperado; 0 cambios de arquitectura/auditoría; index vacío; tags intactos. Al sustituir sólo los SHA iniciales de core/contracts.py y ci/pytest_contracts.json, el agregado de los 2181 archivos originales vuelve exactamente al freeze previo. Se demuestra conservación byte-a-byte del resto, incluida toda evidencia histórica.

Las clasificaciones, reglas, configuración y selectors CI anteriores se compararon contra HEAD sin pérdidas; sólo se añade la regla/26 contratos AW0. El cambio aleatorio de un parameter ID Memory es el UUID generado en collection por un fixture ya existente, no cambio de selección.

PASSIVE_WEB/tools/Policy/Grant/Memory/Knowledge/Desktop/proveedores/adapters permanecen intactos. Snapshot es evidencia, no authority. No se afirma process isolation ni broker enforcement implementado. Ninguna page observation se publica al modelo en AW0.

## 6. Gate literal §35, criterio por criterio

| Criterio AW0 | Estado | Evidencia |
|---|---|---|
| Freeze de baseline | PASS | baseline_freeze.json + agregado/93 pins |
| Corpus de invariantes | PASS | 50 cláusulas y arquitectura SHA, sin claims runtime |
| DTOs/enums | PASS | schema V1, 128 casos focused + Core |
| Capability snapshot | PASS | integración compatible UNKNOWN, codecs y validación |
| CI contract inventory | PASS | 3821 clasificados, 26 aditivos, 0 previos cambiados |
| «ninguna implementación browser todavía; contratos coherentes» | PASS contractual | AST/factory/integridad/tests |
| Regresión heredada íntegramente verde para cierre de tarea | PARTIAL | Core conserva el fallo de harness anterior; demás jobs verdes, 0 fallos nuevos |

**AW0 = PARTIAL**, conservador: entregables contractuales completos, pendiente reconciliación separada del fallo previo del gate Core. No se declara READY ni certificación Active Web real, ni se reabre READY heredado.

## 7. Archivos y límites

Modificados: local_cli/core/contracts.py; ci/pytest_contracts.json.

Creados: local_cli/core/active_web.py; tests/active_web_v1/__init__.py; tests/active_web_v1/test_aw0_contracts.py; docs/active_web_v1/aw0/{baseline_freeze.json,invariant_corpus.json,ci_contract_inventory.json,test_results.json,integrity.json,manifest.json,resultados.md}.

Los tres documentos de entrada del usuario se conservan sin modificar. No dependencias productivas nuevas, workflows, DB, cache ni outputs runtime dentro de Git.

Limitaciones: engine/broker/lifecycle/refs freshness/approvals/observation admission/transfers/frontends/real browser y 50 invariantes runtime pendientes de sus fases; no son deuda de implementación exigida por AW0. No se resolvieron decisiones futuras ni se introdujo BrowserPort anticipado. No cambios normativos.

La siguiente fase de la arquitectura es AW1, **no implementada**. Detención para revisión humana y decisión sobre la reconciliación del harness existente. Sin commit, push, tag ni release.

