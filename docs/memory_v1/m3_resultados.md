# MEMORY V1 — cierre de M3

Estado: **M3 = PASS**. Fecha: 2026-10-06.

Alcance exclusivo: **M3 — User control + explicit remember/correct/forget**, MEMORY V1 §37. El usuario puede crear, inspeccionar, corregir y olvidar recuerdos sin extractor LLM. **No se ha implementado M4 ni declarado NOVA_MEMORY_V1_READY.**

## 1. Baseline y preflight

Branch `main`; HEAD inicial/final `468d213ede2fa52f6b2588ebaa1191b83669ccb8` (`ci: align unsupported filesystem gates across platforms`). Tags relevantes preexistentes: `nova-core-v1-stable`, `nova-security-v1.2-ready`; no creados/movidos.

Nova 0.12.6; Python 3.14.6; SQLite 3.50.4; Node 24.16.0. Host comprobado: Windows 11 build 26200, NTFS local, `HOST_UNISOLATED`. No sandbox ni process isolation. Linux/macOS no ejecutados ni certificados por este cierre.

Working tree inicialmente dirty: M0/M1/M2 y 64K existentes sin commit. Ocho modificaciones tracked previas: `desktop/tests/application_client.test.cjs`, los documentos Core/contexto, `local_cli/cli.py`, `local_cli/config.py`, `local_cli/core/context.py` y los dos tests phase9 context/integration. También eran preexistentes los cuatro documentos, `docs/memory_v1/`, `docs/context64/`, Core MEMORY, admission, SQLite/codec/migrations, fixtures y tests MEMORY.

Se inspeccionaron las definiciones normativas §12/14/16/24/25/29/30/34–37/41, Core/Security y la auditoría. Precedencia: Core para lifecycle/contexto/API; SECURITY para autoridad/tools/secrets/audit; MEMORY para su extensión; auditoría sólo como evidencia. No quedó conflicto normativo pendiente. La prohibición de wiring propia de M1 no prevalece sobre los controles explícitos exigidos por M3.

Regresión nativa inicial: **3.705 passed + 53 subtests passed, 11 skips, 0 failures**. La primera corrida restringida tuvo siete fallos de permisos/contratos OS; se conserva íntegra y no se transformó en skip/xfail. La repetición nativa demostró el baseline real.

Preservación: **267 archivos capturados en preflight; 253 idénticos y 14 solapamientos necesarios para M3**. Es un muestreo declarado, no un hash previo universal del repo. Documentos normativos, evidencia M0/M1/M2/64K, CI, policies/grants/brokers/launcher/redactor/audit SECURITY y contexto/config permanecen intactos respecto al inicio. CLI conserva su cambio 64K previo y añade solamente la ruta MEMORY. Véase [preservation.json](m3_evidence/preservation.json).

## 2. Contrato interpretado

**Objetivo:** memoria útil bajo control explícito del usuario, todavía sin extracción automática.

Prerrequisitos comprobados: M0/taxonomía, M1/tipos-identidad-provenance, M2/SQLite-FTS-migrations existentes y passing en el working tree real; no se atribuyen al HEAD committeado.

**MUST:** MemoryService Application; ocho controles equivalentes a §25; CLI mínima y contrato Desktop compartido; identidad/scope del host; provenance; sensibilidad básica; explicit NORMAL sin confirmación redundante; SECRET_DENIED rechazado; SENSITIVE con consentimiento de la acción; correction/supersession y revision CAS; forget de proyecciones propias; export versionado/read-only; resultado observable; audit/eventos sin canonicalText por default; terminal Core único.

**MUST NOT:** writes autoritativos por LLM/UI serializando identidad o grants; segundo AgentLoop/sesión; bypass de tools/Security; RAG como memoria personal; secretos deliberados; inferir aislamiento/encryption/secure erase; ampliar scope por cwd; implementar recall al prompt, capsules, budgeting MEMORY, embeddings, auto-capture, semantic consolidation o mantenimiento de M4+.

Decisiones estructurales ya resueltas aplicadas: MEM1-AD-01/02/03/04/09/10/12/13/14/15. Ninguna OPEN DECISION futura se resolvió arbitrariamente.

## 3. Entregables y evidencia del Gate M3

| Requisito | Componente | Test/evidencia |
|---|---|---|
| MemoryService / ocho controles | Application `memory.py`; coordinator único | service/application/composition |
| Remember → restart → record exists | SQLite M2 + lazy factory normal CLI/server | reopen de service/Application y dos composition roots sobre state privado |
| Inspect/list/search/show | DTO metadata/provenance; FTS/exact acotado | cinco kinds, Unicode, source/time/scope/explicit/status/lineage |
| Correction supersedes | old SUPERSEDED; nuevo ACTIVE con supersedesMemoryId | corrección, stale revision, búsqueda excluye valor anterior; contrato Desktop→Application real |
| Workspace no leak | sujeto durable distinto de SessionId; scope resuelto desde workspace del host | aislamiento, rebind, Global explícito, provider/model change, denial de IDs ajenos |
| Dedup/conflicto básico | exact key → exact content; source adicional, no truth boost; ausencia CAS transaccional | repetición, ambigüedad sin LWW, intercalación de dos conexiones reales |
| Forget | M2 delete/tombstone/FTS/derived invalidation | no retorno tras rebuild/reopen; receipts sin contenido; no sources/audit/backups erase |
| Export | port / snapshot `nova-memory-export` v1 | scope-bound, SENSITIVE excluido por default, total_changes invariado al export |
| Basic sensitivity | WritePolicy explícita + redactor S6 inyectado | known secrets, nombres/assignments de credenciales, JSON/Bearer/password, consentimiento sensible y no declassification |
| CLI mínima | `/memory` → CliApplicationClient → coordinator | parser/handler real, sin SubmitUserInput ni inference ni transcript append |
| Desktop adapter contract | preload IPC / Main / signed MemoryControl / JSONL → mismo coordinator | 8 contratos nuevos: proof/correlation, native consent, frozen args, cancel/stale/disconnect, no cache/chat copy |
| Audit/log safety + lifecycle | S7 real + resumen de OTHER Operation | canonical/secret ausentes de audit/events/snapshot; terminal único; pre-effect deny/post-effect gap/no retry |

**Gate literal:** “usuario puede crear, inspeccionar, corregir y olvidar recuerdos sin LLM extractor.” **PASS:** existen todos los entregables y pasan sus tests requeridos; no queda MUST M3 sin demostrar. Este PASS no certifica los invariantes operativos de fases futuras.

## 4. Contratos / schemas / cambios de comportamiento

- DTO aditivo `MemoryControl` schemaVersion 1, `MemoryCommand` y resultado síncrono `MemoryControlResult`. `completed` representa outcome observado, no la aceptación asíncrona de un Turn. Core ApplicationCommand/CommandReceipt y schemas públicos de tools no cambian.
- Nombres: `memory_status/list/search/show/remember/correct/forget/export`. `/memory inspect` alias de status.
- Core contiene sólo ports: export explícito, match exacto acotado y insert-if-absent atómico; identidad permite resolve read-only. SQLite/paths/OS permanecen Infrastructure/Composition.
- Schema DB, codec, application_id, exportVersion y migraciones M2 siguen en v1; **ninguna migración nueva**, ningún store legacy destruido/importado. Apertura v0 sigue exigiendo opt-in tipado M2.
- Factory perezosa: `<config.state_dir>/memory/v1/memory.db`, fuera del workspace. Sólo se inicializa tras una acción del host aceptada y el barrier S7. El cambio de workspace vuelve a verificar la localización del store.
- Default de scope de controles: WORKSPACE actual; GLOBAL_PROFILE por selección explícita; ALL sólo inspección. SubjectId/provenance no se reciben del renderer. El scope de estos controles mediados no constituye aislamiento frente a procesos HOST_UNISOLATED.
- Límites operacionales por item: 4.096 caracteres / 512 tokens estimados; key ≤256 caracteres. List/search default 20 y máximo 100. No fijan las quotas finales OD-04 ni el cap de capsule M4.
- CLI exige host TTY para estos controles. Desktop usa host proof separado por discriminator MemoryControl, privado en Main, no un grant; raw renderer frames se deniegan. Datos sensibles/reveal requieren diálogo nativo por acción; cancel/rebind/revision change invalida consentimiento.
- Actor del adapter cerrado no autoriza. Writes son serializados por coordinator; los receipts idempotentes sólo contienen digest/metadata, nunca recall data. Reusar un ACK histórico no recrea un delete.
- La política básica detecta secretos conocidos S6 y credenciales evidentes; no es un detector universal. SENSITIVE por indicación explícita/heurística conservadora; conserva la clasificación en correcciones/dedup.
- Export no altera recuerdos/índices/metadata. La inicialización perezosa del store/subject es una acción separada de apertura, no una migración por export.
- Forget elimina el recuerdo indicado/proyecciones propias. Lineage superseded no solicitado para borrado sigue inspectable. Audit/logs/conversaciones/backups externos quedan intactos; aviso explícito, **no secure erase**.

## 5. Tests ejecutados y clasificación de evidencia

| Corrida | Resultado |
|---|---|
| Baseline restringido | 7 failed, 3.698 passed, 11 skipped, 53 subtests |
| Baseline Windows nativo | 3.705 passed, 11 skipped, 53 subtests |
| Bloque service inicial | 283 passed |
| M3 definitivo | **354 passed, 2 skipped, 0 failed/xfail** |
| HEAD final | **3.751 passed + 53 subtests passed, 11 skipped, 0 failed/xfail** |
| Desktop contratos | **38 passed, 0 skipped/failed** (8 nuevos M3) |
| TypeScript --noEmit | exit 0 |
| git diff --check | exit 0 |

M3 añade **46 tests Python**: 31 service, 14 Application/transport, 1 composition; no provider inference. Los dos skips de la selección dirigida son los E2E opt-in históricos Electron/Ollama; los 11 skips de HEAD son los mismos del baseline. No se añadieron skips/xfail ni se reintrodujeron suites históricas S0/legacy al gate HEAD.

**Unit/contract:** DTO/ports, parsing, WritePolicy, host proof, revisión/identidad y Desktop client. TTY/catalog provider/dialog son fixtures; no claim de interacción humana real ni calidad LLM.

**Integration/persistence real:** SQLite/FTS, audit JSONL, Application, CLI handler, JSONL y composition roots normales sobre state sintético privado. Reinicio significa close/recreate/reopen de estos componentes; recuperación multiproceso/crash nativo se hereda de las pruebas M2 repetidas, no se sustituye con mocks.

**Fallos inyectados:** audit flush pre/post y error observado después de commit, con resultado incierto/no retry. La intercalación de writes es controlada, con dos conexiones SQLite reales; no se etiqueta como benchmark multiproceso.

**Host-real regresión:** suite Core/native vigente y pruebas M2 de crashes/lock/subprocess; datos sólo sintéticos. No host-real con LLM, Electron visual, embeddings ni Linux/macOS: M3 no los exige.

Todos los fallos intermedios se conservan en [m3_evidence](m3_evidence/):

- Harness referenciaba un archivo inexistente: se reemplazó por el test JSONL vigente, no la suite legacy excluida.
- Ruta nueva de rechazo usaba un atributo inexistente: bug M3 corregido, error seguro/redactado.
- Expectativa M1 de cero wiring: stale por autorización M3; se conservan prohibiciones válidas de dependency direction, AgentRuntime, tools/RAG y los cierres históricos.
- Fixture revision 0: harness incorrecto; la sesión inicial real tiene revision 1; se utiliza snapshot y se conserva el test de stale rejection.
- Declaración TypeScript faltante/null workspace: contrato nuevo corregido, sin alterar Core.
- Harness Node omitía SystemRoot por casing y el transform-types requerido por tests S7: errores de ejecución corregidos; las assertions S7 no cambian.
- **Race real M3:** el fixture demostró dos commits después de precheck vacío. Se añadió insert-if-absent bajo BEGIN IMMEDIATE; el perdedor devuelve MEMORY_CONFLICT. Se conserva la corrida fallida y la corrección demuestra una sola copia, sin retry/merge/rollback simulado.

## 6. Performance / invariantes / compatibilidad

M3 no fija thresholds de performance ni los READY/quotas M8. Se repitió descriptivamente el benchmark M2 10k/20k; valores íntegros en [m2_regression_benchmark_final.json](m3_evidence/m2_regression_benchmark_final.json). No se inventó un benchmark MEMORY semántico, LLM ni export masivo.

En esta repetición: 10k/20k records, SQLite WAL + synchronous FULL; consultas exact/FTS devuelven ≤8 IDs. Medianas exact key: 0,667/1,016 ms; selective FTS: 0,273/0,671 ms; broad FTS: 25,131/51,297 ms. Los números pertenecen a fixtures locales y no prometen durabilidad contra power-loss/OS, ni latencia universal.

[m3_invariants.json](m3_invariants.json) separa evidencia actual de obligaciones M4+. Demostrados: identidad/scope/provenance, separación de stores, dedup sin truth score, correction lineage, no LWW, secret denial/consent, borrado/FTS/tombstone, no audit erase, sin authority/grants, sin auto-RAG/subagent store, terminal único y resultado observado ante gaps. Los contratos de prompt/budget/semantic/maintenance permanecen diferidos, no marcados como runtime PASS.

Core y SECURITY conservan AgentSession/Turn/Generation/Operation, ToolRuntime, policies/approval/grants, provider switching, subagentes y schemas de tools. ContextManager/config y matriz 4K/8K/16K/32K/64K no cambian; HEAD incluye su regresión/M0. Memory no participa aún en el prompt: no consume presupuesto ni carga transcript por espacio disponible. Git sigue opcional. CLI y Desktop comparten el backend Application.

## 7. Archivos creados/modificados

El manifest enumera y hashea todos los archivos de M3, diferenciando overlaps previos:

- Application: nuevos `memory.py`, `memory_policy.py`; coordinator `session.py`.
- Core/Infrastructure: extensión mínima de `core/memory.py` y `memory_sqlite.py`; codec/migrations intactos.
- Composition: nuevo `memory_config.py`; wiring CLI/server.
- Interfaces: nuevo `memory_cli.py`, CLI/JSONL adapters, handler `cli.py`.
- Desktop: client/Main/preload, DTO shared/types; nuevos `memory_control.cjs/.d.cts` y tests.
- Tests: service/application/composition, runner Desktop, modo m3 en runner común, actualización normativa del test M1 de wiring.
- Cierre: este documento, manifest, invariantes y evidencia nueva. No se reescriben manifests ni evidencia previos.

## 8. UNKNOWN / deuda / OPEN DECISIONS

No hay pendiente obligatorio del Gate M3. No se certifica MEMORY completa.

Persisten para fases posteriores: recall/capsules/budget M4; backend/modelo semántico M5; extracción, normalización semántica/consolidación/maintenance M6; controles completos privacidad/subagentes/remoto M7; calidad/quotas/retención/escala M8. Export explícito materializa un snapshot y puede crecer O(n); no se reclama streaming ni performance masiva. M3 hace exact key/content dedup, no equivalencia semántica ni aliases de keys.

MEM1-OD-01 backend semantic, OD-02 embedding model, OD-03 AUTO_SAFE thresholds, OD-04 quotas finales, OD-05 retención EPISODE, OD-06 cifrado at-rest y OD-07 umbrales READY siguen abiertas. Ninguna bloquea M3. Almacenamiento local no implica encryption; SENSITIVE consentido puede quedar en claro. Detección de datos desconocidos/obfuscados no se demuestra universalmente.

Sin regresiones observadas en el alcance probado. Certificación de otras plataformas/LLM/Electron visual permanece NO VERIFICADA; no se convirtió unsupported en PASS.

## 9. Reproducción y detención

Desde la raíz del checkout, con Python/runtimes actuales y nuevos directorios externos privados:

```powershell
python -B -m tests.memory_v1.run_regression --mode m3 --output <new-private-directory>
python -B -m tests.memory_v1.run_regression --mode head --output <another-private-directory>
python -B -m tests.memory_v1.run_m3_desktop --output <another-private-directory>
git diff --check
```

El runner registra comandos exactos, runtime, junit y logs; rechaza reutilizar directorios. Los contratos OS se ejecutan en contexto nativo permitido. No perfiles/databases privados son copiados a este cierre: sólo logs, XML, metadata y benchmark sintético.

**Siguiente fase lógica: M4 — Lexical recall + TAC user-first budgeting**, sólo referencia. No implementada. No commit, push, tags, CI, global config, modelos/cloud ni GPU modificados.

