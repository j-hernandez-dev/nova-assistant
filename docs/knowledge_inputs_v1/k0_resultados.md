# Knowledge Inputs V1 — K0: baseline y contratos

**Estado de cierre: K0 PASS.** Todos los requisitos obligatorios de §55 están demostrados.
**Fecha:** 2026-10-07. **Alcance exclusivo:** §55 K0; no K1 ni READY Knowledge.

## 1. Baseline y precedencia

Branch `main`, HEAD/base `717a24218dea7fb60d8b630896d653e39091bc7b`.
El árbol inicial tenía únicamente dos archivos untracked preexistentes:

- `docs/architecture/AUDITORIA_KNOWLEDGE_INPUTS_NOVA_V1.md`;
- `docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md`.

Se conservaron íntegros. El usuario aprobó explícitamente la arquitectura como
baseline normativo; su encabezado editorial anterior «propuesta normativa» no
se editó. Se aplica §3: Core gobierna lifecycle/context, SECURITY gobierna
authority/tools/acquisition, MEMORY conserva su dominio independiente, y
Knowledge añade únicamente su dominio documental. La auditoría es evidencia,
no precedencia sobre la arquitectura aprobada. No se detectó contradicción
normativa que bloquee K0.

[Freeze previo](k0_freeze.json): HEAD, working tree, tags, 15 hashes protegidos,
READY anteriores y baseline ejecutado antes de introducir contratos.

| Tag preservado | Commit objetivo |
|---|---|
| `nova-core-v1-stable` | `158b60effa484cd34a58b991f3ee4ca3f808d924` |
| `nova-security-v1.2-ready` | `26dc87786d8ad1c1d879255a068c7fb50a25e6f2` |
| `nova-memory-v1-ready` | `9911ad4ca0fc13edfef49e84441a759d35cbefda` |
| `nova-memory-v1.1-ready` | `3678d5b597a888b743e90d26efda6219943d58df` |

Los cuatro tags son ancestros del HEAD; se preservan también sus objetos
annotated, registrados en el freeze. No se creó/movió ningún tag.
Runtime: paquete `0.12.6`, Python 3.14.6, pytest 9.1.1, SQLite 3.50.4,
Windows 11 build 26200, volumen C: NTFS. Node v24.19.0 para contratos Desktop.
Runtime alternativo sólo para contratos K0: Python 3.12.14 ya instalado.
No se instaló ninguna dependencia ni modelo.

## 2. Preflight exclusivo de K0

| Pieza existente | Estado observado / reutilización | Cobertura existente | Cambio K0 |
|---|---|---|---|
| `core/contracts.py`, `core/runtime.py`, `application/session.py`, `application/legacy_runtime.py`, `agent.py` | Lifecycle Core/AgentRuntimePort y adapter/loop productivos; no segundo loop | Core fases 9/13/14, HEAD | Ninguno |
| `core/security.py`, `application/tool_runtime.py` | Authority, grants y ruta común de tools productivos; sintaxis URL reutilizable | SECURITY S1–S8 contracts, HEAD | Sólo reutilización de sintaxis Core en locator; no nueva autorización |
| `application/network.py`, `infrastructure/http_fetch.py`, `tools/web_fetch_tool.py` | Fetch PUBLIC_ONLY productivo, pero no Source/Revision/citations V1 | S5 contracts/runtime; HEAD | Ninguno; integración Knowledge es posterior |
| `infrastructure/windows_filesystem.py`, `filesystem_tools.py` | S3 mediado Windows/NTFS; no heredar claims en una ruta nueva | S3 contracts/runtime; READY SECURITY preservado | Ninguno; no acquisition en K0 |
| `core/context.py` | Budgeting numérico y shared retrieval cap MEMORY/RAG productivos | Context 64K, Core fase 9, MEMORY M4 | Ninguno |
| `application/rag.py`, `infrastructure/rag.py`, `rag.py` | RAG legacy integrado detrás de puerto; no equivale a Knowledge V1 | Core fase 10, MEMORY M4/M7 | Ninguno; aislamiento/rebuild legacy corresponde a K1/K4 |
| `core/memory.py`, `application/memory_recall.py` | MemoryStore/MemoryCapsule independientes y certificados Core | Suite MEMORY completa | Ninguno productivo; sólo reparar harness CI |
| `cli.py`, `server.py`, `desktop/electron/application_client.ts` | Backend Application común; no attachments/import documental V1 terminado | Core frontends/snapshots; 40 contratos Node | Ninguno |
| Source/Revision/Locator y capability snapshot documental | Faltaban contratos versionados del dominio aprobado | No cobertura K0 previa | Nuevo módulo Core y tests sintéticos |
| Parsers, store Knowledge, citations turn-local | No implementación V1 terminada; stubs/legacy no constituyen soporte | Auditoría previa | No implementar en K0 |

Antes de editar se previeron un módulo Core autónomo, fixtures/harness/tests
K0 y evidencia; el requisito de reconciliación CI autorizaba reparaciones
puntuales de tests MEMORY, no cambios productivos. No se modificaron workflows:
el gate Core existente ya descubre `tests/knowledge_inputs_v1` al ejecutar
`pytest tests`; los modos MEMORY `m0`/`m4` conservan su selección.

## 3. Contratos implementados y trazabilidad

`local_cli/core/knowledge.py` es stdlib/Core exclusivamente. No SQLite,
Ollama, Electron, paths resueltos, filesystem I/O, red, store ni parser.

| Requisito | Implementación | Evidencia |
|---|---|---|
| §6.1–2, KI-OD-01 | `Source`, `SourceRevision`, UUID Nova-generated, digest SHA-256, snapshots frozen | Roundtrip de 18 fixtures; UUIDs no derivados del origen; cambio de contenido con nueva identidad |
| §6.6 | `SourceLocator`: líneas, página/rango, párrafo/sección, JSON Pointer/rango, URL/bloque, URL/rank | 6 clases; coordenadas inválidas rechazadas, copia immutable, JSON Pointer root/escapes |
| §7–8, KI-OD-03/04 | 7 kinds; scopes SESSION/WORKSPACE con bindings host opacos; sin GLOBAL ni subject MEMORY | Scope explícito; SESSION requiere sessionId, WORKSPACE no admite sessionId |
| §16/19 | Estados de extracción y lifecycle representables, separados | Enums roundtrip; Source READY/PARTIAL/SUPERSEDED exige currentRevisionId |
| §36, KI-OD-16/19 | Trust descriptivo, datos sin métodos/fields de autoridad o auto-memory | Texto hostil sigue siendo dato; DTO control-plane desconocido rechazado |
| §38, KI-OD-17 | `SourceRemotePolicy.remoteDocumentForwarding=false` por defecto | Codec/validación booleana; no opt-in ejecutable en K0 |
| §44 | 21 códigos normativos + 2 errores tipados de schema/representación | Código serializable; diagnóstico no incluye contenido/path/secret del caller |
| §45, §55 | 10 nombres y 5 estados; `KnowledgeCapabilitySnapshot` versionado | Snapshot K0 todo UNAVAILABLE; no cableado Application/UI ni cambio del DTO Core existente |
| Contratos versionados | `schemaVersion=1`, camelCase, roundtrip JSON estricto | Versiones desconocidas, bool como versión, campos desconocidos y representaciones inválidas rechazados |

Los dos códigos adicionales son `KNOWLEDGE_INVALID_CONTRACT` y
`KNOWLEDGE_SCHEMA_UNSUPPORTED`. Son validación representacional, no errores
de un parser/store inexistente. El mensaje genérico evita exponer datos.
No se introducen migrations ni compatibilidad con vectores legacy en K0.

## 4. Fixtures y freeze

Corpus inicial `ki-k0-initial-synthetic-v1`, 18 casos exclusivamente sintéticos:
TXT/MD/code/JSON/CSV/HTML/PDF textual/DOCX, ES/EN, SESSION/WORKSPACE,
encoding explícito cp1252, vacío, JSON corrupto, MIME/extensión discordante,
instruction-like, bytes duplicados con provenance distinta, actualización y
search snippet distinto de fetched page. IDs y expectativas se fijaron por
formatos/fronteras normativos, no por resultados de un scorer o modelo.

[Freeze del corpus](k0_corpus_freeze.json) conserva SHA y byteLength de cada
payload. El corpus SHA LF es
`b5edffa72833d49df358ce8da143ef123da6df818dab4fb3647241ceb98efac2`.
No se alteró después de observar resultados. No es el corpus de calidad K8.

PDF tiene header/xref/trailer reales; DOCX es OOXML ZIP real. Se verifica la
estructura del fixture, no calidad de extracción productiva. Los fixtures usan
UUID5 deterministas sólo para tests; el generador Core usa UUID4.

La recompresión DOCX reveló una diferencia entre zlib-ng y zlib clásico:
812 bytes vs 807, con hashes distintos. Se preservó el payload original de
812 bytes y su SHA
`af4dccdad0bbf593b1857367ac60316157ff574f750de19de44044014ba9c4b3`
en `k0_docx_payload_v1.json`. Leer esos bytes evita recomprimir. **No cambió el
corpus ni ningún payload esperado**; ambos runtimes pasan los mismos contratos.
No se afirma certificación nativa Ubuntu/macOS por esta comprobación.

## 5. Fronteras e invariantes aplicables

- KI-INV-001/002/003: representación explícita y frozen, nueva revisión para
  cambio de contenido. Publicación/lineage/immutabilidad persistente es K1,
  no una garantía ya implementada por una dataclass.
- KI-INV-004/005/006/007: dominio distinto de MEMORY, datos sin autoridad y sin
  ruta que emita instrucciones/grants/approval o escriba recuerdos. Probado
  estructuralmente y por ausencia de integración; no nueva campaña LLM de
  resistencia a injection.
- KI-INV-014/015/036/037: no nuevos claims de parsers, OCR, semantic ni READY
  Knowledge; statuses no equivalen a capabilities verificadas.
- KI-INV-009/010: no acquisition nueva ni ruta alternativa a ToolRuntime;
  SourceLocator reutiliza únicamente sintaxis Core URL, **no** autorización
  DNS/network ni enforcement S3.
- KI-INV-026/027/039: ContextManager, current user priority, shared cap y backend
  Application no se modifican; regresión de sus contratos vigente.
- KI-INV-031/032: forwarding documental representado separadamente, off default;
  no web search implementado ni consentimiento inferido de un documento.
- KI-INV-038: ninguna capacidad Active Web, browser, click, formulario o sesión.

Los demás invariantes que requieren store/acquisition/extraction/retrieval/
citations/delegación quedan en sus fases correspondientes. **No se presenta
K0 como prueba integral de los 40 invariantes de Knowledge Inputs V1.**

KI-OD aplicables: 01, 02 (separación, sin adelantarse a Block/Chunk), 03, 04
(representación), 06/07 (errores/status, no extraction), 16, 17, 18/19
(preservación), 21 (no nueva lógica UI), 25 (no reinterpretar legacy), 26
(corpus inicial sin quality claim), 27 y 28. Las decisiones restantes están
resueltas en la arquitectura pero su implementación pertenece a K1–K8.

## 6. Tests y evidencia

Todos los stores/profiles/runtime outputs de pruebas se crean en directorios
nuevos bajo TEMP, fuera de Git. No se usa conversación ni estado privado real.
Los logs publicados en `k0_evidence` son copias textuales con LF y newline
terminal normalizados; los hashes del original externo se registran aparte.

| Corrida | Resultado | Tipo / alcance |
|---|---|---|
| Baseline HEAD antes de cambios | 4138 PASS, 0 FAIL, 11 skips previos, 53 subtests PASS; 310.64 s | Selección CI vigente, contratos/integration/native smokes existentes |
| K0 inicial | 165 PASS; 0.30 s | Unit/contract sintético; sin modelos |
| K0 con freeze | 166 PASS; 0.40 s | Añade comprobación explícita de hashes congelados |
| K0 final Python 3.14.6 | 167 PASS, 0 FAIL/skip; 0.31 s | Payload congelado, contratos y fixture-no-recompression |
| K0 final Python 3.12.14 | 167 PASS, 0 FAIL/skip; 0.40 s | Mismos datos; otro zlib, sin instalación |
| Harness CI específico final | 31 PASS, 0 FAIL/skip; 1.17 s | Doubles + worker real; no calidad embeddings |
| Fronteras Core/context/RAG | 131 PASS, 0 FAIL/skip; 3.86 s | Core architecture, 64K, context, RAG integration con doubles |
| MEMORY completa | 790 PASS, 0 FAIL/skip; 57.73 s | Contratos/persistencia/recovery/CPU fixtures; sin LLM/embeddings reales |
| Primera HEAD posterior | 4309 PASS, 1 FAIL, 11 skips previos, 53 subtests PASS; 275.34 s | Fallo de guard histórico preservado y reparado explícitamente |
| HEAD tras reconciliar guard | 4312 PASS, 0 FAIL, 11 skips previos, 53 subtests PASS; 285.04 s | Antes de eliminar recompresión del fixture; no producto cambiado después |
| HEAD final congelada | 4313 PASS, 0 FAIL, 11 skips previos, 53 subtests PASS; 280.94 s | Estado exacto final del harness y contratos |
| Desktop contrato Node | 40 PASS, 0 FAIL/skip; 713.3515 ms | TS real con transform-types, dialog/IPC doubles; no Electron GUI |

Los 53 subtests se reportan aparte de los tests PASS de pytest. No se suman
entre corridas como si fueran cobertura única.

No se ejecutaron nuevos modelos, HTTP externo, host-real S3 opt-in, Electron
gráfico, embeddings reales, K8 quality ni certificación Knowledge. No son
requisitos nuevos de K0 y el producto existente no se modifica. La selección
HEAD conserva las exclusiones históricas/host opt-in ya clasificadas por CI;
no se añadieron exclusiones, skips ni xfail.

## 7. Reconciliación y fallos preservados

[Diagnóstico separado](k0_ci_reconciliation.json):

1. **HARNESS_BUG, LF/CRLF:** el guard de campaña Qwen exigía sólo bytes CRLF
   del checkout histórico. Se reprodujo con el blob LF real del HEAD.
   Ahora admite sólo esos dos hashes fijados, no cualquier JSON equivalente;
   alteraciones de contenido, whitespace/key y perfil siguen denegadas.
2. **HARNESS_BUG, medición CI:** la aserción macOS de 600 ms falló a
   626.87175 ms. Esa observación permanece fallida; no prueba por sí sola todas
   las etapas ni el reparto del retraso. El test contractual usa clock/Future
   controlados y conserva worker real, timeout, BUSY, recuperación, snapshot
   immutable y cero late search. soft350/hard600/reserve50 no se modifican.
   No se convierte esto en un benchmark semántico real aprobado.
3. **HARNESS_BUG, invocación Node:** 38 PASS/2 FAIL por strip-only mode;
   comando transform-types ya publicado en MEMORY READY: mismos 40 PASS,
   sin cambios a producto/tests Desktop. Se preservan ambos resultados.
4. **HARNESS_BUG introducido en la reconciliación:** el guard histórico también
   validaba bytes del test corregido. Se preservan sus nueve pins; se permiten
   sólo el original y el SHA exacto de la reparación K0 de ese archivo de test.
   Todos los archivos productivos siguen sujetos a los checks históricos;
   cambios adicionales y sustitución del pin antiguo fallan.
5. **HARNESS_BUG, ZIP/compresor:** diferencia de payload entre dos runtimes;
   se conserva el payload original congelado, sin modificar el corpus/gold.

No se identificó PRODUCT_BUG en el runtime existente. Una nueva corrida
GitHub Actions es **NOT_RUN**; Ubuntu/macOS nativos son **NO VERIFICADO** en
esta sesión, no PASS remoto ni nueva certificación.

## 8. Gate literal §55

| Criterio | Estado | Evidencia |
|---|---|---|
| Congelar HEAD y tags | PASS | `k0_freeze.json`, pins y ancestry verificados |
| Reconciliar CI relevante | PASS local | Reparaciones acotadas, 31 tests, MEMORY 790; workflow sin cambios; remoto NOT_RUN |
| Fijar fixtures/corpus iniciales | PASS | 18 casos, corpus/payload SHA; bytes DOCX preservados, dos runtimes |
| Source/Revision/Locator/errors/capabilities | PASS | Módulo Core, schema v1, 167 contratos |
| No anunciar capabilities todavía | PASS | No integración/registro/DTO público nuevo; snapshot de contrato UNAVAILABLE |
| **Cierre: Core/Security/Memory verdes y contratos versionados** | PASS | HEAD final 4313 +53 subtests PASS, 0 FAIL; MEMORY 790, Desktop 40, K0 167 y schemas v1 |

## 9. Archivos y límites del cambio

Creados:

- `local_cli/core/knowledge.py`;
- `tests/knowledge_inputs_v1/__init__.py`, `k0_corpus_v1.json`,
  `k0_docx_payload_v1.json`, `k0_fixtures.py`, `run_k0.py`,
  `test_k0_contracts.py`, `test_k0_corpus.py`;
- `docs/knowledge_inputs_v1/k0_freeze.json`, `k0_corpus_freeze.json`,
  `k0_ci_reconciliation.json`, `k0_resultados.md`, `k0_manifest.json` y
  `k0_evidence/*` (logs/metadata de esta fase).

Modificados únicamente para CI/harness:

- `tests/memory_v1/run_m8_qwen4_chat7b.py`;
- `tests/memory_v1/test_m8_qwen4_chat7b.py`;
- `tests/memory_v1/test_m8_metadata_admission.py`;
- `tests/memory_v1/test_m8_ps_operational.py`.

No se modifica runtime existente, arquitectura, evidencia anterior,
config global, GPU, workflows, dependencias, schemas públicos actuales,
thresholds MEMORY/Knowledge, corpus histórico ni scorer.

## 10. Reproducción y deuda

Con Python/pytest instalados, cada OUTPUT debe ser nuevo y fuera del checkout:

```powershell
python -B -m tests.knowledge_inputs_v1.run_k0 --mode contracts --output <OUTPUT_K0>
python -B -m tests.knowledge_inputs_v1.run_k0 --mode ci-harness --output <OUTPUT_CI>
python -B -m tests.knowledge_inputs_v1.run_k0 --mode boundaries --output <OUTPUT_BOUNDARIES>
python -B -m tests.memory_v1.run_regression --mode m0 --output <OUTPUT_MEMORY>
python -B -m tests.memory_v1.run_regression --mode head --output <OUTPUT_HEAD>
node --experimental-transform-types --test desktop/tests/application_client.test.cjs desktop/tests/approval_host.test.cjs desktop/tests/security_audit.test.cjs desktop/tests/memory_control.test.cjs desktop/tests/memory_maintenance.test.cjs
```

Las invocaciones ejecutadas usan los runtimes locales declarados arriba y,
cuando aplica, `--extra-test-site` de dependencias de tests ya existentes.
El manifest registra comandos, outputs, denominadores y hashes.

Deuda fuera de K0: KnowledgeStore/migrations/publicación/recovery/containment/
delete (K1), acquisition/attachments (K2), parsers reales (K3), documental
retrieval/semantic spaces/legacy rebuild (K4), capsule/citations/context (K5),
passive web (K6), interfaces/delegación/hardening (K7), calidad/E2E/READY (K8).
Todas esas capabilities siguen sin anunciarse como implementadas por K0.

**OPEN DECISIONS bloqueantes K0:** ninguna. KI-OD-01…28 ya están resueltas;
no se reabren ni se toman decisiones de producto adicionales. La siguiente
fase lógica es **K1**, únicamente como referencia; **no implementada**.

`SEMANTIC_PROFILE` MEMORY permanece **NOT_CERTIFIED**. No sandbox ni process
isolation; modelo publicado **HOST_UNISOLATED**. No commit, push ni tag.
