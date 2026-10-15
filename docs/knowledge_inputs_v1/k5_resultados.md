# K5 — Context, provenance y citations

## Resultado

**K5 PASS** — §60 de `NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md`.

Perfil evaluado: **Windows 11 + NTFS local + HOST_UNISOLATED**. No sandbox/process isolation. `DOCUMENT_SEMANTIC_PROFILE = NOT_CERTIFIED`; `MEMORY SEMANTIC_PROFILE = NOT_CERTIFIED`. No K6 ni READY.

## Preflight y precedencia

- Branch: `main`; HEAD: `717a24218dea7fb60d8b630896d653e39091bc7b`.
- Working tree inicial: 145 entradas dirty/untracked; 1773 archivos versionables, todos preservados salvo los cambios K5 explícitos. Inventario inicial íntegro en el manifest/preflight privado.
- Runtime: CPython 3.14.6, AMD64; Windows 11 build 26200; C: NTFS Fixed local.
- Tags Core/Security/Memory anteriores intactos; objetos y commits peeled registrados en el manifest.
- Arquitectura Knowledge SHA-256: `417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432`.
- Baseline antes de editar: Knowledge **524 PASS**; fronteras Core/context/RAG **131 PASS**.
- Se verificaron todos los pins del freeze K4. Se preservaron K3 histórico, reparación PDF, K4 BLOCKED original, K4 resume PASS y sus artefactos; el HEAD K4 previo conserva su XML/hash.
- Precedencia aplicada: Core controla lifecycle/context; SECURITY autoridad y tools; MEMORY su dominio; Knowledge sólo evidencia documental. No contradicción normativa pendiente.
- El encabezado histórico «propuesta» no se modificó: la aprobación del usuario establece el baseline normativo.

## Inventario y alcance aplicado

Ya existían Source/Revision/Locator y scopes (K0), store/lifecycle/recovery (K1), imports y attachmentRefs (K2), extracción real y locators (K3), exact/FTS/candidatos acotados/semantic opcional (K4).

Se reutilizan ContextManager y WorkingMessages; Provider bound por Turn; coordinator/Event System/persistencia; la redaction existente; el cap MEMORY/RAG y factories compartidos por CLI/Desktop.

Faltaban Capsule, registro de citas, admission documental y validación/proyección de provenance. K5 conecta esas piezas; no añade parsers, acquisition, FTS, scoring, embeddings, Active Web ni otro AgentLoop.

Legacy RAG/notes siguen siendo datos acotados, sin IDs K validables ni reinterpretación de vectores. Sin consentimiento de Source, contenido legacy no se envía a un provider remoto/no verificable.

## Implementación y contratos

1. Core incorpora `KnowledgeEvidence`, `CitationTarget`, `CitationRegistry` y `KnowledgeCapsule` inmutables. Sólo contratos/stdlib; sin SQLite/Ollama/host IO.
2. Application consulta el K4 scoped store una vez por Turn. Fija provenance desde candidatos validados; attachment refs restringen source/revision. Generaciones siguientes sólo revalidan los IDs/revisiones ya seleccionados, sin refill/retrieval nuevo.
3. Se renderiza evidencia JSON escapada como `role=user`, no system/project. El guard estático pertenece al host, no al documento. Excerpts truncados se identifican como tales.
4. Core trata filas de evidencia como unidades atómicas bajo el cap compartido. No corta JSON, citation IDs ni guard/footer. No cambia fórmulas/reservas/AUTO/presets.
5. Sólo filas efectivamente admitidas obtienen IDs K1… con targets source/revision/chunk/locator. IDs supervivientes no se renumeran tras delete.
6. Application valida referencias del assistant: mismo Turn, ID existente/admitido y target previamente validado. IDs desconocidos se reportan `CITATION_INVALID`, nunca como evidencia válida. El texto observado no se falsifica ni se reescribe para fingir un éxito.
7. Recibos `knowledgeCitations` con `schemaVersion=1` y `structuralOnly=true` quedan en transcript/snapshot. El payload Capsule no se persiste. Metadata histórica no se usa como autoridad ni se reenvía como campos de provider.
8. MEMORY recibe únicamente el current user content; attachment/document no se transforma en USER_ASSERTION ni auto-write. El recall MEMORY sigue intacto.
9. Default remote forwarding conserva la policy Source existente: sólo destination local verificado o permiso explícito del Source. Endpoints desconocidos no se consideran locales.
10. No cambios de schema SQLite/migrations/dependencias/tool schemas/grants/Policy/Approval/audit. Snapshot agrega una proyección opcional; no segundo backend de frontend.

## Trazabilidad y gate literal

| Requisito | Resultado | Evidencia |
|---|---|---|
| KnowledgeCapsule por Turn (§26) | PASS | Capsule/SourceRegistry/CitationRegistry inmutables; un query inicial, revalidación acotada sin refill por Generation. |
| CitationRegistry (§27) | PASS | IDs K1… sólo para filas admitidas; source/revision/chunk/locator y presentación se fijan por Application. |
| Wrappers de evidencia (§§36–37) | PASS | JSON escapado, role=user y kind=knowledge; guard estático host-owned; documentos nunca son instrucciones system/project. |
| Shared budget (§25) | PASS | Nueva clase documental dentro del mismo retrievalTokens/SharedRetrievalCap; no nueva reserva; filas atómicas. |
| Citation validation (§28) | PASS | Same-Turn y admitted-only; IDs inventados/desconocidos inválidos, locators alterados rechazados; recibos versionados. No claim de entailment. |
| MEMORY coexistence (§34) | PASS | Ambos dominios comparten cap; sólo current user se captura; el documento no escribe memoria ni se transforma en USER_ASSERTION. |
| Current user priority (gate §60) | PASS | 15 casos 4K–64K, tools/MEMORY/RAG en 5 ventanas, user near-limit y 10k history; admisión opcional puede ser cero. |
| Citations válidas (gate §60) | PASS | Target real PDF/DOCX/JSON; mismo Turn; delete/supersession no reasignan IDs; validaciones negativas y persistencia sintética. |
| Authority separation (gate §60) | PASS | Ningún grant/approval/ceiling/policy nuevo; ToolRuntime intacto; host remoto/desconocido denegado por default; mismo backend CLI/Desktop. |

Decisiones aplicables: KI-OD-13,16,17,18,19,21. Invariantes demostrados: KI-INV-004, KI-INV-005, KI-INV-006, KI-INV-007, KI-INV-016, KI-INV-017, KI-INV-018, KI-INV-019, KI-INV-025, KI-INV-026, KI-INV-027, KI-INV-028, KI-INV-029, KI-INV-039.

Validación de citas es **estructural**, no entailment ni verdad garantizada. Los targets conservan los locators reales de K3; una cita no crea permisos.

## Tests y regresión

| Campaña | Resultado | Tipo |
|---|---:|---|
| Baseline Knowledge | 524 PASS | Unit/contract/integration; fuentes sintéticas |
| Baseline fronteras | 131 PASS | Core/context/provider/RAG |
| K5 focused final | 49 PASS | 35 contratos contexto/provenance + 14 integraciones; provider scripted |
| Knowledge K0–K5 | 573 PASS | Store/extraction/FTS/admission reales; semantic doubles |
| PDF repair preservado | 26 PASS | pypdf real, PDFs sintéticos |
| MEMORY | 790 PASS | Regresión vigente, no embeddings/Ollama real |
| Fronteras finales | 131 PASS | Core/context/provider/RAG |
| Compatibilidad de harness | 23 PASS | Golden preservado; destinations locales explícitos |
| HEAD closure | **4719 PASS / 0 FAIL / 0 ERROR / 11 SKIP** | Gate nativo completo aplicable |
| Subtests HEAD | **53 PASS** | Adicionales a los 4730 testcases top-level |

Denominador HEAD: **4730 testcases** = 4719 PASS + 11 SKIP; XML declara **4783 outcomes** contando los 53 subtests. Exit code **0**; duración pytest 334.07 s.

No nuevos skips/xfails/exclusiones. Se conservaron las 12 exclusiones aprobadas de HEAD; los 11 skips coinciden exactamente con K4 (listados en manifest). No se usa mock/scripted como calidad de un LLM ni como certificación semantic.

Todos los comandos exactos, runtimes, timestamps, XML/log/run.json y SHA-256 están en el manifest. Runners: `tests.knowledge_inputs_v1.run_k5 --mode k5/compatibility`, `run_k0 --mode contracts/boundaries`, `run_k3_pdf_repair --mode pdf`, `tests.memory_v1.run_regression --mode m0/head`, siempre `python -B` y `--extra-test-site` existente.

Los runners deshabilitan plugin autoload/cache y usan configuración, runtime/temp y `--basetemp` privados **fuera de Git**. No conversaciones reales/secretos/configuración global/model downloads.

### XML HEAD

- Inicio JUnit: `2026-10-08T00:51:30.530535-06:00`.
- Fin runner: `2026-10-08T06:57:05.7654521Z`.
- Path: `C:/Users/joseh/AppData/Local/Temp/nova-k5-20261008/head-closure/tests.xml`.
- SHA-256: `417576d5d55173f77e0c2787cadcf2bebc22532b39238a12c919a270d35d399e`.
- Comando completo: manifest → `head.run.command`.

### Fallos preservados y clasificación

Se conservan las corridas iniciales, no se sustituyen por PASS:

- `k5-first`: 1 ERROR, **HARNESS_BUG** — import innecesario de fixture inexistente.
- `k5-second`: 37 PASS/1 FAIL, **HARNESS_BUG** — DTO MemoryRecordPage requiere `.records`, no `len(page)`; requisito «un record» intacto.
- Campaña ampliada: token synthetic/contrato de error y mock de teardown incorrectos, **HARNESS_BUG**. Se valida el código tipado, no el mensaje UI.
- Large-history: assertion nueva exigía admission obligatoria a pesar de la precedencia Core §17/MEMORY §19.2. **HARNESS_BUG**, demostrado también con legacy retrieval sin cambiar su implementación. Se comprueban candidato recuperado, admisión cero y guesses inválidos. No ranking/corpus/gold/threshold cambiado.
- Primer HEAD: **4716 PASS, 3 FAIL, 11 SKIP, 53 subtests PASS**; XML preservado: `head-final/tests.xml`, SHA `b8ad58534cd057aae376908d82a61f05e970b2f12ce4500af4ceb0b28e88b847`.
  - Phase0 characterization: **HARNESS_BUG** — faltaba validar la observación aditiva knowledge_recall. Ahora se comprueba su frame exacta antes de comparar todas las frames originales con el golden intacto.
  - Server/CLI RAG: **HARNESS_BUG** — sus doubles locales no declaraban endpoint verificable. K5 correctamente denegaba forwarding por §38. Los doubles ahora anuncian loopback; assertions RAG originales intactas. El camino remoto/no verificado permanece probado como denegado.

No PRODUCT_BUG pendiente demostrado en estas regresiones.

## Budgeting, performance y persistencia

- Matriz 4K/8K/16K/32K/64K × user pequeño/mediano/grande: 15 casos; reservas, caps y determinismo verificados. Evidencia: `k5_evidence/budget_matrix.json`.
- Evidencia pequeña: **147 tokens** estimados Core cuando entra. Se conserva explícitamente el caso 8K/user 1400 + historia donde admite **0**; no se rellena el cap ni se atribuye recall a un guess.
- MEMORY + Knowledge + legacy RAG y ToolResults probados en las cinco ventanas; user obligatorio y continuidad no se sustituyen por documentos.
- Prueba 10k history conserva el transcript y limita el prompt/candidatos; sin escaneo del catálogo/lectura de blobs durante recall. No significa «no materializar jamás el transcript»: el baseline Core sigue construyendo working context.
- FTS K4: evidencia publicada, hash validado, **p95 2.2483 ms <=100 ms** (1000 chunks/60 queries). No se cambió FTS/ranking ni se reinterpreta esta medición como nuevo benchmark K5/LLM.
- Verificación adicional [T] de outputs sintéticos: **14 transcripts**, **15 recibos**, **9 targets válidos**, **0 capsules persistidas**. Referencias sobreviven al cierre/delete sin reescribir historia; UUIDs/version/structuralOnly verificados. `k5_evidence/persisted_citations.json`.
- No claim nuevo de p95 de construcción de contexto, inferencia, otros hosts ni real semantic quality.

## Archivos de esta fase

Modificados respecto del working tree inicial:

- `local_cli/bootstrap_knowledge.py`
- `tests/test_nova_core_phase0_characterization.py`
- `local_cli/application/context.py`
- `tests/test_nova_core_phase10_services.py`
- `local_cli/application/session.py`
- `local_cli/core/context.py`
- `local_cli/application/providers.py`
- `local_cli/application/knowledge_host.py`

Creados producto/tests:

- `local_cli/application/knowledge_context.py`
- `tests/knowledge_inputs_v1/run_k5.py`
- `local_cli/core/knowledge_context.py`
- `tests/knowledge_inputs_v1/test_k5_integration.py`
- `tests/knowledge_inputs_v1/test_k5_context.py`

Evidencia nueva: este reporte, `k5_manifest.json`, `k5_evidence/implementation_freeze.json`, `closure_freeze.json`, `budget_matrix.json`, `persisted_citations.json`. El primer freeze queda preservado; closure freeze sólo incorpora la reconciliación de los dos tests de harness/runner, sin cambios adicionales de producto.

## Limitaciones, deuda y OPEN DECISIONS

- No entailment/veracidad universal ni defensa perfecta frente a prompt injection/secrets.
- Sin certificación semántica nueva; no recertificación MEMORY, inferencia real 32K/64K ni E2E real K8.
- Datos opcionales pueden quedar fuera; no se fuerza admission por existencia de una fuente.
- UX citation-detail/estado current/deleted y delegación documental avanzada corresponden a K7; no se adelantaron.
- No nueva UI de consentimiento/remembrance de sources; no write MEMORY desde Knowledge.
- No claims de POSIX certificado, secure erase, sandbox o aislamiento OS.
- Primer materializado de contexto conserva costes del Core existente; no se anuncian optimizaciones/SLA no medidos.
- **OPEN DECISIONS necesarias para K5: ninguna.** No se resuelven decisiones futuras.
- Siguiente referencia: **K6 — Passive Web**, sin implementarlo.

Sin commit, push ni tag. Se detiene para revisión humana.
