# MEMORY M6 — Extraction, consolidation y temporal memory

Fecha: 2026-10-06. Estado de cierre: **PASS exclusivamente para M6**.
Alcance exclusivamente M6. No se declara `NOVA_MEMORY_V1_READY`; M7/M8 no se implementan.

## 1. Baseline y precedencia

Branch `main`; HEAD inicial y conservado:
`468d213ede2fa52f6b2588ebaa1191b83669ccb8`.
Tags relevantes conservados: `nova-core-v1-stable`, `nova-security-v1.2-ready`.
Working tree inicial dirty, sin cambios staged: M0–M5, 64K, auditoría,
arquitectura MEMORY y su evidencia eran trabajo preexistente, no HEAD limpio.
No se restauró, borró ni sustituyó ese trabajo. No commit, push, tags ni CI.

Preflight: MEMORY §12–16, §23–30, §35–37 M6 y sus fronteras con M7/M8;
Core V1 lifecycle, single writer, operations/background scheduling y contexto;
SECURITY V1.2 redaction, authority y S7; auditoría como evidencia, no norma.
MEMORY define M6; Core/Security conservan sus invariantes superiores. La
decisión humana MEM1-OD-03 acota el auto-write más que las posibilidades
generales de perfil de §12.3: **perfil inferido y episodios no son AUTO_SAFE**.
No conflicto normativo obligatorio residual identificado.

Host observado: Windows 11 build 26200, C: NTFS. Python principal 3.14.6 /
SQLite 3.50.4, sin NumPy. Auxiliar ya instalado: Python 3.12.14 / SQLite
3.53.1 / NumPy 2.3.5. Node 24.16.0. No instalación/download de paquetes/modelos,
config global, GPU, conversaciones privadas ni datos personales reales.

Baseline antes de editar: `m6_baseline_20261006`, **881 passed, 3 skipped,
0 failed, 60.09 s**, runner con perfil/estado privado y permisos nativos.
Hashes iniciales: 1183 entradas / 1182 paths únicos; 781 archivos de evidencia
anterior seleccionados permanecen byte-for-byte. Véanse `m6_evidence/initial_hashes.json`
y `m6_evidence/source_changes.json`; la entrada duplicada config no se cuenta dos veces.

## 2. Gate y alcance literal

MEMORY §37:

> auto-memory es útil en corpus sintético y no viola write/provenance/sensitivity invariants.

Entregables: queue post-Turn, prefiltro barato, extractor local/schema,
WritePolicy, AUTO_SAFE, propuestas/confirmación, dedup, supersession/conflict
groups, memoria episódica, validez temporal e idempotencia de maintenance.

Permitido: mínimos contratos Core/ports, namespace de jobs en la tabla M2
existente, servicio Application, adapter local, integración por coordinator y
controles compartidos. No segundo AgentLoop ni sesión principal, LLM reranker
obligatorio, auto-profile, auto-procedure, compactación M7, retención/cifrado
decididos por conveniencia, nuevos tools/grants, cambios a policies SECURITY.

## 3. Decisión humana y WritePolicy

**MEM1-OD-03: resuelta para el alcance mínimo M6**, versión
`mem6-conservative-span-v1`, conforme a la respuesta humana de esta tarea.

- AUTO_SAFE sólo preferencias estables/convenios de workspace afirmados por
  el usuario, NORMAL, evidencia literal verificable, sin contradicción,
  instrucciones/inyección conocidas, citas/ejemplos/ambigüedad/temporalidad explícita.
- Application asigna sujeto/scope. Una preferencia personal inequívoca puede
  usar GLOBAL_PROFILE; referencias a proyecto permanecen WORKSPACE. El job y
  su confirmación siguen vinculados al workspace de origen.
- Perfil inferido, EPISODE, assistant/tool/subagent y casos ambiguos:
  PROPOSE_ONLY, no auto-globalización. PROCEDURE: EXPLICIT_ONLY.
- No score de confianza LLM autoriza nada. Campos authority/subject/scope/
  confirmed/confidence fuera del schema son rechazados.
- Sensitive/secret/instruction-like no se escrowean automáticamente como texto
  de propuesta. No downgrade ni auto-append a un record ya SENSITIVE.
- Detector/gramática son conservadores y acotados, no comprensión universal
  ni garantía de detectar cualquier secreto desconocido o lenguaje adversarial.

Config confiable `memory_auto_capture=off|propose_only|low_risk`; default **off**
conserva opt-in/legacy y la semántica M3–M5. §12.3 condiciona AUTO_SAFE a
low_risk; no se cambió configuración real del usuario. CLI/server instalan el
mismo servicio y adapter. Un actor/render/modelo no puede cambiar este modo
mediante argumentos de un tool o MemoryControl.

## 4. Implementación y trazabilidad

| Requisito | Componente | Evidencia reproducible |
|---|---|---|
| Jobs post-Turn / prioridad del usuario | coordinator + MemoryMaintenanceService | `test_m6_application.py`: terminal único, preemption, cancel manual, model switch |
| Prefiltro barato | memory_extraction | chatter/sensitive/secret/injection sin llamada al extractor |
| Extractor local y schema validado | MemoryExtractorPort + LocalOllamaMemoryExtractor | `test_m6_extractor.py`, corpus Ollama real |
| WritePolicy/AUTO_SAFE | AutoSafeMemoryPolicy | corpus bilingüe, fuentes no-user, temporal/ambiguo, authority fields |
| Propuestas/confirmación | MemoryService/MemoryControl + CLI/Desktop | actor auténtico, job/proposal/revisión exactos, rechazo, stale CAS, Desktop frame |
| Dedup sin truth boost | MemoryConsolidator + aggregate transaction | repetición mantiene un record, añade fuentes, importance NORMAL |
| Supersession/conflict groups | consolidation + SQLite metadata/projections | no LWW, cuarentena, resolución supersede o conflict explícita |
| Episode / temporal validity | literal bounds + MemoryRecord | episodio propuesto/confirmado, elegibilidad expiración; procedimiento explícito |
| Crash/retry/idempotency | MemoryMaintenancePort + SQLiteMemoryMaintenance | crash real antes/después de COMMIT, reopen, receipt+record atómicos |
| Privacy/delete | invalidation + normalized tombstone | jobs pending/ready/resueltos propios, sin resurrección ni borrado audit |
| Core/Security/contexto | contratos anteriores + regression | cinco ventanas, full HEAD, audit pre-effect/gap, scopes/provenance |

Source hashes enumeran **12 archivos preexistentes modificados** y **12 nuevos
source/test files**. Los nuevos documentos/evidencia M6 se añaden aparte.

Modificados: `application/session.py`, `application/memory.py`,
`application/memory_recall.py`, `core/memory.py`, `infrastructure/memory_sqlite.py`,
`infrastructure/memory_semantic.py`, `memory_config.py`, `config.py`,
`bootstrap_cli.py`, `bootstrap_server.py`, `interfaces/memory_cli.py` y
`desktop/electron/application_client.ts`.

Nuevos: `core/memory_maintenance.py`, `application/memory_extraction.py`,
`application/memory_maintenance.py`, `infrastructure/memory_extractor.py`,
`infrastructure/memory_maintenance.py`, `tests/memory_v1/m6_fixtures.py`,
`run_m6_model.py`, los cuatro `test_m6_*.py`, y
`desktop/tests/memory_maintenance.test.cjs`.

## 5. Contratos, persistencia y recovery

Nuevos ports/value objects Core: MemoryExtractionInput, MemoryRecordChange,
MemoryExtractorPort y MemoryMaintenancePort. Sin SQLite/Ollama/paths concretos
en Core. Error tipado aditivo `MEMORY_EXTRACTION_UNAVAILABLE`; MemoryQuery
incluye un conjunto acotado de IDs excluidos por Application, filtrado antes
de ranking SQL/vector, no una authority del modelo.

No migration destructiva ni cambio de `user_version`/MemoryRecord v1. Se usa
`maintenance_jobs` M2, namespace `nova-memory-maintenance-v1`, schemaVersion 1,
revision CAS, identity/workspace/source inmutables, estados
PENDING/READY/DEFERRED/DONE/FAILED/CANCELLED. Payload ajeno/histórico se conserva.
Corrupt owned drafts fallan tipadamente; no se interpretan como recuerdos válidos.

Extractor wire schema: v2 devuelve `kind/evidenceSpan/key/validFrom/validTo`;
Application verifica una ocurrencia literal única y conserva el texto, incluida
su capitalización. El parser también caracteriza v1 offsets estrictos; no
clampa ni corrige offsets inventados. Evidencia/hashes/IDs nacen del host.

Límites operacionales mínimos: evidencia 4096 caracteres, span 512, hasta cuatro
candidatos, payload 64 KiB, 64 jobs activos, 128 jobs con propuestas, un worker
y un job por tramo idle, deadline 30 s, salida modelo 384 tokens y respuesta
HTTP retenida hasta 64 KiB. No cuotas OS/aislamiento; no son la resolución de
quotas finales MEM1-OD-04. No purga temporal ni sobrellenado del contexto.

Checkpoint READY permite recuperar extracción sin repetirla. Cambios de record,
fuentes, FTS/epoch y recibo DONE comparten **una transacción SQLite**. Crash real
antes de COMMIT no inventa efectos; después de COMMIT se observa receipt+record.
CAS evita replay/doble fuente. Error de COMMIT incierto conserva outcome_unknown;
se verifica tras reopen, no se reintenta ciegamente.

Dedup: key/exact/normalizado, candidatos lexical acotados y semantic opcional
si M5 está disponible; ambiguity no se convierte en auto-merge ni confianza.
Repetición no incrementa importancia/truth. Conflicto marca el viejo record
CONFLICTED, agrupa la propuesta sin crear el nuevo hecho automáticamente y
excluye ese conflicto del recall. Confirmación exacta permite supersession
con lineage o mantener ambos CONFLICTED. Rechazar propuesta no revive el viejo
valor: requiere corrección explícita. Validez ISO debe estar literalmente en
la evidencia, ser timezone-aware y coherente; no se inventa TTL para preferencias.

Forget elimina/invalida contenido pendiente y drafts/receipts propios asociados,
actualiza tombstone normalizado sin texto y evita nueva ID resurrectora. No
borra transcript, Audit, fuentes externas/backups; no secure erase.

## 6. Lifecycle, seguridad y contexto

El Turn termina antes del mantenimiento: resultado/status/terminalCount y
transcript range no se reabren. Maintenance tiene OperationId propio, deadline,
CancellationToken, cuota y terminal aun sin renderer. Un solo writer coordina
captura/checkpoints/commit; el worker sólo hace inference fuera del lock.

Nuevo Turn solicita cancelación y tiene prioridad; no se admite resultado tardío,
de otro runtime/workspace o posterior al deadline. Cancel manual no reinicia
blindamente. Jobs conocidos pueden diferirse; failed/uncertain effects no se
replayean como si no hubieran ocurrido. HTTP lectura bounded/polling observa
token/deadline; no afirma parar físicamente Ollama ni otros procesos del host.

Extractor: sólo loopback sin credenciales/proxy/redirect; catálogo installed,
completion capability, digest y modelo main ya residente/contexto verificable.
No pull/load deliberado, cloud, tools, todo transcript, environment/provider
secrets ni acceso al store. El main Turn normal puede cargar su modelo instalado;
no se utiliza un modelo de chat como embeddings.

S7 se reutiliza sin modificar su schema/policy: metadata sólo, barrier durable
antes de queue/checkpoint/commit, terminal y gap. Si audit falla antes se deniega
el efecto; si falla después permanece el resultado observado y se informa gap,
sin retry/rollback. Tests inyectan fallos: no son evidencia de un fallo IO real.

4K/8K/16K/32K/64K: budgeting N numérico y caps M4/Core intactos. Current user,
system/security y continuidad obligatoria prevalecen; memoria irrelevante puede
usar cero tokens. No aumento automático del recall ni transcript indiscriminado.
Los cinco presets se prueban contractualmente; inferencia real M6 se evalúa en
**4K**, no se atribuye calidad/costo real medido a 64K.

## 7. Pruebas y resultados

| Corrida | Resultado | Naturaleza |
|---|---|---|
| Baseline previo | 881 pass / 3 skips previos / 60.09 s | regression privado, no inference externa |
| Primer bloque | 72 pass / 0 skip / 3.49 s | SQLite/recovery M2+M6 real, sintético |
| M6 contractual antes de últimos guards | 76 pass / 0 skip / 11.27 s | unit, adversarial, Application, persistence, proceso/HTTP nativos |
| Regresión final pertinente | **959 pass / 3 skips previos / 72.93 s** | Core/context/config/providers/CLI/Desktop/persistence/RAG/M0–M6 |
| Auxiliar final NumPy | **606 pass / 0 skip / 41.19 s** | contratos positivos semantic + M0–M6, sin calidad LLM |
| HEAD previo a dos últimos guards | 3960 pass / 11 skips previos / 53 subtests / 269.17 s | selección vigente CI, histórica excluida |
| HEAD final guarded | **3962 pass / 11 skips previos / 53 subtests / 261.68 s** | misma selección; no skips/xfail añadidos |
| Desktop | **40 pass / 0 skip**, TypeScript exit 0 | contratos Node, sin nueva UI/Electron launch |
| Local model final | **12/12 corpus pass + E2E normal pass** | qwen3.5:9b real local, no scripted inference |

Los tres skips de la regresión pertinente ya existían: config symlink, Electron
E2E y Electron/Ollama opt-in. No son evidencia positiva; no se escondieron
fallos M6 con skips/xfail. Windows host-real SECURITY symlink/S8 no se vuelve
a certificar; su evidencia histórica y exclusiones permanecen intactas.

Clasificación de corridas fallidas conservadas en `incremental/`:

- block2: HARNESS_BUG (nombres de enum); block2b: HARNESS_BUG (fixture de dates).
- block3: HARNESS_BUG (StartTurn inexistente); block3b: enum casing en harness
  y PRODUCT_BUG M6 de integration (`policyVersion` no pertenece a schema S7).
  Se corrigió M6 para usar `policyRevision`, **no** se amplió Security Audit.
- extractor/extractor_fixed: PRODUCT_BUG M6 de cancelación HTTP bloqueante;
  corrected por lectura polling en el worker; `extractor_poll`: 19/19 pass.
- primera corrida qwen: invalid proposal workspace-en, raw no registrado en ese
  caso: causa específica **UNKNOWN**, no se inventa outcome. Normal backend
  record+recall sí pasó; existió carrera de cierre en el harness tras t2.
- literal v2 inicial: MODEL_BEHAVIOR (omisiones en positivos) y key camelCase
  fuera de schema. Se conserva PASS=false. Prompt/schema/harness se corrigen;
  no se relajaron checks de span ni los 12 casos.

El corpus contractual final tiene **78 casos M6** (959 − 881), todos ejecutados,
sin skip. SQLite/crash/HTTP real ≠ real LLM. Extractor fixtures son contracts,
no calidad de modelo; sólo los report.json Ollama respaldan calidad real limitada.

## 8. Métricas reales y límites de la afirmación

Modelo qwen3.5:9b Q4_K_M, digest
`6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`.
Corpus fijo bilingüe: cuatro preferencias/convenios elegibles AUTO, ocho casos
no-auto (perfil/episodio/hipotético/ambiguo/chatter/sensitive/secret/injection).
**4/4 elegibles, 0 auto-admisiones en los ocho negativos, 12/12 checks** en la
última corrida. Ocho calls reales de extractor, cuatro prefiltros sin inference.
La métrica `autoWrites` del harness es disposition count del parser/policy,
**no ocho/doce writes DB ni un score factual**. El E2E separado sí demuestra
un record durable real, source USER_ASSERTION, operation/audit y recall real.

Final: inference extractor entre **931.954 y 2853.266 ms** en los calls medidos;
E2E normal terminal+maintenance **3704.026 ms**; recall lexical **2.889 ms**,
un recuerdo, **62 tokens / cap 327** en 4096. Segunda generación/main Turn
responde `Concise answers.` con snapshot real de ese record. Repetición final
es una corrida nueva tras cambios, no retry ciego de una operación fallida.

No benchmark nuevo 10k/20k exigido por M6, no inventado. No calidad universal,
M8 READY, cold-start/co-residencia RAM/VRAM, certificación Linux/macOS, robustez
multilingüe general ni parada física de compute de Ollama demostrados aquí.
El modelo omitió profile/episode en el corpus real; la capacidad proposal /
confirmación/temporal EPISODE está probada con fixtures, no con calidad LLM
universal. No se utiliza ausencia de embedding model como deficiencia.

## 9. Reproducción

Desde el repo, con runtime existente y un **nuevo** directorio de output fuera
del workspace; runners aíslan profile/cache/temp y conservan outputs anteriores:

```powershell
python -B -m tests.memory_v1.run_regression --mode m4 --output <nuevo-output-privado>
python -B -m tests.memory_v1.run_regression --mode head --output <otro-output-privado>
python -B -m tests.memory_v1.run_regression --mode m0 --extra-test-site <pytest-puro-existente> --output <nuevo-output-auxiliar>
python -B -m tests.memory_v1.run_m3_desktop --output <nuevo-output-desktop>
python -B -m tests.memory_v1.run_m6_model --model qwen3.5:9b --output <nuevo-output-modelo>
```

Los run.json registran comandos/runtime/plataforma exactos; run.log/tests.xml
dan los resultados sin reinterpretar corridas históricas. El model runner es
opt-in, usa sólo fixtures sintéticos locales y no descarga modelos. Corrección
de jobs humanos: `/memory proposals`, `/memory confirm <JSON>` y
`/memory reject <JSON>`; commandId/host proof/session revision + job revision
ligan la acción exacta. Desktop usa las mismas operaciones Application, sin
necesidad de implementar una pantalla compleja nueva en M6.

## 10. UNKNOWN, deuda, OPEN DECISIONS y próxima fase

Todos los entregables M6 existen, sus nueve tests requeridos y los invariantes
aplicables pasan; el corpus real demuestra utilidad limitada sin ampliar
AUTO_SAFE. No requisito obligatorio queda UNKNOWN ni se adelantó M7. Se
declara **Gate M6 = PASS**, no MEMORY READY. La última regresión HEAD también
pasó; no regresión residual demostrada en el alcance ejecutado.

Deuda no bloqueante fuera del gate M6: recall/consolidation de paráfrasis
generales, extracción libre más allá de las formas directas conservadoras,
UI de gestión avanzada, escalado/retención de receipts, performance bajo
contención prolongada, co-residencia de modelos y hardening multilingüe.
No se amplió auto-capture para resolver esa deuda.
Los auto-commits invalidan los vectores derivados mediante el epoch M5 y no
re-embeben sincrónicamente en el tramo de commit: lexical permanece disponible;
warm semantic del nuevo record requiere el mantenimiento/proyección M5 existente.
No se afirma que todos los auto-records ya tengan embedding ni se incorpora
un segundo job LLM/embedding especulativo para adelantar M7.

OD-03 necesaria M6: criterio humano implementado/evaluado; ampliar clases sigue
requiriendo aprobación y nuevos datos. OD-01 mantiene resolución M5 (matriz
NumPy derivada); OD-02 no se convierte en recomendación universal/co-residencia
por usar un modelo local seleccionado. OD-04 quotas finales, OD-05 retención
física episodios, OD-06 cifrado/key lifecycle y OD-07 umbrales READY permanecen
abiertas para fases posteriores. Ni threshold LLM arbitrario ni elección de
store/modelo futuro se impusieron para conseguir verde.

Core, Security, tools públicos, RAG, provider switching, subagentes, Git opcional,
CLI/Desktop y persistencia legacy conservan sus contratos. Siguiente referencia
lógica: **M7** (efficiency/compaction/RAG/subagentes), **sin implementarla**.
