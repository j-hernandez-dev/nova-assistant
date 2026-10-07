# Evaluación normativa final — NOVA_MEMORY_V1_READY

Fecha: 2026-10-07. Fuente normativa: [NOVA_MEMORY_ARQUITECTURA_V1.md §38](../architecture/NOVA_MEMORY_ARQUITECTURA_V1.md), con MEM1-OD-08 (§36), Gate M8 (§37), INV-041–044 (§35) y límites de §43.

```text
NOVA_MEMORY_V1_READY
MEMORY_CORE = READY
SEMANTIC_PROFILE = NOT_CERTIFIED
```

**25/25 criterios de §38: PASS para el alcance Core aplicable.** La certificación adicional de Semantic Profile no aplica a esta declaración. Sus fallos históricos no desaparecen ni se convierten en PASS/UNAVAILABLE/NOT_EVALUATED.

Esta es una evaluación de evidencia, no una fase de implementación. Sólo se crean este informe y [su manifest](memory_v1_ready_manifest.json). Sin cambios de producto, arquitectura, SECURITY, CI, thresholds, datasets o gold; sin inferencia, llamadas Ollama, descarga, commit, push o tags.

## 1. Baseline congelado y preservación

- Branch: `main`.
- HEAD: `468d213ede2fa52f6b2588ebaa1191b83669ccb8` (`ci: align unsupported filesystem gates across platforms`).
- Working tree inicial: **dirty heredado**, 26 archivos tracked modificados, además de archivos/directorios untracked de MEMORY/context64. Índice sin cambios staged. El detalle tracked y las áreas untracked figuran en el manifest. HEAD por sí solo **no** identifica el producto evaluado.
- Tag Core: `nova-core-v1-stable`, ref `97f41c6dab89ee59332875bb8d89c29620b52156`, commit `158b60effa484cd34a58b991f3ee4ca3f808d924`.
- Tag SECURITY: `nova-security-v1.2-ready`, ref `e5bea6a4c2c559a1f5a2f8824316a83b548b2533`, commit `26dc87786d8ad1c1d879255a068c7fb50a25e6f2`.
- Ambos commits son ancestros de HEAD. `core/contracts.py` y `core/runtime.py` no presentan diferencias respecto al tag Core; runtime/AgentLoop/harness y superficies SECURITY seleccionadas no presentan diferencias respecto al tag SECURITY. Las extensiones ya aprobadas de contexto/MEMORY se identifican por el freeze M8; **no** se afirma igualdad byte a byte de todo Core con el tag antiguo.
- Plataforma de certificación MEMORY: **Windows 11 build 26200 + local NTFS + HOST_UNISOLATED**. No sandbox ni process isolation. No nueva certificación MEMORY de Linux/macOS ni certificación universal de hardware mínimo.

SHA-256 de arquitectura normativa vigente:

`886a4788d55282aefbbc776344ec507b779519e15ea940dcad62ea24ef57e9cd`

Se verificaron, antes del cierre:

| Inventario con hashes previamente registrados | Comprobación |
|---|---:|
| Código/protocolo del freeze M8 Core |442/442 coinciden|
| Artefactos históricos protegidos M0–M8 |556/556 coinciden|
| Artefactos SECURITY/arquitectura en pins de SECURITY READY |953/953 coinciden|
| Superficies seleccionadas SECURITY, incluida arquitectura |32/32 coinciden|
| Freeze, sidecar, protocolo, standalone, E2E y assessment crítico frente al manifest M8 Core |todos coinciden|

[Freeze M8 Core](m8_core_evidence/core_freeze_v1.json):
`07c6f2afbf1fb0afa99034c8b2c16fac8c71ba561ff7ef544165bb4858135113`.

El manifest nuevo registra referencias directas y sus hashes, además de las referencias transitivas a los inventarios completos anteriores. Distingue `PRESERVED_EXPECTED_PIN` de `READY_PREFLIGHT_CAPTURE`: para artefactos que no tenían un hash previo registrado, el hash se captura ahora; no se inventa una comprobación retrospectiva.

No se limpió, restauró ni revirtió el working tree. La corrección histórica del índice descrita en el diagnóstico M8 permanece histórica; no se repitió aquí.

## 2. Método y evidencia reutilizada

[O] Lectura de los contratos normativos, implementación pertinente, manifests, hashes, prompts sintéticos preservados y JUnit. [T] Pruebas **ya ejecutadas** y preservadas por las fases. La verificación actual sólo recalcula integridad/coherencia sobre esos resultados; no ejecuta nuevamente tests, modelos o efectos de producto. Ningún PASS se basa exclusivamente en intención arquitectónica.

Referencias de la matriz:

- **E-P**: [manifests M0](m0_manifest.json), [M1](m1_manifest.json), [M2](m2_manifest.json), [M3](m3_manifest.json), [M4](m4_manifest.json), [M5](m5_manifest.json), [M6](m6_manifest.json), [M7](m7_manifest.json), [M8 Core](m8_core_manifest.json).
- **E-M**: [JUnit final MEMORY](m8_core_evidence/final_memory_20261007/tests.xml) y [comando/runtime](m8_core_evidence/final_memory_20261007/run.json): **782 PASS / 0 FAIL / 0 skips**. El manifest READY vincula cada prueba citada a su módulo y cantidad de instancias PASS ejecutadas.
- **E-H**: [JUnit HEAD aislado](m8_core_evidence/final_head_isolated_20261007/tests.xml) y [comando](m8_core_evidence/final_head_isolated_20261007/run.json): **4138 PASS / 0 FAIL / 11 skips previos / 53 subtests PASS**. Incluye **392 pruebas Core PASS** (4 skips Core previos) y **615 pruebas SECURITY PASS**.
- **E-S**: [SECURITY READY](../security_v12/nova_security_v12_ready_manifest.json), S0–S8, y evidencia host-real Windows/NTFS allí referenciada. 20/20 criterios SECURITY acreditados en su cierre; hashes históricos verificados. No se repitió host-real.
- **E-R**: [standalone Core](m8_core_evidence/standalone_v1/report.json): exact/FTS/SQLite reales, sin inferencia.
- **E-E**: [E2E Core](m8_core_evidence/e2e_v1/report.json), sus source reports, observations JSONL y prompts reales.
- **E-C**: [campaña crítica](m8_core_evidence/critical_v1/report.json) y [assessment contractual](m8_core_evidence/critical_gate_v1.json): 30/30.
- **E-A**: [sidecar](m8_core_evidence/protocol_v1/annotation_v1.json), [protocolo](m8_core_evidence/protocol_v1/core_protocol_v1.json), [independencia de outcomes](m8_core_evidence/protocol_v1/outcome_independence.json).
- **E-D**: [Desktop](m8_core_evidence/desktop_regression.json): **40 PASS**, contratos nativos Node; no nuevo E2E gráfico Electron.

Se reconstruyeron las anotaciones desde las fuentes y se comparó su representación JSON canónica con el protocolo congelado. Se recalcularon los scores standalone y los E2E **desde IDs, respuestas y cápsulas preservados**, aplicando el scorer congelado; se verificaron los 330 prompts del corpus completo y los 30 escenarios críticos. No es otra campaña de calidad ni inferencia nueva.

Una primera comparación auxiliar Python detectó listas de tuples frente a arrays JSON en `sourceCorpora`; la comparación canónica demostró igualdad exacta. Fue un error del comparador de auditoría, no drift del protocolo ni un fallo de producto; no cambió ningún artefacto/assertion normativo.

## 3. Matriz literal de los 25 criterios de §38

Los nombres `test_…` corresponden a pruebas ejecutadas en E-M/E-H; no sólo a archivos existentes. La tabla distingue contratos con doubles de calidad LLM real.

| §38 | Criterio vigente | Evidencia concreta | Resultado | Justificación / límite |
|---|---|---|---|---|
|1|M0–M8 están cerrados.|E-P; hashes esperados de los manifests; M5_CORE y cierre prospectivo M8 Core bajo OD-08.|PASS|M0–M7 PASS; M8 CORE PASS. El manifest histórico M8 PARTIAL/campañas FAIL permanece intacto; no certifica el perfil semántico actual.|
|2|Core V1 y SECURITY V1.2 continúan verdes.|E-H, E-S; ancestry/tags; 32 pins SECURITY; contratos/AST, lifecycle y smokes del gate HEAD.|PASS|392 Core y 615 SECURITY PASS en regresión final aplicable; 0 FAIL HEAD. No se sustituye host-real por mocks ni se recertifican plataformas ajenas al alcance.|
|3|MemoryStore está versionado/migrable y recovery probado.|E-M: `test_native_sqlite_version_pragmas_owned_tables_and_ports`, `test_migration_v0_copy_explicit_idempotent_and_original_unchanged`, migrations fallidas y crashes nativos insert/update/supersede/delete.|PASS|Formato/schema identificados; rollback/migration explícita; reopen conserva ACK y no inventa writes no committed. Crash de proceso real, no certificación de power-loss/hardware.|
|4|subject/workspace scopes son explícitos y probados.|E-M: `test_filters_before_limit_scope_subject_sensitive_kind_and_time`, `test_workspace_scope_and_global_selection_do_not_cross_leak`, UI no forja identidad; E-C isolation.|PASS|Subject durable no equivale a sessionId; filtros antes de ranking/límite; acceso/mutación cross-scope denegados.|
|5|user correction/forget funcionan y no resucitan índices.|E-M: correction/lineage/CAS, `test_restart_correction_forget_rebuild_no_future_capsule_resurrection`, atomic delete; E-C correction/delete.|PASS|Supersession y tombstones gobiernan FTS/vector/caches; reopen/rebuild no reactiva versiones borradas.|
|6|secret-deny/sensitive policy está activa.|E-M: `test_known_secret_and_obvious_credentials_denied_before_write`, consentimiento sensible exacto, `test_sensitive_or_injection_not_escrowed`; E-C secret.|PASS|Cero writes de secretos en fixtures; sensitive no auto-write, consentimiento y redaction. No detector universal de toda sensibilidad/secreto.|
|7|lexical memory funciona sin embeddings.|E-R, E-E; E-M: `test_case_preserved_normalized_dedup_no_embeddings_required`, reapertura/recall normal.|PASS|Stores/FTS reales; exact/lexical/none y embeddings DISABLED durante certificación Core; ningún modelo de embeddings requerido.|
|8|semantic/hybrid implementation y contratos de spaces/security/degradación existen y están probados; sólo se anuncia Semantic Profile CERTIFIED con sus benchmarks/E2E reales superados. No certificado no invalida READY Core conforme a OD-08.|M5_CORE; E-M: no load/download, capability detection, cold/chat denied, typed fallback, timeout/BUSY/recovery; E-A/OD-08.|PASS|Implementación y contratos PASS con fixtures/doubles declarados. Certificación adicional: NOT_APPLICABLE a esta declaración, **NOT_CERTIFIED**, no PASS de calidad real.|
|9|embedding spaces están versionados y no se mezclan.|E-M: digest crea espacio nuevo, wrong-space same-dimension denied, revisión/dimensión/post-validation; metadatos de campañas preservados.|PASS|No reuse/reinterpretación de vectores incompatibles; no publicación de vector si falla prueba posterior. No se anuncia un espacio certificado.|
|10|MemoryCapsule respeta presupuesto numérico N: targets 4K/8K/16K y capacidades avanzadas soportadas 32K/64K, con el mismo hard ceiling.|E-M: matriz numérica M4 35 combinaciones, 5 ceilings, 5 admissions M8; E-E budgets.|PASS|N=4096/8192/16384/32768/65536; memoria ≤min(8% N,1024), ≤8 items y reservas Core. 32K/64K son contratos sintéticos de budgeting, no certificación LLM real.|
|11|current user message no se sacrifica para memoria.|E-M: `test_optional_zero_and_intrinsically_impossible_input_is_core_error`, historial 10k/current priority; E-E prompt/budget.|PASS|Input actual íntegro; memoria opcional puede ser 0. Input intrínsecamente imposible produce error Core, no truncamiento oculto.|
|12|MEMORY + RAG respetan cap compartido.|E-M: `test_shared_soft_share_borrow_and_nonadditive_retrieval` en 5 ventanas y `test_rag_separate_service_shared_retrieval_budget_and_no_memory_write` ON/OFF.|PASS|Cap combinado, no presupuestos aditivos; RAG sigue Knowledge/data, no auto-write de memoria personal.|
|13|retrieval principal no se repite por Generation.|E-M: M4 first prompt/restart con 2 generations/ToolResult real y 1 recall; M5 query once; M7 historial10k.|PASS|Snapshot por Turn; generaciones sólo revalidan IDs/revisiones acotados. Providers/embeddings de esas pruebas son doubles contractuales, no calidad semantic real.|
|14|no LLM reranker pesado es requisito del critical path.|[O] `memory_recall.py` / `memory_semantic.py`: exact/FTS y fusión determinista, sin chat-reranker; E-R/E-E lexical y E-M M5 two-generation/query-once.|PASS|Retrieval no requiere inferencia chat adicional ni reranker pesado; la llamada chat del E2E responde, no reranquea.|
|15|auto-extraction no bloquea el primer response.|[O] `session.py`: queue después de publicar terminal y `turn.done.set()`; E-M: post-terminal/new-turn-preempts, extractor bloqueado controladamente.|PASS|Maintenance tiene operación separada; foreground/primer response no espera extracción ni se reabre el Turn terminal.|
|16|extractor no escribe directamente.|[O] `MemoryExtractionPort` y adapter sólo retornan payload no confiable; E-M: literal-span/schema, `test_untrusted_schema_not_authority`, confirmación humana exacta.|PASS|Application/WritePolicy validan y hacen commit; extractor no recibe store ni decide scope/authority/consent.|
|17|assistant/tool/subagent no puede auto-globalizar memoria sin policy.|E-M: `test_non_user_never_auto_or_global` (3 clases), assistant hallucination y child proposal/confirmación.|PASS|Propuestas WORKSPACE, accepted=0 antes de confirmación; no confidence LLM como autorización.|
|18|subagent access está acotado.|E-M: delegated subset/relevance/revision/no-global-query, forged scope/grant denied, child loop normal local/remote.|PASS|Cápsula delegada/atenuada, sin acceso global a store/commit/delete; una sesión principal y ruta ToolRuntime común.|
|19|remote memory injection es opt-in.|E-M: `test_remote_injection_requires_host_opt_in_and_visible_metadata` ON/OFF, config default false, child remote denied.|PASS|Denegación tipada por default y estado visible. Provider remoto scripted sólo para contrato, sin llamadas cloud.|
|20|delete/no-resurrection está probado.|E-M: M2 owned projections+tombstones/rebuild/crash, M5 external delete, M6 pending drafts/content; E-C delete/reopen.|PASS|No reaparición en FTS/vector/snapshot/propuestas. No claim de borrar transcript histórico, Security Audit, backups o fuentes externas.|
|21|poisoning/instruction-like memory no obtiene autoridad system.|E-M: quoted user-data/wrappers, invalid system capsule excluded, poisoned memory + ToolRuntime deniega file://; E-C poison/authority.|PASS|Memoria no emite grants ni aprobación, ni eleva ceiling. Cero bypass en campaña/contratos; no garantía universal de inmunidad LLM.|
|22|el corpus completo y sidecar Core/Semantic versionado cubren updates/temporal/abstention/multi-session; el corpus Core tiene tamaño/provenance/denominadores OD-08 demostrados.|E-A: 3 fuentes/SHA, 110 normales, 75 Core (57 positivos/18 negativos), 53 hechos únicos; 10 escenarios Core críticos/temporales aparte; E-C/M6.|PASS|Todos los casos preservados; reglas deterministas sin outcomes; sidecar anota también contratos/cross-session/correction/expired/conflict. Críticos no inflan ranking normal.|
|23|un modelo local real apropiado supera MEMORY_CORE_QUALITY E2E4K/8K/16K sin cloud; certificar Semantic Profile exige su E2E adicional.|E-E qwen3.5:9b real sobre backend normal, prompts/IDs/cápsulas; scorer congelado recalculado.|PASS|74/75,75/75,74/75 superan85/90/90%; guesses/transcript-only no cuentan. E2E semantic adicional NOT_APPLICABLE aquí; no certificado.|
|24|latencia/context cost cumplen los umbrales del perfil certificado y los contratos obligatorios de degradación.|E-R p95lexical3,312ms≤50; E-E p95retrieval3,397/3,922/5,305ms, cápsula≤304 tokens; E-M deadline/cutoff/late/BUSY/recovery/budget.|PASS|soft350/hard600/guard50 intactos; no vector tardío/incompatible en snapshot. Warm hybrid quality/performance no se certifica. Hard es contrato del critical path, no garantía realtime OS/full Turn/chat.|
|25|READY publica alcance Core, estado de Semantic Profile, limitaciones, degradaciones y resultados históricos sin reinterpretación.|Este informe y manifest; E-P/E-A; inventarios con hashes y sección histórica abajo.|PASS|Claims limitados, fallos/model behavior preservados, semantic NOT_CERTIFIED explícito. Sin avance a otra fase.|

**Ningún criterio obligatorio queda FAIL/UNKNOWN.** NOT_APPLICABLE corresponde sólo a la certificación condicional semantic adicional en los criterios 8/23/24; no exime sus contratos ni los invariantes críticos Core.

## 4. Métricas y alcance de los tests

| Evidencia reutilizada | Resultado |
|---|---|
|Standalone Core R@3|56/57 =98,25% (≥85%)|
|Standalone Core P@1|55/57 =96,49% (≥90%)|
|Exact retrieval contractual|18/18 =100%|
|Lexical p95, 110 queries completas|3,312ms (≤50ms), max4,657ms|
|E2E4K|74/75 =98,67% (≥85%); positivos56/57; negativos18/18|
|E2E8K|75/75 =100% (≥90%); positivos57/57; negativos18/18|
|E2E16K|74/75 =98,67% (≥90%); positivos56/57; negativos18/18|
|Abstención ordinaria|54/54 =100% (≥95%)|
|Escenarios críticos local LLM|30/30 =100%; contratos de subject/sensitivity/etc además en E-M|
|Contexto|5 ventanas contractuales; máximo MEMORY E2E304 tokens; presupuesto numérico y reservas verificadas|
|MEMORY / HEAD / Desktop|782 / 4138 (+53 subtests,11 skips previos) /40 PASS; 0 FAIL finales|

E-M/E-H incluyen unit/contract con doubles declarados, integration con stores/FTS/NumPy reales y crashes de procesos nativos sobre fixtures sintéticos. E-E/E-C son **LLM local real**, no scripted/cloud. E-D son contratos Node, no E2E gráfico nuevo. S3 host-real proviene de E-S, incluido cierre manual válido de symlinks; la evidencia histórica WinError1314 no se altera.

No se hicieron reruns masivos ni verificaciones de producto adicionales: **tests adicionales=0; inferencias adicionales=0**. Sólo integridad, parsing JUnit, reconstrucción canónica de protocolo y revaloración de resultados congelados.

Los 11 skips y exclusiones S0/legacy/host-real separados son los [ya documentados](m8_core_evidence/unchanged_skips.json). No se añadieron skips/xfail ni se reintrodujo baseline histórico al gate HEAD.

La primera corrida HEAD en fixtures dentro del repositorio sigue en [su diagnóstico](m8_core_evidence/head_isolation_diagnostic.json): 6 fallos HARNESS_BUG preservados. La corrida aislada usa el mismo producto/runtime/assertions/selección con estado privado fuera de Git. No se presenta la corrida fallida como PASS. Igualmente se conserva la invocación Node strip-only fallida antes del comando correcto con transform-types.

## 5. Modelo/host y límites de rendimiento

Certificación E2E: Ollama0.40.0, `qwen3.5:9b`, Q4_K_M/llamacpp, digest
`c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`;
temperature0, think=false, num_predict128, num_ctx=N. Evidencia de identidad pre/post preservada; no se consulta Ollama nuevamente.

Windows11 build26200; CPU Intel Core Ultra7 155H; RAM física observada15,48GiB. GPU efectiva de inferencia **UNKNOWN**: enumerar adapters o size_vram no identifica offload real. No se modificó GPU/global config.

Conteo de contexto E2E: estimación Core UTF-8 bytes/3 con overhead, **no tokenizer exacto del modelo**. Los caps/reservas se verifican según ese contrato; no es una medición física exacta de tokens procesados por cada backend.

Deadline semántico: soft350/hard600ms, guard interno50ms y cutoff550ms. Contratos de abandono, retorno lexical, BUSY, recovery e inmutabilidad PASS; no garantía absoluta de scheduling OS ni de respuesta chat completa en600ms. Ningún nuevo benchmark semántico se usa para certificar el perfil.

Defaults de capacidad previamente validados M8:20.000 activos /512MiB, soft limits independientes; checkpoint/maintenance seguro antes de decidir size capacity, pause AUTO_SAFE, correction/forget conservados, no purge estable automático. No cuotas OS.

## 6. Historia inmutable y perfiles no certificados

| Evidencia histórica | Estado conservado |
|---|---|
|Benchmark general lexical M8 original|57,14% FAIL en4K/8K/16K; no recalculado/reinterpretado como PASS|
|Qwen3-Embedding0.6B|quality FAIL, incluidas campañas/query-document; candidato cerrado|
|BGE-M3 final inicial|standalone FAIL, semantic quality NOT_EVALUATED por0/72 WARM; scores de fallback lexical|
|BGE VALIDITY_REPAIR|hybrid quality FAIL: R@3=88,33%,P@1=68,33%;72/72 WARM. No atribución causal nueva a embedding/RRF|
|Forense BGE sin inferencia|PARTIAL por ausencia de pre-fusion evidence preservada; no se inventa atribución|
|Qwen3-Embedding4B, chat9B y repetición chat7B|operational FAIL por disponibilidad/residencia; quality no ejecutada|
|Qwen3-Embedding8B/M5|evidencia real histórica M5 preservada; no equivale a certificación actual de Semantic Profile|
|Qwen2.5:7b single-Turn multi-tool Core/SECURITY|MODEL_BEHAVIOR histórico, limitación no bloqueante; no fallo reetiquetado|

El corpus Core OD-08 no pretende ser un HELD-OUT nuevo ni una demostración universal. Global lexical actual sobre las110 queries:79/110,80/110,79/110;35 casos Semantic conservados con observación lexical5/35 por ventana, **informativa**. Para el perfil no certificado siguen NOT_EVALUATED en la campaña Core; eso no modifica los FAIL de campañas semánticas realmente evaluadas.

## 7. Qué certifica READY y qué no

Certifica **MEMORY Core local**, con exact/lexical y persistencia multi-session; identity/scope por subject/workspace; correction/supersession; forget/delete/no-resurrection; conflictos/temporalidad; políticas de secretos/sensibilidad; MemoryCapsule acotado/user-first; RAG con cap compartido; delegación acotada; integración local normal E2E4K/8K/16K sobre el modelo/host publicado y degradación segura si semantic no está certificado/disponible.

No certifica:

- memoria perfecta, verdad garantizada o detección universal de secretos/sensibilidad;
- Semantic Profile, recall semantic/cross-language garantizado o un modelo embedding recomendado;
- cifrado universal/secure erase de discos, backups, audit o fuentes externas;
- sandbox, process isolation o protección del store frente a procesos con autoridad de la misma cuenta;
- igual calidad en todos los modelos/hardware, ni un minimum hardware universal;
- inferencia LLM real certificada32K/64K; sólo contratos de budgeting avanzados;
- MEMORY/S3 host-real Linux/macOS por extensión de una corrida Windows.

Se conservan los misses de ranking `heldout-learning`/#2 y `heldout-receipt`/#4, y las dos respuestas `UNKNOWN` de `heldout-parcel` en4K/16K con el recuerdo correcto en cápsula: fallos por caso, **no retries ni guesses contados**. Exact retrieval18/18 no significa exact answer infalible (17/18,18/18,17/18).

Retención física EPISODE (OD-05) y cifrado opcional (OD-06) permanecen diferidos; no se cierran decisiones futuras. No queda un requisito obligatorio de §38 sin demostrar.

## 8. Comprobación reproducible de este cierre

Los comandos históricos exactos están en los run.json E-M/E-H y en los manifests de cada fase. **No se repiten en esta evaluación.**

La comprobación actual, sólo lectura, comprende:

1. `git branch --show-current`, `git rev-parse HEAD`, `git status --short --untracked-files=no`, `git diff --cached --name-only`.
2. Resolver refs/commits de los tags y `git merge-base --is-ancestor <tag> HEAD`.
3. SHA-256 de cada entrada `files`/`protectedHistoricalEvidence` en el freeze M8 y de los pins históricos SECURITY utilizados; comparar con sus expected hashes.
4. Reconstruir `m8_core_protocol.build_annotation/build_protocol` desde fixtures originales; comparar JSON canónico/thresholds con sidecar/protocolo congelados.
5. Aplicar únicamente `m8_evaluation.score/aggregate`, `m8_core_protocol.supported_answer/quality_gate` y `run_m8_core_certification.critical_gate` a resultados ya preservados; no llamar create/seed/standalone/e2e/verify_chat.
6. Parsear JUnit y confirmar que cada nombre de prueba contractual de la matriz tiene instancias PASS ejecutadas, no skips.
7. Verificar referencias del manifest nuevo, 25 filas sin bloqueadores y preservación final de baseline/hashes.

El manifest contiene los resultados de estas comprobaciones, hashes y trazabilidad por criterio. Su inventario directo permite comprobarlo sin acceder a conversaciones reales o secretos.

**Resultado final: NOVA_MEMORY_V1_READY — únicamente MEMORY Core en el alcance publicado.** No se crea M9 ni se ejecuta una fase posterior.

