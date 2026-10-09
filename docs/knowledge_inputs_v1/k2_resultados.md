# K2 — Attachments y host acquisition

Resultado: **K2 PASS**, limitado a §57. No declara Knowledge Inputs READY ni soporte de formatos/retrieval de K3–K5.

## Baseline y alcance

- Branch: `main`; HEAD base y final: `717a24218dea7fb60d8b630896d653e39091bc7b`.
- Estado evaluado: HEAD + K0/K1 no commiteados + cambios K2 identificados por hashes. No es HEAD limpio.
- Working tree inicial: cuatro modificaciones MEMORY preexistentes y archivos no versionados K0/K1/arquitectura; inventario íntegro en `k2_freeze.json`. Los cuatro archivos MEMORY se conservaron byte por byte.
- Host: Windows 11 build 26200, C: NTFS local, `HOST_UNISOLATED`. Sin sandbox, process isolation ni claims S3 para host acquisition.
- Nova 0.12.6; Python 3.14.6 / pytest 9.1.1 / SQLite 3.50.4; contratos también en Python 3.12.14; Node 24.19.0.
- Arquitectura Knowledge SHA-256: `417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432`.
- Precedencia §3: Core > SECURITY > MEMORY > Knowledge. No contradicción bloqueante ni modificación normativa.
- Preflight antes de cambios: 329 Knowledge PASS y 131 boundaries PASS. K0/K1 son prerrequisitos ya preservados.
- Tags Core, Security, Memory V1/V1.1: objetos y commits intactos, todos ancestros de HEAD. 68 pins protegidos/preexistentes comprobados sin mismatch; detalle `k2_evidence/integrity.json`.

Reutilización: store K1 versionado, staging/publicación/recovery/tombstones/ownership; Core ServiceOperations, eventos, cancel y coordinator; canales host y firmas existentes. Legacy notes/RAG/preview no son autoridades de ingestion y no se migraron.

## Implementación y contratos

1. `AttachmentRef` V1 estricto: attachment/source/revision UUID, display name y estado. No path, bytes, scope arbitrario ni grant. `SubmitUserInput.content` sigue siendo texto; referencias separadas, validadas contra catálogo autorizado. Transcript conserva refs descriptivas; runtime/model y captura MEMORY reciben sólo contenido actual, sin auto-concatenación documental.
2. `HostFileAcquisitionPort` en Core y adapter Infrastructure de archivos seleccionados explícitamente. Lecturas de 256 KiB, límite por fuente 50 MiB, cancel entre unidades y detección de modificación. Se rechazan targets relativos, NUL, directorios, reparse/junction y hardlinks. Path seleccionado no se conserva como origin ni se obtiene de metadata documental.
3. `KnowledgeControl` V1 en Application: source_import/list/status/promote/delete/cancel, session + expectedRevision, argumentos exactos e idempotencia. Actor host verificado, no tool/model import paralelo. Workers usan el lifecycle Core; I/O del store fuera del lock del coordinator.
4. SESSION por defecto; WORKSPACE sólo explícito. Promote crea Source/Revision/blocks/chunks nuevos a partir de bytes/proyección adquiridos, sin reabrir origin ni reinterpretar vectores. Cleanup SESSION al cerrar/rebind; WORKSPACE persiste.
5. CLI `/attach` y `/source`; JSONL autenticado `knowledge_command`; mismo backend Application. Desktop main-owned picker, main frame validado, selección única y precondiciones de sesión/workspace/revisión. Renderer sólo recibe refs/estado y solicita acciones por IDs; no parser, DB, path-import ni raw control bypass.
6. Progress/status/cancel, cierre EOF y receipts sin success optimista ni retry automático. Security Audit existente: pre-effect failure impide acquisition; terminal gap conserva efecto observado, lo informa y no simula rollback.
7. Extensiones del port K1: `list_sources`, `read_prepared`, `operation`. No cambia schema SQLite V1 ni agrega migración. DTO/capability snapshot estable entre lecturas sin cambio de estado.

### Límite intencional de fase: no parsers ficticios

La composición productiva tiene `prepare=None`: adquiere bytes/staging mediante la ruta real y termina con `UNSUPPORTED_FORMAT`, source FAILED, sin revision READY ni blobs/staging publicados. Una fuente sin revisión publicada no se puede promover.

Los tests de publicación/promote usan un **producer sintético de proyecciones preparadas** con adquisición y SQLite reales. Ese seam mínimo permite comprobar los contratos K2 sin adelantar parsers K3 ni algoritmos K4. No demuestra extracción real ni answer-from-attachment.

Snapshot: attachments/workspaceLibrary `DEGRADED`; extraction/lexicalRetrieval false; PDF/DOCX/HTML/OCR/webSearch/webFetch/semanticRetrieval `UNAVAILABLE` en Knowledge. No se altera la capability productiva preexistente de la tool Security web_fetch.

## Gate §57, criterio por criterio

| Requisito | Estado | Evidencia |
|---|---|---|
| attachmentRefs | PASS | DTOs estrictos, refs scoped y separación transcript/runtime/MEMORY |
| Desktop picker flow | PASS | Main-owned picker, firma y freshness; 10 tests K2 Desktop; dialog double identificado |
| CLI/JSONL import | PASS | TTY / host proof exacto; roots normales sin eager store |
| SESSION sources | PASS | Scope host explícito, cleanup y aislamiento cross-session/workspace |
| promote/import WORKSPACE | PASS | Acción explícita, nueva identidad, copia de revisión scoped y persistencia; proyecciones sintéticas |
| progress/status/cancel | PASS | Core Operation/eventos, cancel cooperativo, idempotencia y terminal único |
| Attachment no es user assertion | PASS | No bytes/refs/name añadidos al user/system/prompt/captura MEMORY |
| Renderer no obtiene authority directa | PASS | No path/import/proyección arbitraria; raw pipe bloqueado y main frame validado |
| Core/Security/Memory compatibles | PASS | Regresión amplia final verde y pins protegidos sin cambios |

Trazabilidad detallada requisito → componentes → tests: `k2_manifest.json::traceability`.

Invariantes demostrados en el alcance K2: KI-INV-001–011, 014–016, 023–025, 027–029, 031–035, 038–040. KI-INV-003 se conserva mediante store K1; no se añade refresh K3+. 014/015 se prueban por capability/failure honestos, no por parsers inexistentes. 027/028/031/032: contenido documental no admitido ni enviado; shared budgeting productivo existente sigue intacto. Delegación documental KI-INV-030, retrieval/citations y calidad K8 no se reclaman anticipadamente.

Decisiones aplicables: KI-OD-01/02/03/04/16/17/21/24/25/28; límites K1 existentes KI-OD-11/12/23, sin cambios.

## Tests y regresiones

| Corrida final | PASS | FAIL | SKIP | Alcance |
|---|---:|---:|---:|---|
| Knowledge Python 3.14 | 432 | 0 | 0 | 167 K0 + 162 K1 + 103 K2 |
| Knowledge Python 3.12 | 432 | 0 | 0 | Mismos contratos, deps de tests existentes sin instalación |
| Core/context/RAG boundaries | 131 | 0 | 0 | Arquitectura, context 64K y RAG |
| Compatibility focalizada | 55 | 0 | 0 | Los 4 fallos encontrados en primer HEAD quedan corregidos |
| MEMORY | 790 | 0 | 0 | Store/policy/retrieval/budgeting/contratos actuales |
| HEAD final aislado | 4578 | 0 | 11 existentes | 4589 casos XML + 53 subtests PASS; 324.68 s |
| Desktop | 50 | 0 | 0 | 10 nuevos K2 + 40 existentes |
| TypeScript --noEmit | exit 0 | — | — | DTO/IPC/renderer/main |

HEAD incluye 432 Knowledge, 790 MEMORY y 615 SECURITY; los restantes 2752 casos XML cubren Core y demás regresión. Estos números se solapan entre corridas: no se suman como tests únicos.

Los 11 skipped IDs y las 12 exclusiones HEAD son exactamente los del cierre K1. No hay nuevos skips/xfail/exclusiones; suites históricas S0/legacy y gates opt-in reales conservan su clasificación anterior. No se modifica CI.

Unit/contract: DTOs, firma, freshness, schemas, snapshots e invariantes. Integration/persistence: Application/CLI/JSONL + host reader + SQLite/FTS/publicación/delete/reopen reales. Host-real: NTFS Unicode/bytes/modificación/cancel, hardlinks/junctions y crash/recovery K1 reejecutados. Doubles: producer de proyecciones, provider/runtime sintético y respuesta del native picker/transporte Electron. No LLM real, embeddings, parsers reales ni Electron interactivo ejecutados; no requeridos por el gate K2. No calidad semántica inferida de doubles.

### Fallos observados y conservados

| Corrida | Resultado observado | Clasificación / causa |
|---|---|---|
| block1 | 319 PASS / 10 FAIL | ENVIRONMENT: sandbox negó crear fixtures NTFS antes de evaluar containment. Repetidas con permiso nativo, sin skip |
| block2 | 366 PASS / 58 FAIL | 48 PRODUCT_BUG (45 IDs Core incompatibles + 3 comparación Windows ctime) y 10 HARNESS_BUG (event stream ausente en helper nuevo) |
| block3 | 415 PASS / 9 FAIL | PRODUCT_BUG: nueva ruta rejection pasaba argumento no admitido a _reject |
| block4 | 415 PASS / 9 FAIL | PRODUCT_BUG: primer ajuste de esa firma seguía siendo incorrecto |
| block5 | 419 PASS / 10 FAIL | 9 PRODUCT_BUG de rejection y 1 HARNESS_BUG: import de enum de audit inexistente |
| Python 3.12 inicial | no collection, exit 1 | ENVIRONMENT: pytest no instalado en runtime alterno; se reutilizó site de tests existente |
| HEAD inicial | 4573 PASS / 4 FAIL / 11 SKIP | 3 PRODUCT_BUG reales K2: capturedAt mutaba snapshot; 1 HARNESS_BUG: double FailingAdapter sin close() tras cleanup EOF |

La comparación temporal del reader conserva identity/size/mtime entre APIs y ctime dentro del mismo handle; no elimina detección de cambio. Rejection usa receipt CAPABILITY tipado. CapturedAt queda estable en el controller. FailingAdapter ahora implementa close y verifica su llamada; assertions de reader/errores no se relajan.

Cambio de test K1: una assertion estática prohibía activar roots en K1. Es STALE_EXPECTATION respecto de K2, que exige esa activación. Se reemplazó únicamente por comprobaciones de backend común y ausencia de parser/loop/bypass; evidencia histórica K1 intacta.

Los IDs y clasificaciones individuales están en `k2_evidence/test_runs.json`; tracebacks completos de corridas fallidas archivados separadamente. Ningún fallo observado se reescribe como PASS histórico.

## Reproducción

Usar un directorio **nuevo fuera de Git**, fixtures sintéticos y permisos NTFS cuando corresponda. Los commands exactos, runtimes y raw hashes están en `k2_evidence/test_runs.json`. Los harnesses aíslan perfil/state/temp, desactivan plugins/cache pytest y no descargan modelos.

```text
python -B -m tests.knowledge_inputs_v1.run_k0 --mode contracts --output <new-external-dir> --extra-test-site <existing-test-site-if-needed>
python -B -m tests.knowledge_inputs_v1.run_k0 --mode boundaries --output <new-external-dir> --extra-test-site <existing-test-site-if-needed>
python -B -m tests.knowledge_inputs_v1.run_k2 --mode compatibility --output <new-external-dir> --extra-test-site <existing-test-site-if-needed>
python -B -m tests.memory_v1.run_regression --mode m0 --output <new-external-dir> --extra-test-site <existing-test-site-if-needed>
python -B -m tests.memory_v1.run_regression --mode head --output <new-external-dir> --extra-test-site <existing-test-site-if-needed>
node --experimental-transform-types --test desktop/tests/knowledge_control.test.cjs desktop/tests/application_client.test.cjs desktop/tests/approval_host.test.cjs desktop/tests/security_audit.test.cjs desktop/tests/memory_control.test.cjs desktop/tests/memory_maintenance.test.cjs
node desktop/node_modules/typescript/bin/tsc --project desktop/tsconfig.json --noEmit
```

Freeze inicial: `k2_freeze.json`; primer candidato preservado: `k2_product_freeze.json`; implementación final (34 archivos): `k2_product_freeze_v2.json`. Todos los pins finales siguen coincidiendo después de HEAD. Raw outputs externos no se borraron; las copias de logs en Git sólo normalizan finales de línea, con hashes de ambas formas separados.

## Archivos de implementación/tests

### Creados por K2

- `desktop/electron/knowledge_control.cjs`
- `desktop/electron/knowledge_control.d.cts`
- `desktop/tests/knowledge_control.test.cjs`
- `local_cli/application/knowledge_host.py`
- `local_cli/core/attachments.py`
- `local_cli/infrastructure/knowledge_acquisition.py`
- `local_cli/interfaces/knowledge_cli.py`
- `local_cli/server.py`
- `tests/knowledge_inputs_v1/k2_helpers.py`
- `tests/knowledge_inputs_v1/run_k2.py`
- `tests/knowledge_inputs_v1/test_k2_acquisition.py`
- `tests/knowledge_inputs_v1/test_k2_application.py`
- `tests/knowledge_inputs_v1/test_k2_composition.py`
- `tests/knowledge_inputs_v1/test_k2_contracts.py`
- `tests/knowledge_inputs_v1/test_k2_interfaces.py`

### Modificados por K2

- `desktop/electron/application_client.ts`
- `desktop/electron/main.ts`
- `desktop/electron/preload.ts`
- `desktop/shared/application.ts`
- `desktop/src/App.tsx`
- `desktop/src/types.ts`
- `local_cli/application/commands.py`
- `local_cli/application/knowledge.py`
- `local_cli/application/session.py`
- `local_cli/bootstrap_cli.py`
- `local_cli/bootstrap_knowledge.py`
- `local_cli/bootstrap_server.py`
- `local_cli/cli.py`
- `local_cli/core/knowledge_store.py`
- `local_cli/infrastructure/knowledge_sqlite.py`
- `local_cli/interfaces/cli_application.py`
- `local_cli/interfaces/jsonl_application.py`
- `tests/knowledge_inputs_v1/test_k1_application.py`
- `tests/test_nova_core_phase11_characterization.py`

### Evidencia nueva

`docs/knowledge_inputs_v1/k2_{preflight.md,freeze.json,product_freeze.json,product_freeze_v2.json,resultados.md,manifest.json}` y `k2_evidence/` (logs, test_runs, Desktop, integrity y hashes). No se versionan DBs/state/caches/fixtures runtime.

## Limitaciones, UNKNOWN y deuda

- Parsers K3 y retrieval/context/citations K4/K5 no implementados; imports normales no son todavía documentos utilizables por el agente. El gate aquí certifica contratos y rutas K2, no capability end-to-end futura.
- No certificación Linux/macOS, modelos, embeddings ni Electron UI interactiva. `MEMORY SEMANTIC_PROFILE=NOT_CERTIFIED` previo permanece intacto.
- Host acquisition no pasa por S3, no hereda su claim fuerte ni protege contra toda carrera hostil de otro proceso del mismo usuario. No process isolation.
- Cancel cooperativo, no kill de parser (no hay parser productivo). Cierre espera trabajo pendiente fuera del reader; no garantía universal de power-loss.
- Delete no es secure erase ni elimina MEMORY/transcript/audit/backups. No DLP/cifrado/secret detection universal.
- No performance benchmark ni SLA nuevo K2; sólo duración de tests y bounds funcionales. Crecimiento/footprint/calidad documental quedan UNKNOWN para fases pertinentes.
- No Active Web, cloud, downloads, cambios globales ni dependencias/CI alterados.
- OPEN DECISIONS bloqueantes K2: **ninguna**. No se resuelve ninguna futura por adelantado.
- No regresión pendiente observada en las selecciones ejecutadas.
- Siguiente fase lógica: **K3**, referencia únicamente; no implementada.

Sin commit, push, tag ni staging. Se detiene para revisión humana.
