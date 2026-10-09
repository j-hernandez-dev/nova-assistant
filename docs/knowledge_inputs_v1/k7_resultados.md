# K7 — Interfaces, subagents y hardening

## Resultado y baseline

**K7 PASS** — §62 de `NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md`.

Perfil: **Windows 11 + NTFS local + HOST_UNISOLATED**. No sandbox/process isolation. `DOCUMENT_SEMANTIC_PROFILE = NOT_CERTIFIED` y MEMORY `SEMANTIC_PROFILE = NOT_CERTIFIED` permanecen intactos. No K8 ni READY.

- Branch `main`; HEAD/base `717a24218dea7fb60d8b630896d653e39091bc7b`.
- Working tree inicial: **182 entradas dirty/untracked**, **1798 archivos versionables**; conservado salvo los cambios K7 expresos. Inventario completo/tags en manifest.
- K6 PASS y sus artefactos/hash verificados antes de editar. Arquitectura SHA-256: `417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432`.
- Runtime: CPython 3.14.6 AMD64 / pytest 9.1.1; Node v24.16.0; C: NTFS Fixed local.
- Baseline: **634 Knowledge PASS**, **131 Core/context/RAG PASS**, **50 Desktop contracts PASS** (Node observado antes de editar).
- Core/Security/Memory mantienen precedencia §3 y tags intactos. No modificación normativa ni contradicción bloqueante.

## Inventario y alcance

Ya existían: store/scopes/quotas/recovery K1, host controls/picker/CLI/JSONL K2, parsers K3 + PDF repair, chunk/exact/FTS K4, cápsula/citas/shared cap K5, passive web/URL snapshots K6. Las interfaces parciales no tenían detail/consent/export/refresh completos y el child no tenía cápsula documental.

Se reutilizan esas rutas; no se crea un parser/store/AgentLoop principal nuevo. Legacy notes/vectors/RAG y MEMORY siguen independientes. Source origin/metadata nunca abre un path automáticamente. Funcionalidad nueva limitada a §62 y dependencias mínimas demostradas en hardening.

## Implementación

### DTOs, store e interfaces

- SourceSummary/SourceDetail **schema 1** y puerto de inspección separado/aditivo: bytes/chunks/error, source identity/scope/state/remote policy, revisiones/metadatos. Hasta **20 revisiones** o un revisionId exacto para citas históricas.
- Detail funciona para metadata histórica/deleted, pero no reabre blobs ni publica fingerprint/raw body. Revision solicitada debe pertenecer al source/scope. No migración SQLite ni cambio de schema.
- Source list/status/detail por Application común; CLI/JSONL comparten actor verificado, revisión/idempotency, Operations y audit.
- Host commands nuevos: source_detail (revisionId opcional), source_refresh (path nuevamente seleccionado), source_export (destino seleccionado), source_remote (bool explícito). No nuevos argumentos al tool agent ni nueva authority.
- CLI /source ofrece detail/status/url/refresh/refresh-url/export/remote on|off junto a controles anteriores.
- Desktop mínimo: DTOs/status/capacity, detalle de source/revisión y cita, refresh/export por picker/save dialog de main, snapshots URL explícitos WORKSPACE, consentimiento remoto nativo. Renderer sólo presenta DTOs/despacha acciones; no DB/parser/scanner ni paths directos de ingestion.
- Labels y locators son datos escapados por React; una referencia estructural no se presenta como verdad/entailment.

### Privacy y export

- remoteDocumentForwarding **off por default**; sólo un host verificado puede cambiar la SourceRemotePolicy. Persistencia scoped, no modificación de config global/grants/MEMORY/search consent.
- Desktop requiere confirmación nativa explícita al permitir; argumentos congelados y session/workspace/revision revalidados después del diálogo. Revoke no necesita nueva confirmación. Ya transmitido no se promete recuperar.
- Permiso se revalida entre Generations remotas, con shrink-only: revocación retira evidencia/citas; sin query/refill adicional.
- Export copia bytes administrados verificados a un destino nuevo seleccionado por host: exclusividad, unidades 256KiB y flush/fsync. No overwrite ni target dentro del root administrado. Falla tras crear/escribir → OUTCOME_UNKNOWN/archivo parcial posible, no rollback ficticio ni borrado automático. No claim S3/OS confinement.

### Delegación

- DelegatedKnowledgeCapsule **schema 1** contiene parent Turn, refs/revisions ya admitidos y presupuesto; no contiene MemoryStore/KnowledgeStore/retriever/grants.
- Application puede seleccionar knowledgeCitationIds en StartSubAgent; desconocidos/duplicados no amplían autoridad. Tool agent mantiene su schema público.
- Child recibe callback acotado a **≤10 refs parent-admitted**, no catálogo/blob/global query. Revalida eligibility/scope/revision/policy y reduce solamente la selección admitida; nunca rellena con otro recuerdo/documento.
- Provider/destino desconocido o remoto exige consentimiento documental separado. Nuevas adquisiciones siguen ToolRuntime y ceiling/grant heredado existente; no aislamiento del shell.
- MEMORY y Knowledge usan el mismo WorkingMessages/ContextManager/shared cap. Current task permanece prioritario en 4K/8K/16K/32K/64K. En child real de 4K con MEMORY una cápsula documental puede ser cero: [K1] scripted sin fuente se marca **inválida**, no recall PASS.
- SubAgent/coordinator reales verificados con provider **scripted**; no son calidad de un LLM real. Citas child estructurales conservan provenance; callbacks se limpian al terminal.

### Quotas y observabilidad

Defaults **sin cambios**: SESSION 256MiB, WORKSPACE 2GiB, 2000 sources / 100000 chunks (50MiB/source y límites K3/K4 intactos).

Contabilidad de bytes: **bodies adquiridos retenidos + staging pendiente**, como K1; excluye index/metadata/DB/WAL. Es operacional, no cuota OS ni target de footprint físico. Status lo declara explícitamente.

- Capacidad/refusal observable tipada; una petición demasiado grande puede ser rechazada aunque el uso estable todavía sea AVAILABLE. No declarar lleno por un simple fallo de request.
- delete/export de contenido existente permanecen; no purge automático.
- Events contienen IDs/scope/kind/mediaType/bytes/chunks/timings/codes, no adquisición completa ni secretos.
- Local refresh: selección nueva → lectura única acotada → comparación digest/representación → unchanged o nueva revisión; evento knowledge.source.refreshed correlacionado. Fallo conserva anterior.

## Gate — criterio individual

1. **source list/status/detail DTOs (§62,§§6,19,29,45) — PASS**. Core SourceSummary/Detail version 1 + separate inspection port; scope-bound metadata only, bounded 20 revisions or exact revision ID; history/deleted/source mismatch contracts.

2. **CLI/JSONL parity (§62/33) — PASS**. Authenticated KnowledgeCommand same Application; detail/status/refresh/export/remote actions, exact HMAC, no second Turn, path/metadata/actor adversarial contracts.

3. **Desktop mínimo (§62/33/40) — PASS**. 68 Node contracts + real React rendering + TypeScript/frontend build. Main-owned refresh/export picker and remote native-consent seam (dialog double); data projections only, no renderer DB/parser/grants.

4. **delegated knowledge capsule (§62/35) — PASS**. Parent-admitted refs/revisions/token budget only; no store/retriever exposed to child; scope/eligibility/forwarding shrink-only per Generation; real SubAgent/coordinator + scripted provider; shared caps 4K–64K and truthful zero admission.

5. **privacy/remote forwarding (§62/38) — PASS**. Default off, trusted host policy setter; human native confirmation with frozen/stale fields; revoke revalidated between remote Generations. Search and MEMORY consent remain independent. Metadata inspection omits body/fingerprint.

6. **quotas/observability (§62/41/42/46) — PASS**. Existing 256MiB session/2GiB workspace/2000 sources/100k chunks, no OS quota claim. Stable raw-body+pending accounting; typed rejection/usage state/capacity.hit, export/delete preserved. Counts/types/timings only, no full docs.

7. **adversarial tests (§62/53) — PASS**. Wrong scope/forged paths/actor/citation refs, metadata-only reads, guard-literal user/system preservation, consent races/prototype keys, no overwrite/managed export, stale/deleted/no refill/no auto-MEMORY.

8. **cierre no business logic renderer — PASS**. Backend owns extraction/store/scopes/metadata/policy/lifecycle. Main owns user selections/dialogs; React displays DTOs and dispatches controls only.

9. **cierre no child global access — PASS**. Bound callback over ≤10 parent-admitted rows, no new global query/catalog/blob reads, existing ToolRuntime/ceiling inheritance for acquisitions; unknown/unadmitted IDs denied.

10. **cierre capacity states honestos — PASS**. Full state derived from counts/bytes; oversized request can be denied while stable state is still AVAILABLE. No purge; existing content export/delete remain.

11. **regresión Core/Security/Memory/HEAD — PASS**. 671 Knowledge, 37 K7, 791 MEMORY, 401 Core/S5/subagents, 26 PDF, 68 Desktop + TypeScript/frontend. HEAD 4818 PASS + 53 subtests, 0 FAIL/ERROR, same11 historical skips and12 excludes.

KI-OD aplicables: 03/04/12/13/16/17/18/20/21/23/24/27/28. Invariantes demostrados/reutilizados: scope/ownership/metadata containment; 001–011,016–019,024–035,038–040, separation de MEMORY/authority y shared cap. Exact/FTS y semantic fallback permanecen bajo K4; no se recertifica semantic/OCR.

## Tests y regresión

| Gate | Resultado final | Evidencia |
|---|---|---|
| K7 específico | **37 PASS** | Host/SQLite/FTS/parsers/context/subagent/coordinator reales; provider/HTTP doubles declarados |
| Knowledge K0–K7 | **671 PASS** | Sin nuevos skips/xfail |
| MEMORY reconciliado | **791 PASS** | Un test adicional de tamper-rejection del delta histórico; no behavior MEMORY nuevo |
| Core/context/S5/subagentes | **401 PASS** | Contratos y regression relacionados |
| PDF repair K3 | **26 PASS** | Parser pypdf real y fixtures sintéticos |
| Desktop | **68 PASS** | 50 anteriores +18 K7; Node + React static render; diálogos con doubles |
| TypeScript/frontend | **PASS** | tsc --noEmit + Vite frontend a Temp; no install/package/publish |
| HEAD completo | **4818 PASS +53 subtests PASS /11 SKIP históricos** | **0 FAIL/ERROR**, exit code 0 |

Los gates se solapan: no sumar sus denominadores. HEAD tiene **4829 testcases** =4818 PASS+11 SKIP; XML header **4882 outcomes** incluyendo 53 subtests. Los 11 skips y las 12 exclusiones son exactamente los de K6; listados/comparados en manifest. Sin nuevos skip/xfail/exclusiones.

Runners: run_k7, run_k0, run_k3_pdf_repair, tests.memory_v1.run_regression y run_k7_desktop. Exact commands/runtime/timestamps/exit codes/hashes en manifest. Pytest sin plugin autoload/cacheprovider; HOME/APPDATA/TEMP/basetemp/runtime privados **fuera del checkout**. No datos personales/model downloads/cloud/GPU/config global.

### HEAD XML

- Inicio registrado UTC: `2026-10-08 09:04:35 UTC`.
- Inicio JUnit: `2026-10-08T03:04:40.246886-06:00`; fin runner UTC: `2026-10-08T09:11:34.7409306Z`.
- Tiempo pytest **413.23s**; JUnit `413.165s`.
- XML: `C:/Users/joseh/AppData/Local/Temp/nova-k7-20261008/head-final/tests.xml`.
- SHA-256: `930d17dbebbc494b416b2327331603a5e5546c8d8cfc10b3e49912eb9338f119`.
- Exit code **0**; command → manifest head.run.command.

### Fallos/descubrimientos preservados

- block1/block2: **HARNESS_BUG**, asumía cap35 bytes y primera publicación sin comprobar el tamaño real del fixture. Se derivó el cap del mismo archivo sintético y se exige publicación inicial; no cambio de producto/defaults/corpus/gold.
- block4: **HARNESS_BUG**, join5s de helper K2 para 1.1MiB/50k bloques; join45s acotado en test, sin retry ni ampliar HTTP30. Mismo body y assertions de persistencia.
- block4: **HARNESS_BUG**, exigía MEMORY+documento siempre en 4K; se comprueba admission real/caps/user priority y cita inválida si no hay documento. No PASS de un guess.
- memory-final: **HISTORICAL/PREEXISTING expectation de harness**, 789 PASS/1 FAIL. Freeze M8 esperaba sub_agent.py inmutable de la campaña. Se reconoce sólo el delta K7 exacto/reversible, reproduciendo SHA histórico `aec584fb687e771cc99af9f29d1fa7b8794336f80fbb699aa6344e5b1e18d69d`; todo el resto sigue pinneado. Regresión niega tamper/timeout/MEMORY changes. **No** se modifica freeze/dataset/resultado/calidad M8.
- refresh-contract-before: **PRODUCT_BUG introducido K7**, 1 FAIL demostrado de §40. Reparado unchanged/new revision y refreshed event. Corridas anteriores y tres freezes preservados; final_freeze identifica reparación específica.
- Inspección adversarial: **PRODUCT_BUG compartido**, cleanup por texto podía borrar user/system literal del guard. Metadata privada host-only distingue guard; strip antes del modelo; regresión actual PASS.
- Inspección >1MiB: **PRODUCT_BUG K6 compartido**, body S5≤2MiB se entregaba como unidad K1>1MiB. Ahora unidades256KiB; límites S5/K1 intactos; real parser/store con1.1MiB PASS. No historia K6 reescrita.
- Desarrollo: WorkingMessages duplicado podía separar callback de documento al añadir MEMORY; misma instancia preservada. Lookup JS usa own keys contra prototype actions. Ambas regresiones actuales PASS.
- Approval block5: **ENVIRONMENT**, revisión automática expiró antes de iniciar; único retry autorizado block5-retry. No reintento de una operación de producto/test.

No PRODUCT_BUG pendiente demostrado. No falla se convierte en skip/xfail. Evidencia inicial/fallida conservada, no reinterpretada.

## Archivos modificados/creados

Respecto del working tree **inicial**, no del HEAD antiguo:

- `local_cli/sub_agent.py`
- `tests/memory_v1/test_m8_ps_operational.py`
- `desktop/electron/preload.ts`
- `desktop/electron/knowledge_control.d.cts`
- `local_cli/interfaces/knowledge_cli.py`
- `desktop/src/components/MessageBlock.tsx`
- `local_cli/application/knowledge.py`
- `local_cli/application/knowledge_host.py`
- `local_cli/application/session.py`
- `desktop/electron/application_client.ts`
- `desktop/src/types.ts`
- `local_cli/bootstrap_knowledge.py`
- `desktop/shared/application.ts`
- `desktop/electron/main.ts`
- `local_cli/infrastructure/knowledge_sqlite.py`
- `desktop/src/App.tsx`
- `local_cli/application/knowledge_web.py`
- `desktop/electron/knowledge_control.cjs`
- `local_cli/application/knowledge_context.py`

Nuevos producto/tests:

- `tests/knowledge_inputs_v1/test_k7_children.py`
- `local_cli/application/knowledge_children.py`
- `local_cli/infrastructure/knowledge_export.py`
- `local_cli/core/knowledge_views.py`
- `tests/knowledge_inputs_v1/run_k7.py`
- `desktop/tests/knowledge_k7.test.cjs`
- `local_cli/core/knowledge_delegation.py`
- `tests/knowledge_inputs_v1/run_k7_desktop.py`
- `tests/knowledge_inputs_v1/test_k7_host.py`

Evidencia nueva: k7_resultados.md, k7_manifest.json y k7_evidence/{implementation_freeze,closure_freeze,final_freeze}.json. Todo K0–K6 histórico y arquitectura conservados por hashes. Sin migración/dependency/CI/cosmetic refactor general.

## Limitaciones, deuda y OPEN DECISIONS

- No K8 ni READY ni calidad universal; LLM local/search/embedding real **NOT_EVALUATED** en K7. Native Electron E2E no ejecutado; Desktop son contracts/React/build, no certificado de integración de modelo.
- No sandbox, OS quotas, DLP/cifrado/universal injection/entailment/secure erase. Export parcial incierto no se borra ni se oculta.
- Byte budget no equivale a footprint SQLite/index/WAL; inspection metadata acotada, no body preview.
- Parent y child pueden admitir cero evidencia; datos delegados nunca crean autoridad ni writes MEMORY.
- Revocación opera para envíos futuros; no promete retirar datos ya transmitidos. Actor/control durante Turn activo conserva conflictos Core; revalidación detecta cambios externos entre Generations.
- Semantic documental y MEMORY **NOT_CERTIFIED**. No recertificación, OCR ni Active Web añadidos.
- **OPEN DECISIONS bloqueantes: ninguna.** No se fijaron decisiones K8 futuras ni thresholds/corpus nuevos.

Siguiente fase lógica: **K8**, sólo referencia. Se detiene en **K7 PASS** para revisión humana. Sin commit, push o tag.
