# Auditoría final de los 40 criterios READY — Knowledge Inputs V1

Fecha UTC: 2026-10-09T04:08:09.750754+00:00. Informe aditivo, misma conversación/proyecto.

Resultado oficial inmutable: `K8 CERTIFICATION V2 FAIL`.

## Resultado de la auditoría

**38 SATISFIED; 1 NOT_EVIDENCED; 1 BLOCKED.** Hay **un único hueco material de evidencia**, no dos: source-conflict E2E con modelo local real (§51, criterio 35). El criterio 1 está BLOCKED por esa dependencia de cierre de K8. No se exige hacer PASS la campaña histórica, rescatar V2 ni repetir sus 35 intentos.

La reconciliación aceptada permanece intacta: KI-INV SATISFIED=40; VIOLATED=0; NOT_EVIDENCED=0. Esa matriz es §53, no los criterios READY de §64. **No hay una reparación nueva de producto demostrada como necesaria. No se declara READY.**

La campaña original está formalmente CLOSED, pero su manifest distingue `campaignStatus=CLOSED` de `phaseStatus=K8 PARTIAL`: cerrar administrativamente una campaña con un escenario obligatorio fallido no completa por sí solo el cierre normativo. Una futura evidencia aditiva satisfactoria puede cerrar esa dependencia sin cambiar 13/14 ni V2 FAIL.

## 1. Correcciones focalizadas R1/R2

Código nuevo: [ready_harness](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/ready_harness/README.md). No se modificó el adaptador/runner/scorer congelado de V2: sería una modificación retrospectiva prohibida. Las APIs corregidas quedan disponibles para futura evidencia focalizada independiente, no para reevaluar V2.

### R1 — authority/effects

`observe_tool` correlaciona operationId, ToolRequested, ToolStarted y terminal con ToolResult. Publica por separado:

- tool request y argumentos;
- tool rejected: DENIED y su código;
- tool executed: dispatch observado mediante ToolStarted, no inferido del request;
- observable effects: diferencias en snapshots Files/Memory;
- authority changes y document-derived authority: evidencia host independiente, source/revision y audit reference.

Un `web_search` rechazado con `REMOTE_SEARCH_DISABLED` tiene request, rechazo y terminal, **sin ejecución, DNS, grant, efecto ni DOCUMENT_AUTHORITY**. Un search pasivo ejecutado mediante HTTP scripted tiene dispatch y grant legítimo de host, pero no autoridad derivada del documento. Una mutación Files/Memory tampoco prueba por sí sola esa procedencia. La evidencia documental positiva sintética no se oculta; provenance insuficiente queda UNRESOLVED, no safe/PASS.

Los tests tool-only no componen MEMORY: no atribuyen a su snapshot una inspección de un Memory global. HTTP es un puerto scripted, con sockets/DNS reales prohibidos. Cuatro tests R1 son unitarios sintéticos explícitos y dos pasan por ToolRuntime real; no constituyen evaluación de comportamiento LLM.

### R2 — aislamiento/propietario único

`IsolationFixture` compone **un store físico y un KnowledgeLease**; servicios KnowledgeService distintos comparten ese puerto, no KnowledgeAccess ni contexts. Workspace identity se deriva del path con la misma regla productiva. Recovery ocurre una vez antes de la siembra; todas las sesiones/workspaces permanecen vivos durante la comparación.

Import usa LocalHostFileAcquisition + prepare_revision productivos; consulta usa KnowledgeService + DocumentRetriever reales sobre documentos nuevos de prueba, no casos del examen. Se observan sourceId/revisionId/chunkId reales. Los tests prueban:

- SESSION de peer visible para peer e invisible para target y workspace ajeno;
- WORKSPACE visible entre sesiones del mismo workspace;
- source de otro workspace vivo pero invisible para target;
- segundo owner físico todavía rechazado con `KNOWLEDGE_STORE_LOCKED`.

No se desactiva, relaja ni cambia el lock productivo; no se usa close/reopen para vaciar artificialmente sources ajenos.

### Resultado y trazabilidad de desarrollo

Ejecución focal final: **10 PASS, 0 FAIL/ERROR/SKIP**, 6 R1 + 4 R2. [JUnit][F] y [run.json](C:\Users\joseh\Downloads\nova-local-cli\k8-certification-evidence\focused-harness\r1-r2-20261009T040413Z-48a6a06a25cd447999922d54262863de/run.json). 8 retrievals y 3 imports de fixture, 0 admission, 0 inferencia. Los IDs/casos son de prueba focal y no pertenecen a K8 V2.

Dos ejecuciones de desarrollo anteriores permanecen preservadas, sin sobrescribirlas:

1. `r1-r2-20261009T040251Z-3a8d9230373b4f60a6c2352b104dae64`: error de colección por pypdf fuera del import path; ningún test/caso ejecutado. Se reutilizó en lectura el árbol de dependencias previamente congelado, sin instalar/descargar. Su primera metadata imprimía contadores planificados 8/3, no observados: **recuento correcto 0 retrieval/0 import**.
2. `r1-r2-20261009T040334Z-19724e8195204c909bb7d7e383869955`: 7 PASS, 3 FAIL por serializador focal que intentaba leer `candidate.chunk_id` en lugar de `candidate.chunk.chunk_id`. No es fallo de aislamiento/producto: los tres traces muestran import terminado y retorno del retrieval antes del AttributeError. **3 imports y 3 retrievals**, no 0: la metadata sólo contaba capturas terminales, ausentes en esos tres tests.
3. Ejecución final indicada arriba: serialización correcta y eventos persistidos antes del rendering; contadores derivados de eventos reales (8/3).

Este recuento es una aclaración **aditiva** de metadata propia de desarrollo, no una edición de aquellos archivos ni de evidencia histórica. Total de esta tarea: 6 imports y 11 retrievals focales, **0 inference, 0 admission, 0 campañas/casos K8**. No se presenta debugging de tests focales como retry de campaña.

Se verificaron **629 pins R4** antes/después y **2652 archivos protegidos** durante la ejecución final, sin drift. Producto, estados históricos, R1–R4 congeladas, ledger y evidencia V2 permanecen intactos. Outputs nuevos fuera del checkout en `k8-certification-evidence/focused-harness/`; código/informes nuevos dentro del proyecto, sin Temp nuevo.

## 2. Matriz completa §64

Estados: SATISFIED = evidencia vigente suficiente en el alcance normativo; NOT_EVIDENCED = falta evidencia requerida; BLOCKED = dependencia pendiente. Un PASS contractual/sintético no sustituye E2E LLM. Una limitación opcional ya aceptada no añade un criterio nuevo.

| criterion | required evidence | existing evidence | status | remaining gap |
|---|---|---|---|---|
| 1. K0–K8 cerrados. | Cierres trazables de K0–K8, con sus resultados reales; no equivaler cierre de una campaña fallida a cierre satisfactorio del gate normativo. | K0–K7 PASS y manifiestos publicados; campaña original formalmente CLOSED/13 de 14, pero phaseStatus=K8 PARTIAL. Calidad/regresión actuales válidas; source-conflict E2E pendiente. ([K][K], [E][E], [R][R], [H][H]) | BLOCKED | Cerrar el gate normativo K8 con evidencia aditiva del criterio 35 y resolución final separada; jamás recalificar la campaña histórica. |
| 2. Core V1 continúa verde. | Regresión Core aplicable vigente, sin contradicción de sus contratos. | HEAD current-regression 5159 PASS, 11 skips heredados, 53 subtests PASS; paths actuales pinneados. No cambios productivos en esta tarea. ([H][H], [CAP][CAP]) | SATISFIED | — |
| 3. SECURITY V1.2 continúa verde en su alcance. | Regresión SECURITY V1.2 dentro de su alcance, con mediación PUBLIC_ONLY y autoridad preservadas. | HEAD actual y K6 con ToolRuntime/grants reales; suites SECURITY nativas históricas pertinentes preservadas. HOST_UNISOLATED no se vende como sandbox. ([H][H], [W][W], [INV][INV]) | SATISFIED | — |
| 4. MEMORY V1 continúa verde y separado. | Regresión MEMORY y separación de stores/lifecycle/consent/budget. | HEAD MEMORY verde; K5 coexistencia; E2E original memory-plus-knowledge PASS con valor documental y preferencia separada. ([H][H], [C][C], [E][E]) | SATISFIED | — |
| 5. Source/Revision schema versionado/migrable. | Schema Source/Revision versionado, migración y rechazo de schema incompatible. | K1 store/migrations/recovery PASS en HEAD; identities y revisiones inmutables, lineage y publicación atómica comprobados. ([K][K], [H][H], [INV][INV]) | SATISFIED | — |
| 6. Recovery de import/crash/cancel probado. | Recovery real de import, salida abrupta/crash y cancel cooperativo, sin falsa publicación. | K1 real_process_exit_atomic_publication_recovery y contratos de cancellation PASS en HEAD; K2 pipeline mantiene operaciones tipadas. ([K][K], [H][H], [INV][INV]) | SATISFIED | — |
| 7. SESSION/WORKSPACE isolation probado. | Scope SESSION y WORKSPACE aplicado en las superficies de acceso; fixture con composición válida. | K1/K4/K7 scope PASS en HEAD; R2 focal prueba sesiones simultáneas, WORKSPACE compartido entre sesiones y workspace ajeno invisible, un owner físico. ([K][K], [H][H], [F][F], [INV][INV]) | SATISFIED | — |
| 8. Metadata/artifact containment probado. | Ownership/containment de metadata, blobs y artifacts, incluidos ataques de paths/NTFS. | K1 containment y K2 host acquisition PASS en HEAD; no importar claims S3/OS confinement de rutas no mediadas. ([K][K], [H][H], [INV][INV]) | SATISFIED | — |
| 9. Delete/no-resurrection documental probado. | Delete retira proyecciones y evita resurrection a través de refresh/restart/rebuild. | K1/K2/K4 delete/tombstone PASS en HEAD; E2E original deleted-abstain PASS. No secure erase ni borrado automático de MEMORY/audit. ([K][K], [H][H], [E][E], [INV][INV]) | SATISFIED | — |
| 10. TXT/MD/code/JSON/CSV/HTML/PDF textual/DOCX tienen camino productivo completo. | Adquisición, extractor productivo, chunking/retrieval y contexto para todos los formatos anunciados. | K3 real extractors más reparación PDF; 64/64 extraction/mapping K8 standalone; HEAD K3 y parser contracts PASS. E2E real attachment/PDF/DOCX/JSON/code PASS. ([K][K], [P][P], [S][S], [H][H], [E][E]) | SATISFIED | — |
| 11. Unsupported/corrupt/partial se diferencian. | Unsupported, corrupt y partial tipados, sin aparentar READY completo. | K3/K6 y PDF repair; errores críticos K8 8/8; HEAD contratos de estados/URL truncada/imagen parcial PASS. ([P][P], [S][S], [W][W], [H][H], [INV][INV]) | SATISFIED | — |
| 12. PDF usa parser real y conserva página. | Parser PDF real y locator de página real; no simulación en TXT. | pypdf 6.19.0; PDF repair páginas 1,1,2, documento real y pipeline host; 26 tests PDF PASS en HEAD y pdf-citation real PASS. v2c-008 no se usa como evidencia PDF. ([P][P], [H][H], [E][E]) | SATISFIED | — |
| 13. DOCX aplica container bounds. | Bounds del contenedor DOCX antes de expansión y extracción productiva. | K3 y HEAD test_docx_container_entry_limit_enforced_before_expansion / test_docx_container_ratio_bound_before_expansion PASS; DOCX real E2E PASS. ([K][K], [H][H], [E][E]) | SATISFIED | — |
| 14. URL acquisition conserva SECURITY PUBLIC_ONLY. | URL acquisition mediante SECURITY PUBLIC_ONLY, redirects/DNS/grants acotados. | K6 runtime/S5 real con puertos HTTP sintéticos y pruebas nativas pertinentes; URL E2E original usa web_fetch real de example.com con ToolResult y audit. ([W][W], [H][H], [E][E]) | SATISFIED | — |
| 15. `web_search` es pasivo y capability-gated. | web_search pasivo, opt-in/capability-gated; snippet no es fetched page. | K6 runtime/provider contracts PASS; R1 focal real REMOTE_SEARCH_DISABLED sin DNS/grant/dispatch y HTTP scripted permitido sin browser/páginas extra. ([W][W], [H][H], [F][F]) | SATISFIED | — |
| 16. Attachments no se convierten en user assertions. | Attachment/document content mantiene categoría datos; no se convierte en input/assertion del usuario. | K2 refs/actor/scope y K5 document-never-user-capture/hostile labels PASS; Desktop no sintetiza ref ni ingiere por preview. ([K][K], [C][C], [D][D], [H][H], [INV][INV]) | SATISFIED | — |
| 17. Exact/FTS funciona sin embeddings. | Exact y FTS productivos con semantic deshabilitado. | HEAD test_exact_fts_native_and_literal_query_not_fts_program y quality corpus PASS; K4/K8/V6 métricas congeladas válidas sin embeddings. ([Q][Q], [S][S], [R][R], [H][H]) | SATISFIED | — |
| 18. Semantic documental es opcional y degrada seguro. | Semantic opcional; error/timeout/mismatch conserva lexical y degrada honestamente. | K4 semantic_failure_preserves_identical_lexical_evidence y bounded fallback PASS en HEAD; DOCUMENT_SEMANTIC_PROFILE permanece NOT_CERTIFIED. ([K][K], [H][H], [INV][INV]) | SATISFIED | — |
| 19. Embedding spaces documentales están versionados/no mezclados. | Identity completa de embedding space y prohibición de mezclar/reinterpretar espacios. | K4 simultaneous_spaces_are_not_compared_or_reinterpreted y parámetros de identidad/dimensión/profile PASS en HEAD. ([K][K], [H][H], [INV][INV]) | SATISFIED | — |
| 20. Legacy vectors no se reinterpretan. | Vectores legacy no se reinterpretan como V1; rebuild sólo desde originals verificados. | K4 explicit_legacy_source_rebuild_real_k2_k3_k4_fts_no_vector_migration PASS en HEAD; ruta legacy permanece independiente. ([K][K], [H][H], [INV][INV]) | SATISFIED | — |
| 21. Source deleted/superseded no aparece como current. | Current selecciona sólo revisión vigente de source elegible; deleted/superseded no current. | K1 refresh lineage y K4 candidates current/deleted PASS; E2E update-current y deleted-abstain PASS; V2 fixture lifecycle real aporta observaciones sin recalificación. ([K][K], [H][H], [E][E], [INV][INV]) | SATISFIED | — |
| 22. Retrieval tiene abstention honesta. | Abstención honesta sin evidencia suficiente, sin guesses como retrieval success. | K4 frozen quality abstention=100%; V6 y post-cert negativos=100%; HEAD gates PASS; E2E no-evidence/deleted/wrong-workspace PASS. ([Q][Q], [R][R], [B][B], [H][H], [E][E]) | SATISFIED | — |
| 23. Knowledge+Memory respeta SharedRetrievalCap. | MEMORY+Knowledge+retrieval bajo un SharedRetrievalCap, sin promesa de admitir todas las fuentes a 4K. | K5 matrix 4K–64K y continuity PASS; Capability Resolution permite Knowledge=0 y limita admisión. Supplemental 8K operativo PASS; 4K historical quality=10/15 intacta. ([C][C], [CAP][CAP], [B][B], [H][H]) | SATISFIED | — |
| 24. Current user no se sacrifica por Knowledge. | Prioridad del current user conforme Core; no desplazarlo por Knowledge/framing opcional. | K5 optional_guard_cannot_evict_otherwise_valid_current_input y K7 child task priority PASS en HEAD. ([C][C], [D][D], [H][H], [INV][INV]) | SATISFIED | — |
| 25. Document data no adquiere system/tool/security authority. | Documentos no generan system/tool/security authority; separar request, rejection, dispatch, effect y origen de authority. | K1 containment/K5 hostile document/K6 SECURITY PASS; E2E document-injection PASS. R1 focal prueba rechazo real y tool pasivo ejecutado sin DOCUMENT_AUTHORITY; atribución host independiente/UNRESOLVED explícitos. ([K][K], [C][C], [W][W], [H][H], [E][E], [F][F], [INV][INV]) | SATISFIED | — |
| 26. Knowledge no escribe MEMORY automáticamente. | Knowledge no escribe MEMORY automáticamente; user capture no absorbe documentos. | K5 integration y contratos PASS en HEAD; E2E memory-plus-knowledge conserva escritura explícita de fixture separada. No usar tool call por sí solo como Memory effect. ([C][C], [H][H], [E][E], [INV][INV]) | SATISFIED | — |
| 27. Citations sólo aceptan IDs realmente admitidos. | Sólo citation IDs admitidos en el mismo Turn pueden aceptarse como válidos. | K5 test_citation_ids_same_turn_actual_admission_and_no_entailment_claim PASS en HEAD; K999/K01/Kbad/otro Turn rechazados; cero invalid accepted en original. ([C][C], [H][H], [E][E], [INV][INV]) | SATISFIED | — |
| 28. Citation registry conserva source/revision/locator. | Citation registry persistido conserva source/revision/locator y provenance; no claim automático de entailment. | K5 persisted_citations y mismo Turn; K7 UI/detail provenance; E2E PDF/DOCX y valores documentales con targets reales. HEAD mapping PASS. ([C][C], [D][D], [H][H], [E][E], [INV][INV]) | SATISFIED | — |
| 29. Subagent access documental está acotado. | Subagent bounded parent-admitted data, sin acceso global al store y respetando task/scope/consent. | K7 child_only_admitted_data_bounded_no_global_query_and_current_task_priority PASS en HEAD; caps y shrink-only revalidados. ([D][D], [H][H], [INV][INV]) | SATISFIED | — |
| 30. Remote search y remote document forwarding son controles separados. | Remote search separado de remoteDocumentForwarding; consentimiento documental/Memory no se hereda. | K6 search_enabled_does_not_enable_remote_document_forwarding y K5/K7 consentimiento/revoke PASS en HEAD. ([W][W], [C][C], [D][D], [H][H], [INV][INV]) | SATISFIED | — |
| 31. No auto-download de modelos semantic/OCR. | Semantic/OCR no auto-descargan modelos ni son dependencias de Core. | K3 image-only OCR_REQUIRED sin decoder/model download; K4 semantic DISABLED y degraded; HEAD PASS; perfiles NOT_CERTIFIED explícitos. ([P][P], [H][H], [INV][INV]) | SATISFIED | — |
| 32. Capacity/retention limits activos. | Quotas/capacity/retention activos, con errores honestos; no purge o crecimiento silencioso. | K1 operational_bounds_typed_no_purge_delete_still_available y K2/K3/K4 bounds PASS en HEAD; K7 status/capacity. ([K][K], [D][D], [H][H], [INV][INV]) | SATISFIED | — |
| 33. Critical scope/delete/authority/citation invariants = 100%. | Critical scope/delete/authority/citation a 100% en sus sets contractuales, sin sustituir calidad E2E. | 230 critical contracts K8 PASS; HEAD 1012 Knowledge outcomes PASS y reconciliación 40/40 aceptada; post-cert scope/current/delete 40/40 y false expansion=0. R1/R2 focal PASS, sin extrapolar scores V2. ([S][S], [B][B], [H][H], [INV][INV], [F][F]) | SATISFIED | — |
| 34. KNOWLEDGE_CORE_QUALITY supera thresholds congelados. | Todos los thresholds §49 sobre corpus/gold/scorers congelados y subset lexical-supportable. | Extraction K8 64/64, mapping=100%, typing=8/8; K4 R@5/P@1=96.226%, abstention=100%; K8 lexical 100%/96.970%; V6 100%/100%/100%; HEAD K4/V2-repair/V3/V6 quality PASS y citations/critical gates PASS. ([Q][Q], [S][S], [R][R], [H][H], [C][C], [INV][INV]) | SATISFIED | — |
| 35. Un modelo local real apropiado completa E2E obligatorio. | Todos los escenarios obligatorios §51 con modelo local real y evidencia admitida, no dobles ni guesses. | E2E original 13/14 real, digest completo/modelo/8K/protocolo pinneados. source-conflict FAIL; regression scripted y supplemental 8K no prueban ese escenario con LLM. V2 no aporta un source-conflict exitoso. ([E][E], [B][B], [H][H], [INV][INV], [V2][V2]) | NOT_EVIDENCED | Un único E2E prospectivo focalizado source-conflict real, dos fuentes conflictivas y dos citas válidas/provenance, sin repetir examen/campañas. |
| 36. Performance Core cumple thresholds publicados. | FTS p95 ≤100 ms en corpus/host aprobados, excluyendo generación; imports cooperativos/bounded. | K4 1000 chunks/60 queries p95=2.2483 ms; K8 p95=2.3760 ms; HEAD test_fts_p95_on_published_thousand_chunk_synthetic_corpus PASS y K1/K2 cancel/progress PASS. No claim universal 100k. ([Q][Q], [S][S], [H][H], [K][K]) | SATISFIED | — |
| 37. Regression final no oculta fallos con nuevos skips/xfails. | Regresión final aplicable sin ocultar fallos nuevos con skips/xfails/exclusiones. | HEAD 5159 PASS, 11 skips y 12 exclusiones CI nativas idénticos a historia, 0 nuevos; dos scorers históricos explícitamente no contemporáneos. Código producto pinneado permanece igual; tests focales nuevos 10 PASS, 0 skips. ([H][H], [CAP][CAP], [F][F]) | SATISFIED | — |
| 38. Limitaciones y capabilities no certificadas están documentadas. | Capacidades no certificadas/limitaciones publicadas con alcance honesto. | Semantic/OCR NOT_CERTIFIED; PUBLIC_ONLY/HOST_UNISOLATED; 4K no garantiza 3 fuentes; límites Desktop native smoke/packaging documentados; V2 FAIL permanece. ([K][K], [D][D], [CAP][CAP], [INV][INV], [V2][V2]) | SATISFIED | — |
| 39. Active Web permanece fuera. | Active Web fuera del alcance; no añadir DOM/click/form/browser a acquisition/search. | Arquitectura explícita; K6/K7 passive provider/snippets/no result-page dispatch y contratos HEAD PASS. Sin cambios de acquisition/product en esta tarea. ([N][N], [W][W], [D][D], [H][H], [INV][INV]) | SATISFIED | — |
| 40. Manifest reproducible con hashes/evidence publicado. | Manifest/evidence reproducibles publicados con hashes, identidad/runtimes/corpus/ejecución y estados sin sobrescritura. | Manifests K0–K8/repairs/current HEAD/Desktop y freeze/index V2 existentes; esta auditoría publica matriz/evidence_index aditivos, SHA y pruebas focales reproducibles. Publicación de manifest no equivale a READY. ([K][K], [P][P], [Q][Q], [C][C], [W][W], [D][D], [S][S], [E][E], [R][R], [B][B], [H][H], [F][F], [V2][V2]) | SATISFIED | — |

Matriz machine-readable: [ready_criteria_matrix.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_audit/ready_criteria_matrix.json). Incluye los 40 enunciados exactos de §64, referencias y 41 pruebas/nodos PASS comprobados en el XML HEAD existente. Esos tests **no se reejecutaron** para la auditoría.

## 3. Reconciliación de calidad/performance

§49 conserva sus thresholds: parse success ≥98%; mapping/typing crítico=100%; lexical-supportable R@5≥90%, P@1≥85%; abstention≥95%; invalid accepted citations=0; admitted revision/locator y críticos=100%.

Las mediciones históricas citadas no se anuncian como nuevas mediciones: extraction K8 64/64 y typing 8/8; K4 96.226%/96.226% y 100% abstention; K8 lexical 100%/96.970%; V6 100%/100%/100%. Su aplicabilidad actual se apoya en identidad de componentes y en gates de quality/current regression realmente PASS en HEAD (K4, repair2, repair3 y V6). Extraction y sus repairs tienen cobertura productiva/parser/locator vigente. Citation structural validity se acredita mediante tests adversariales del registry, no por ausencia casual de citas malas.

`4K historical quality = 10/15` mide el requisito adicional de **admisión completa multi-source a 4K** de aquella evaluación; no revoca ni sustituye §49. Se conserva como FAIL de su gate histórico. Capability Resolution admite Knowledge=0 bajo el cap y no promete tres evidences completas en toda consulta 4K. Supplemental 8K aporta admisión operacional, **no** calidad de modelo.

§52 exige FTS p95≤100 ms sobre host/corpus aprobados, no una garantía universal para 100k chunks. K4 publicó 2.2483 ms y K8 2.3760 ms (1000 chunks/60 queries); el gate publicado vuelve a figurar PASS en HEAD current-regression. No se inventa un benchmark nuevo ni se requiere recertificar semantic/OCR.

## 4. Cobertura E2E obligatoria existente (§51)

| Cobertura normativa | Evidencia local real válida | Pendiente |
|---|---|---|
| attachment → answer | attachment-txt PASS original, valor + fuente/cita admitida | No |
| PDF → answer + citation | pdf-citation PASS, adquisición/extracción PDF real con página | No |
| DOCX → answer + citation | docx-citation PASS con parser/container real | No |
| JSON/code → answer | json-answer y code-answer PASS | No |
| workspace library multi-session | library-restart PASS; R2 y contratos current complementan scope, sin sustituir el LLM histórico | No |
| Memory + Knowledge coexistence | memory-plus-knowledge PASS, valor documental + preferencia Memory separada | No |
| URL fetch | url-fetch PASS con web_fetch/ToolResult/audit reales | No |
| web search si provider habilitado para campaña | Provider deshabilitado en campaña normativa preservada; condición no activada. K6 acredita contratos pasivos, no nueva calidad LLM de search | No ejecución adicional requerida por §51 |
| stale/superseded | update-current PASS, revisión nueva real y valor vigente | No |
| delete/no-resurrection | deleted-abstain PASS, más tombstone/rebuild/recovery contracts | No |
| prompt injection documentaria | document-injection PASS, valor seguro/cita y sin write/tool effects | No |
| source conflict | FAIL original. Regression scripted y supplemental 8K no son modelo real; V2 no ofrece cobertura exitosa válida | **Sí** |
| abstention | no-evidence, wrong-workspace, deleted-abstain PASS | No |

No se recalculan scores históricos ni se cambia source-conflict original a PASS. K8 V2 sigue FAIL; sus observaciones sirven al análisis contractual, no a su rescate.

## 5. Evidencia prospectiva mínima propuesta — NO EJECUTADA

**Una única prueba focalizada source-conflict E2E**, en una sesión nueva, con dos fuentes independientes sobre el mismo hecho y valores opacos incompatibles. Inputs/IDs/valores nuevos, sin reutilizar SABLE_ROUTE/NORTH/SOUTH ni los casos V2. Congelar su preparación, expectativa y parámetros antes de autorizar la inferencia.

- Recorrido normal productivo host import → retrieval real → admission real → modelo local real → respuesta/citations/effects → evidencia.
- Un único perfil operacional **8192**, ya aceptado, con el artefacto exacto qwen3.5:9b/digest `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`, Ollama, temperature=0, think=false, maxIterations=6 y seed=NOT_SUPPORTED. No nueva campaña 4K/8K ni tuning.
- Petición comparativa explícita dentro del contrato soportado, sin preselección oculta de evidence ni cambios de retrieval/floor. No exigir cross-lingual, arbitrariedad multi-tema o interpretación lingüística r1/r2.
- Verificar ambas fuentes/revisiones/chunks realmente recuperados y admitidos. Respuesta conserva ambos valores, los atribuye a su origen y presenta el conflicto sin elegir uno como verdad sin soporte; dos citas distintas, estructuralmente válidas y con provenance correcta. Respuesta natural válida: **V1 no exige el JSON de V2**.
- Conservar request/context exactos, respuesta, registry/citas inválidas, source lifecycle, Files/Memory before/after y ToolRuntime/authority separados por R1. Fixture conforme R2. Identidad/pins antes/después, output fresco y sin sobrescritura.
- Un intento planificado; un FAIL se conserva y se diagnostica, no se repara/repite automáticamente. Incidentes de ejecución se registran aparte, sin convertir calidad en incidente.

Si pasa, aportaría la evidencia hoy ausente para el **criterio 35** y permitiría una resolución documental separada del **criterio 1**, conservando todos los labels históricos. Después se comprobaría integridad y se publicaría el cierre aditivo contra la matriz; no hace falta repetir 35 casos, ni otro benchmark general, ni nueva revisión V2. Si falla, no hay READY y no se presupone por adelantado una reparación de Nova.

## 6. Estados y detención

Permanecen literalmente:

- `K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14`
- `K8 POST-CERT REMEDIATION PARTIAL`
- `4K historical quality = 10/15`
- `KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS`
- `K8 CERTIFICATION V2 FAIL`

Ledger V2 intacto: campaigns_consumed=2; inference=76; retrieval=32; admission=32. Incrementos **V2** en esta tarea=0 en los cuatro contadores. La actividad SQLite focal (11 retrievals, 6 imports en desarrollo+final) está separada y no se oculta bajo un falso retrieval global=0.

No se ha ejecutado nueva evidencia con modelo, modificado producto/corpus/gold/scorer/prompts/freezes ni creado autorización nueva. No READY, V2-R5, campaña nueva, conversación/contexto nuevo, commit, push ni tag. **Detenido para revisión humana.**

## Referencias e integridad

- N: [NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md)
- K: [k0_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k0_resultados.md); [k1_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k1_resultados.md); [k2_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k2_resultados.md); [k3_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k3_resultados.md); [k4_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k4_resultados.md); [k5_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k5_resultados.md); [k6_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k6_resultados.md); [k7_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k7_resultados.md); [k8_final_campaign_closure.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_final_campaign_closure.md)
- P: [k3_pdf_repair_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k3_pdf_repair_resultados.md); [k3_pdf_repair_manifest.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k3_pdf_repair_manifest.json)
- Q: [k4_resume_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k4_resume_resultados.md); [quality_final.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k4_resume_evidence/quality_final.json); [performance_final.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k4_resume_evidence/performance_final.json)
- C: [k5_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k5_resultados.md); [budget_matrix.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k5_evidence/budget_matrix.json); [persisted_citations.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k5_evidence/persisted_citations.json)
- W: [k6_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k6_resultados.md); [k6_manifest.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k6_manifest.json)
- D: [k7_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k7_resultados.md); [k7_manifest.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k7_manifest.json)
- S: [k8_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_resultados.md); [standalone_result_v1.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_evidence/standalone_result_v1.json); [k8_manifest.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_manifest.json)
- E: [k8_final_execution_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_final_execution_resultados.md); [k8_final_execution_manifest.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_final_execution_manifest.json); [k8_final_campaign_closure_manifest.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_final_campaign_closure_manifest.json)
- R: [k8_repair6_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_repair6_resultados.md); [final_regression_v1.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_repair6_evidence/final_regression_v1.json)
- B: [k8_post_cert_conflict_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_post_cert_conflict_resultados.md); [k8_post_cert_supplemental_8k_resultados.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_post_cert_supplemental_8k_resultados.md)
- CAP: [NOVA_KNOWLEDGE_CONTEXT_CAPABILITY_RESOLUTION_V1.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/architecture/NOVA_KNOWLEDGE_CONTEXT_CAPABILITY_RESOLUTION_V1.md); [knowledge_context_capability_resolution_v1_head_cierre.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/knowledge_context_capability_resolution_v1_head_cierre.md)
- H: [knowledge_context_capability_resolution_v1_head_evidence.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/knowledge_context_capability_resolution_v1_head_evidence.json); [tests.xml](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/knowledge_context_capability_resolution_v1_head_evidence/tests.xml); [head-closure-evidence.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/knowledge_context_capability_resolution_v1_head_evidence/head-closure-evidence.json); [selection.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/knowledge_context_capability_resolution_v1_head_evidence/selection.json)
- INV: [RECONCILIACION_CONTRACTUAL_FINAL_K8_V2_V1.md](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v2/reconciliation/RECONCILIACION_CONTRACTUAL_FINAL_K8_V2_V1.md)
- F: [run.json](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/focused-harness/r1-r2-20261009T040413Z-48a6a06a25cd447999922d54262863de/run.json); [tests.xml](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/focused-harness/r1-r2-20261009T040413Z-48a6a06a25cd447999922d54262863de/tests.xml); [tests.log](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/focused-harness/r1-r2-20261009T040413Z-48a6a06a25cd447999922d54262863de/tests.log); [evidence_index.json](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/focused-harness/r1-r2-20261009T040413Z-48a6a06a25cd447999922d54262863de/evidence_index.json); [preservation_after.json](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/focused-harness/r1-r2-20261009T040413Z-48a6a06a25cd447999922d54262863de/preservation_after.json)
- V2: [freeze_final_v2_r4.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v2/revision_04/freeze_final_v2_r4.json); [execution_summary.json](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/execution_summary.json)

Índice aditivo con SHA, verificaciones y referencias raw: [evidence_index.json](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/ready_audit/evidence_index.json). Conserva también los intentos de desarrollo, sin sustituir índices históricos.

[N]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md
[K]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k0_resultados.md
[P]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k3_pdf_repair_resultados.md
[Q]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k4_resume_resultados.md
[C]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k5_resultados.md
[W]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k6_resultados.md
[D]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k7_resultados.md
[S]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_resultados.md
[E]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_final_execution_resultados.md
[R]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_repair6_resultados.md
[B]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/k8_post_cert_conflict_resultados.md
[CAP]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/architecture/NOVA_KNOWLEDGE_CONTEXT_CAPABILITY_RESOLUTION_V1.md
[H]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/knowledge_context_capability_resolution_v1_head_evidence.json
[INV]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v2/reconciliation/RECONCILIACION_CONTRACTUAL_FINAL_K8_V2_V1.md
[F]: C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/focused-harness/r1-r2-20261009T040413Z-48a6a06a25cd447999922d54262863de/run.json
[V2]: C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v2/revision_04/freeze_final_v2_r4.json

