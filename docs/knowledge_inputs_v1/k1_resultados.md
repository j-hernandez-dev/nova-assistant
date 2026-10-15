# K1 — Store, lifecycle y authority

## Estado y alcance

**K1 PASS.** La evaluación final y los denominadores se registran en `k1_manifest.json`.
Norma: `NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md` §56, con §§6, 8, 10,
16, 18–20, 41–44 y las decisiones de §54. No se modifica la arquitectura.

K1 implementa el store y su frontera interna de publicación. **No** implementa
acquisición K2, parsers K3, chunking/retrieval K4, cápsulas/citas K5, search K6
ni interfaces/delegación K7. No declara Knowledge READY ni ninguna capability
de attachments, PDF/DOCX, lexical recall o semantic recall disponible.

Precedencia: Core V1 > SECURITY V1.2 > MEMORY V1 > Knowledge. No se encontró
contradicción que requiera cambiar una norma o resolver una OPEN DECISION.

## Baseline real y preflight

- Branch `main`; HEAD `717a24218dea7fb60d8b630896d653e39091bc7b`.
- Working tree inicialmente sucio: K0 no commiteado, cuatro reparaciones de
  harness MEMORY ya existentes, auditoría y arquitectura Knowledge del usuario.
  Inventario completo y SHA previos: `k1_freeze.json`. No se revierten ni editan.
- Tags Core stable, Security ready, Memory ready y Memory v1.1 ready: sus objetos
  y commits objetivo coinciden con el freeze de K0 y se mantienen intactos.
- Windows 11 build 26200, C: NTFS local, `HOST_UNISOLATED`; Python 3.14.6,
  pytest 9.1.1, SQLite 3.50.4. Contratos también probados en Python 3.12.14.
- Antes de código: K0 **167 PASS**; Core/context/RAG **131 PASS**;
  MEMORY **790 PASS**. Outputs, comandos, tiempos y hashes en
  `k1_evidence/test_runs.json`. Sin inferencia ni datos personales.

Inventario aplicable:

| Pieza | Estado antes de K1 | Tratamiento |
|---|---|---|
| `core/knowledge.py` | DTOs K0, no store ni autoridad | Reutilizado sin editar |
| Core ExecutionContext/cancel/OperationStatus | Productivo | Contratos existentes, sin segunda sesión/loop |
| Memory SQLite/migrations | Productivo MEMORY | Patrón observado; DB, records, policies y código intactos |
| `local_cli/knowledge.py` | Notes legacy JSON/Markdown | No importado, migrado ni borrado |
| RAG legacy | SQLite/vectores sin identidad V1 documental | Sin reinterpretación ni activación automática |
| S3 / ToolRuntime / S5 | Seguridad de tools productivas | Intactos; ningún nuevo bypass de adquisición |
| Store documental V1 | Ausente | Implementado en K1 |
| Productores de documentos/chunks V1 | Ausentes | Doubles sintéticos; algoritmos pendientes K3/K4 |

Los archivos previstos y creados son exclusivamente los contratos de storage,
Application interno, adapters, composition root, tests K1 y evidencia de K1.
No se modifica CI, configuración global, dependencias o frontend.

## Contratos y persistencia

`core/knowledge_store.py` declara `KnowledgeStorePort`, acceso host-bound,
límites operacionales y DTOs mínimos de proyecciones preparadas. Documento,
bloques y chunks tienen schema V1, representación inmutable y decode estricto.
Metadata de bloque es descriptiva y plana, nunca autoridad. No fija algoritmos
de parser/chunking, ranking, embeddings o citas futuras.

`SQLiteKnowledgeStore` usa `<state_dir>/knowledge/v1/knowledge.db` y directorios
`blobs/`, `staging/`, `cache/`. SQLite: `user_version=1`, application/format ID
propio, foreign keys, WAL, synchronous FULL, transacciones y lease de escritor.
El lease es un lock local de Nova, no sandbox, cuota OS ni aislamiento host.

Tablas: sources, source_revisions, revision_publication, documents,
document_blocks, chunks, chunk_fts, semantic_spaces, semantic_vectors,
source_tombstones, import_operations y knowledge_meta. Las tablas semantic son
sólo esquema reservado; K1 no escribe embeddings ni ejecuta semantic retrieval.

La migración explícita disponible es formato **0 vacío reconocido → V1**.
K0 no tenía un formato de store con datos que migrar. DB desconocida, legacy,
futura o corrupta se rechaza: no se convierte silenciosamente en V1. La prueba
usa una copia sintética; conserva el original, rollback e idempotencia.

Las proyecciones FTS comprometidas son dependencia mínima inevitable de §20:
un booleano "indexed" no prueba publicación atómica. K1 recibe proyecciones
preparadas y almacena documento/bloques/chunks/FTS en una transacción; **no**
expone recall, scoring, QueryComposer ni un productor/chunker productivo.

## Lifecycle, authority y recovery

1. Application valida workspace/session y niega child access no delegado.
   Acepta bytes ya adquiridos y un productor interno de proyecciones, no paths
   de documentos ni un comando/model DTO. El composition root es explícito,
   aún no activado en CLI/Desktop. No representa una feature pública K2.
2. Source/revision UUID nuevos; operación usa el `operationId` del
   ExecutionContext Core. Correlación, cancel y terminal usan contratos Core.
3. Staging por ID Nova; writes en unidades ≤1 MiB, con límites y cancel checks.
   Flush/fsync del blob antes de publicación. Cancel no significa cero bytes leídos.
4. Documento/chunks/FTS y puntero actual se publican en una transacción tras
   validar digest, bytes, IDs, lineage y proyecciones obligatorias.
5. Revision publicada no cambia de significado: triggers impiden su update.
   Estado SUPERSEDED vive separado del contenido inmutable. La revisión vieja
   se conserva actual hasta commit de la nueva; una revisión parcial sigue PARTIAL.
6. Recovery diferencia commit probado de import interrumpido. Devuelve
   `OUTCOME_UNKNOWN`/gaps, no inventa éxito. Valida bytes y proyecciones; corrupción
   se informa y no permanece anunciada READY. Nunca usa staging como prueba de éxito.
7. Delete retira current, documentos/FTS/vectores, caches y blobs propios;
   conserva tombstone y metadata de revisión para referencias históricas.
   Tombstone, constraints y authority impiden publicación tardía/resurrección.
8. SESSION no cruza sesiones ni se promueve a WORKSPACE. Se limpia al cerrar y
   durante recovery de sesiones abandonadas del workspace host-bound. WORKSPACE
   persiste entre reinicios/sesiones y no cruza workspace.

Sólo se abren nombres calculados desde IDs planos Nova; origen, locator y paths
externos de metadata no son rutas de lectura. Se rechazan traversal, rutas
absolutas, ADS, reparse points, symlinks, hardlinks y cambios de identidad de root.
La prueba NTFS usa junctions reales y hardlinks reales; **no** se presenta como
certificación host-real de todos los tipos de symlink ni como garantía S3.
No se promete resistencia general a un proceso malicioso de la misma cuenta
que reemplace concurrentemente el state confiable.

Cleanup sólo elimina artifacts inequívocamente propios; ficheros ajenos se
conservan. Cleanup posterior a delete no simula rollback de la transacción.
Resultado incierto de commit bloquea la instancia hasta reopen/recovery, sin
retry ciego. Fallo de notificación posterior a publish preserva resultado y
expone `notification_gap`, sin duplicar efectos.

## Decisiones e invariantes demostrados

| Requisito / decisión | Componente y prueba |
|---|---|
| KI-OD-01/02/11/12; KI-INV-001/002/003/033 | IDs, lineage, contenido inmutable; `test_k1_store` + crashes K1 |
| KI-OD-03/04; KI-INV-029 | Access SESSION/WORKSPACE, todas las superficies; store/application/recovery |
| KI-OD-23/24; KI-INV-034/035 | Límites, cancel, staging, commit/recovery; store/recovery |
| KI-INV-008/009/011 | Keys calculadas, ownership/containment, origen descriptivo; containment/application |
| KI-INV-024/025 | Delete/FTS/vector/cache/blob/tombstone y no late publish; store/recovery |
| KI-OD-25; KI-INV-023 | Legacy vectors/notes intactos; containment/DB formato desconocido |
| KI-INV-004/005/006/007/038/039 | Core hacia dentro, no MEMORY/grants/loop/Active Web; AST + hashes protegidos |

Invariantes de parsers, retrieval/citas, shared cap, search o delegación que K1
no introduce no se anuncian como nueva implementación. Sus contratos vigentes
se preservan mediante ausencia de cambios y regresión Core/Security/Memory.

## Pruebas y naturaleza de evidencia

- Unit/contract: DTOs, schemas, límites, scope, integridad, authority, dependencias.
- Integration: Application real + adapter real + productor **double** de documentos.
- Persistence/migration: SQLite/FTS reales, copia de fixture, rollback, corruption,
  lineage, tombstones, lease y reopen. Fallos de acknowledgment se inyectan con
  double de conexión, identificados como tal, no como crash físico.
- Host-real: procesos que terminan con `os._exit` durante import/delete, otro
  proceso/instancia con lease ocupado y artifacts NTFS reales. Datos sintéticos.
- Parser real, proveedor remoto, LLM/Ollama, GPU y calidad retrieval: **NOT_RUN**,
  no necesarios para §56; no se presenta un double como evidencia de esas capabilities.

Incremental: 225 → 260 → 321 → **329 PASS**, sin FAIL/skips/xfail K1.
Final por archivo: store 59; recovery 39; containment 51; Application 13 =
**162 K1 PASS**, además de los **167 K0 PASS** preservados. Python 3.12:
**329 PASS**, 0 FAIL/skips. Desktop existente: **40 PASS**, 0 FAIL/skips.

Regresión HEAD final, denominadores de MEMORY/Security/Core, skips históricos y
hashes: `k1_evidence/head_final.json` y `k1_evidence/head_final.txt`.
Resultado: **4475 PASS, 0 FAIL, 11 skips históricos, 53 subtests PASS** en 323.29 s.
Incluye Knowledge 329 PASS, MEMORY 790 PASS y SECURITY 615 PASS. La comparación
de los once IDs de skip con K0 es exacta; no existe skip/xfail nuevo K1.
Se conserva literalmente la selección HEAD ya vigente; no se añaden exclusiones,
skips o xfail. Los resultados de K0 y campañas históricas no se reescriben.

Comandos reproducibles (usar directorios nuevos fuera del checkout):

```powershell
python -B -m tests.knowledge_inputs_v1.run_k0 --mode contracts --output <private-output>
python -B -m tests.knowledge_inputs_v1.run_k0 --mode boundaries --output <private-output>
python -B -m tests.memory_v1.run_regression --mode m0 --output <private-output>
python -B -m tests.memory_v1.run_regression --mode head --output <private-output>
node --experimental-transform-types --test desktop/tests/application_client.test.cjs desktop/tests/approval_host.test.cjs desktop/tests/security_audit.test.cjs desktop/tests/memory_control.test.cjs desktop/tests/memory_maintenance.test.cjs
```

Se usó el parámetro existente `--extra-test-site` para dependencias de tests ya
instaladas. Runtimes y comandos exactos figuran en el JSON de cada corrida.
DB, blobs, staging y logs de fixtures viven bajo el TEMP privado externo.
El repositorio sólo recibe código/tests y reportes sintéticos sanitizados.

## Limitaciones y deuda fuera de K1

- K2 debe conectar acquisition/host intent y Operations a las interfaces normales;
  K3/K4 deben producir las proyecciones reales y exponer retrieval filtrado por
  revisión actual. K1 no anuncia esas capabilities por existir tablas/DTOs.
- No se migra ni reinterpreta corpus/vector legacy. Reconstrucción explícita
  desde originales corresponde a K4; las notes originales se preservan.
- Sin benchmark de crecimiento ni calidad/parser/LLM en K1: **UNKNOWN** para
  esas fases. Reads/publication de bytes están acotados por 50 MiB, no zero-copy.
- Sin certificación Linux/macOS ni claims de sandbox/process isolation.
- Flush/fsync + WAL FULL y recovery/crashes de proceso están probados; power loss
  físico, firmware y atomicidad SQLite+filesystem universal **NO VERIFICADOS**.
- Delete no es secure erase ni borra transcript, MEMORY, Security Audit o backups.
  No se afirma detectar todos los secretos documentales ni DLP universal.
- Remote forwarding sigue false en Source por default; no se integra con
  providers/search ni se cambia ninguna autorización existente.

No OPEN DECISION bloqueante para K1. K2 es la siguiente fase lógica y **no se
implementa**. Sin commit, push, tags nuevos, cambios de CI o arquitectura.

## Gate §56, criterio por criterio

| Criterio obligatorio | Resultado | Evidencia |
|---|---|---|
| KnowledgeStore V1 | PASS | Schema/version/FK/WAL, ports y publicación real: store 59 |
| Migrations/recovery | PASS | Formato vacío → V1, fallo/rollback, corrupción, reopen: recovery 39 |
| Blobs/staging | PASS | Bytes/digest/fsync, bounded reads, artifacts owned: store/recovery/containment |
| SESSION/WORKSPACE | PASS | Matriz de acceso y lifecycle/session cleanup: store/application/recovery |
| Containment | PASS | 51 contratos/casos adversariales, junction/hardlink reales, metadata traversal |
| Delete/no-resurrection | PASS | Proyecciones/caches/bytes/tombstone, late publish rechazado, crashes delete |
| Legacy isolation | PASS | Notes/vectores/MEMORY/audit sintéticos intactos; sin migración automática |
| Crash/cancel probado | PASS | 8 escenarios crash import, 2 crash delete, 10 escenarios cancel; rollback/unknown |
| Cross-workspace probado | PASS | Todas las superficies + Application host binding + recovery ownership |
| Metadata traversal probado | PASS | 30 keys hostiles, 4 blob keys persistidas y corrupción de control/scope/lineage |
| Compatibilidad y control de alcance | PASS | HEAD/Desktop verdes; 43 hashes previos intactos, tags sin cambios; sin K2+ |

Archivos nuevos: 6 de producto (`core/knowledge_store.py`,
`application/knowledge.py`, `bootstrap_knowledge.py`,
`infrastructure/knowledge_files.py`, `infrastructure/knowledge_migrations.py`,
`infrastructure/knowledge_sqlite.py`); helper y 4 suites K1; este informe,
freeze/manifest y `k1_evidence/*`. **Ningún archivo preexistente modificado por K1.**
El manifest contiene el listado exacto y SHA de los artefactos evaluados.
