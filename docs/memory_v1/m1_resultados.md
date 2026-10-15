# NOVA MEMORY V1 — Resultados M1

Estado: **PASS (M1 exclusivamente)**. Fecha: 2026-10-06.

Gate aplicado: MEMORY V1 §37, **“algebra/contratos estables y ninguna ruta de memoria depende de sessionId como persona.”**

La solicitud identifica N=M1, aunque conserva una descripción de baseline/taxonomy/evaluación propia de M0. Se aplica el gate normativo M1, limitado a contratos puros, fixtures y evaluación: no se repite M0 como sustituto de M1, ni se activa MEMORY productiva. No se modifica la arquitectura aprobada ni se implementa M2.

## 1. Baseline inspeccionado antes de editar

- Branch: `main`.
- HEAD: `468d213ede2fa52f6b2588ebaa1191b83669ccb8` — `ci: align unsupported filesystem gates across platforms`.
- Tags presentes relevantes: `nova-core-v1-stable`, `nova-security-v1.2-ready`; no se usa un checkout deprecated.
- Nova: 0.12.6. Python: 3.14.6, 64-bit.
- Plataforma local de ejecución: Windows 11, build 26200, NTFS. Node disponible: v24.16.0; M1 no modifica Desktop ni instala dependencias.
- Working tree **no limpio**: ya contenía M0 MEMORY, documentación de auditoría/arquitectura y ampliación opcional 64K. La regresión corresponde al working tree actual sobre HEAD, no a un checkout limpio del commit.
- Baseline ejecutado antes de introducir contratos M1: **3.452 passed, 11 skipped, 53 subtests passed**, 231,97 s, exit 0.

Se leyeron los contratos pertinentes de Core V1, SECURITY V1.2, la auditoría MEMORY y MEMORY V1: precedencia/dependencias/lifecycle, identity/scope, modelo de dominio, provenance, sensitivity, puertos, invariantes, decisiones abiertas y gate M1. La auditoría es evidencia preparatoria; sus propuestas no sustituyen al contrato normativo.

Cambios tracked preexistentes, no atribuibles a M1 y preservados:

```text
desktop/tests/application_client.test.cjs
docs/architecture/NOVA_CORE_ARQUITECTURA_V1.md
docs/nova_core_od_05_contexto_v1.md
local_cli/cli.py
local_cli/config.py
local_cli/core/context.py
tests/test_nova_core_phase9_context.py
tests/test_nova_core_phase9_integration.py
```

También se preservaron los archivos existentes de `docs/context64`, `docs/memory_v1`, `tests/memory_v1`, `tests/test_context_64k.py` y los cuatro documentos de referencia. De 63 archivos preexistentes cuyo SHA-256 se capturó, **62 permanecen idénticos**; sólo se amplió `tests/memory_v1/run_regression.py` con una selección M1 adicional. Detalle verificable: [preservation.json](m1_evidence/preservation.json).

## 2. Implementación delimitada

### Core: algebra sin IO

Nuevo `local_cli/core/memory.py`, únicamente stdlib:

- `SubjectId` UUID4 opaco, distinto de `SessionId` y del username/email. La creación de un valor UUID **no persiste ni activa** un perfil.
- `WorkspaceId` SHA-256 versionado de un path **ya canonicalizado y normalizado por el host confiable**. El hash es puro; no resuelve symlinks, equivalencias de case ni rutas físicas del SO. El adapter de identity queda pendiente.
- `MemoryScope` (`GLOBAL_PROFILE` / `WORKSPACE`) y `MemoryAccessScope` inmutables. Predicate limitado al mismo subject y perfil/workspace seleccionado; no hay scope derivado del cwd.
- Cinco `MemoryKind`, siete clases de fuente, seis estados, tres sensibilidades, importancia, validez temporal timezone-aware y errores tipados seguros.
- `MemoryRecord`, `MemorySource`, `MemoryEvidence` y `MemoryProposal` inmutables, con provenance obligatorio y contenido privado omitido del repr por defecto.
- Predicado de elegibilidad por metadata: scope/subject, estado, validez y sensibilidad. No recupera ni inyecta datos.
- Hash exacto del contenido, validator de lineage y bounds explícitos suministrados por el caller. No normaliza/deduplica contenido ni elige quotas.
- `MemoryQuery`, metadata sin contenido/vector, página acotada, IDs ordenados por relevancia y `EmbeddingSpace` declarativo. No confunden relevancia con confianza factual.
- Puertos declarativos: `MemoryIdentityPort`, `MemoryStorePort`, `MemoryLexicalIndexPort`, `SemanticIndexPort`, `EmbeddingPort`, `MemoryPolicyPort`. No tienen adapters ni wiring.

`session_id` sólo es correlación opcional de source evidence; no forma parte de subject/scope ni se recibe para crear una persona. El test con un mock de identity verifica los inputs del contrato entre sesiones/providers, **no demuestra identidad durable tras reiniciar un store real**.

Los estados no elegibles se conservan como historia. El lineage completo suministrado al validator rechaza gaps, ciclos, cross-subject/scope y sucesores ambiguos; no reabre antecesores ni aplica una política de consolidación. Un `CONFLICTED` necesita grupo explícito y no se resuelve por last-write-wins.

### Application: frontera contractual no activa

Nuevo `local_cli/application/memory_admission.py`:

- Host/Application aporta binding tipado: identidad, scope, provenance y clasificación.
- El candidate no confiable sólo aporta kind/text/key.
- Se rechazan campos que intenten fijar subject, scope, fuente, consent, grants, approval o trusted flags.
- La salida es una **propuesta**, nunca un write/delete/supersede ni autorización.
- No se expone por comandos públicos, renderer, CLI, Desktop, AgentSession o Composition Root.

El binding es un valor interno, no una capability infalsificable frente a código Python host ni aislamiento de procesos. La integración futura deberá conservar el origen confiable de esos valores.

### Sensibilidad: alcance real

`SECRET_DENIED` puede describir una propuesta transitoria, pero no es representable como `MemoryRecord`. El validator de sensibilidad exige consentimiento explícito suministrado por el host para contenido clasificado `SENSITIVE`; es una precondición necesaria, **no WritePolicy productiva**.

No se añade detector de secretos, redaction nuevo, UI de consent ni auto-capture. Un registro sensible histórico es representable, pero queda excluido de elegibilidad por defecto. No se afirma que los valores sin clasificación se hayan detectado automáticamente ni que un repr sustituya a SECURITY redaction.

## 3. Gate M1, criterio por criterio

| Criterio normativo | Evidencia ejecutada | Resultado M1 |
|---|---|---|
| Workspace isolation | `test_read_scope_has_no_cross_subject_or_workspace_leak`, scope inválido y hash versionado | PASS — algebra/predicate; store real pendiente |
| Subject separation | rechazo de session/username/email y matriz de subjects | PASS |
| Status eligibility | seis estados, conflicto explícito, intervalos de validez y sensitive por defecto | PASS |
| Supersession lineage | cadena válida, antecesores históricos, gaps/ciclos/forks/cross-scope/subject | PASS — validator puro |
| Source required | fuentes tipadas/no vacías/únicas/correlacionadas; import hash sin fabricar sesión | PASS |
| Secret/sensitive classification contract | secret record denied, sensitive consent precondition, error/repr seguros | PASS — inputs clasificados; no detector |
| Renderer/model no construye trusted scope | whitelist/binding host, 19 campos de spoofing, poisoning permanece texto | PASS — frontera contractual no wireada |
| Algebra estable y sessionId no persona | tipos inmutables, schemas de dominio, puertos explícitos, dependency AST y ausencia de wiring | PASS |

Cobertura por módulos: identity/scope **41**, dominio **79**, admission/ports **67**; total **187 casos nuevos**. La selección dirigida incluye además **6 tests de arquitectura Core existentes**: **193 passed, sin skips/xfail**.

La trazabilidad de los 40 invariantes está en [m1_invariants.json](m1_invariants.json). Sólo se marca lo demostrado a nivel dominio; el enforcement MEMORY runtime permanece diferido. Esto no declara los invariantes M2–M8 completos.

## 4. Pruebas ejecutadas y naturaleza de la evidencia

| Corrida | Tipo | Resultado |
|---|---|---|
| Baseline HEAD selection | Regresión actual Core/Security/contexto/contratos + smokes nativos ya incluidos | 3.452 passed, 11 skipped, 53 subtests; 231,97 s |
| Primer bloque M1 | Unit/contract, fixtures sintéticos; mocks sólo de interfaces | 192 passed; 2,27 s |
| Contratos M1 finales + arquitectura Core | Unit/contract/dependency checks | 193 passed; 2,04 s |
| Regresión final HEAD selection | Misma selección previa + 187 casos M1 | 3.639 passed, 11 skipped, 53 subtests; 216,30 s |
| Repetición de caracterización M0 | Core/contexto real con datos sintéticos; oracle/proxy MEMORY no productivos | 26 casos, 34 sources, 20 mediciones de crecimiento, 45 escenarios complementarios; exit 0 |

Los 11 skips corresponden **a los mismos tests antes/después**: disponibilidad de UI opcional, symlink privilege WinError 1314, gates Electron/Ollama explícitos no activados, bits POSIX no soportados en Windows y caracterizaciones legacy del monitor retirado. [unchanged_skips.json](m1_evidence/unchanged_skips.json) conserva nombres, razones y totales. M1 no añade ni modifica skip/xfail.

No se cambia la selección de exclusiones histórica/host-real del gate HEAD reconciliado. Las suites SECURITY host-real Windows/NTFS y E2E local están separadas y **no se repiten ni recertifican en esta fase de contratos**. Los smokes de subprocess existentes dentro de la regresión sí ejecutan procesos nativos; los tests nuevos M1 no ejecutan tools ni inferencia.

No se ejecutó un modelo local real nuevo: M1 no lo requiere. No se descargaron modelos, no se cambió GPU/provider/configuración global y no se hicieron llamadas de inferencia cloud/local para aparentar evidencia de inteligencia.

No hubo tests fallidos. Una lectura auxiliar de XML inicialmente tuvo un error de sintaxis PowerShell al concatenar el path; se corrigió la lectura, sin modificar producto, tests ni sus resultados.

## 5. Matriz 4K/8K/16K/32K/64K y métricas

Se reutiliza **sin modificar** el harness M0/64K existente. Son ventanas sintéticas `MANUAL_UNVERIFIED_SYNTHETIC_PRESET` y estimación `utf8_bytes_div_3`, no capacidad certificada de un modelo/tokenizer real.

| N | Mediciones de crecimiento | Escenarios complementarios | Proxy MEMORY relevante | Cap de referencia* | Historial 10k: mensajes preparados | Mediana prepare 10k |
|---|---:|---:|---:|---:|---:|---:|
| 4.096 | 4 | 9 | 99 tokens | 327 | 22 | 76,432 ms |
| 8.192 | 4 | 9 | 99 tokens | 655 | 49 | 76,968 ms |
| 16.384 | 4 | 9 | 99 tokens | 1.024 | 93 | 93,079 ms |
| 32.768 | 4 | 9 | 99 tokens | 1.024 | 181 | 86,722 ms |
| 65.536 | 4 | 9 | 99 tokens | 1.024 | 387 | 85,196 ms |

*Cap del oracle para el escenario pequeño `memory_synthetic`; no es cuota elegida ni retrieval MEMORY activo. Los casos sin espacio disponible pueden producir cap cero.

En las cinco ventanas:

- Current user exacto, input canónico sin mutaciones, presupuesto/prompt deterministas.
- Usuario pequeño/mediano/grande, historial grande, retrieval, ToolResults y proxy MEMORY sintético evaluados.
- Ausencia de recuerdos relevantes o de espacio opcional → **0 tokens proxy**, sin llenar artificialmente un cap.
- El proxy relevante conserva 99 tokens incluso en 64K; no aumenta la cantidad de recuerdos por ventana.
- Prompt estimado más reservas/output/safety permanece dentro de N; input obligatorio demasiado grande devuelve `CONTEXT_BUDGET_EXCEEDED`, no recorte silencioso del usuario.
- Historial creciente no equivale a transcript completo enviado: en 64K/10k quedan 387 de 10.008 mensajes en el fixture combinado. El costo de preparación legacy sigue relacionado con el historial, con peak traced cercano a 22,58 MB para 10k. No se optimiza en M1.

Las latencias son descriptivas de tres muestras por tamaño, no umbrales M8 ni benchmark de MemoryStore. Se conserva esta repetición como evidencia nueva, sin sobrescribir las mediciones previas M0/64K.

### Lexical/semantic existente, sin embeddings MEMORY

- Lexical legacy: `SkillsLoader` keyword/substring; coincidencia case-insensitive 1, paráfrasis sin match 0, embedding calls 0. No es recall personal MEMORY.
- RAG legacy: SQLite + cosine scan Python; fixture de dos chunks, vectors sintéticos 2D y top-k 2. Modelo configurado legacy `all-minilm`, **no recomendado/seleccionado para MEMORY** y no cargado.
- RAG deshabilitado: embedding calls 0. Backend no disponible: error `RAG_EMBEDDING_UNAVAILABLE`; fallback lexical RAG existente ausente.
- La caracterización conserva el hallazgo de chunk documental eliminado todavía recuperable en el store RAG legacy; no lo reinterpreta ni lo corrige dentro de M1.
- Calidad de recall/correction/deletion MEMORY productiva, dimensiones/latencia/calidad de un modelo embedding real: **NOT_IMPLEMENTED / UNKNOWN**, con métricas null. El corpus etiquetado y los validators no sustituyen esas pruebas.

Reporte íntegro: [m0_characterization.json](m1_evidence/m0_characterization.json).

## 6. Archivos de esta fase

Nuevos:

```text
local_cli/core/memory.py
local_cli/application/memory_admission.py
tests/memory_v1/m1_fixtures.py
tests/memory_v1/test_m1_identity_scope.py
tests/memory_v1/test_m1_domain.py
tests/memory_v1/test_m1_admission_ports.py
docs/memory_v1/m1_resultados.md
docs/memory_v1/m1_manifest.json
docs/memory_v1/m1_invariants.json
docs/memory_v1/m1_evidence/*   (13 snapshots de ejecución/preservación)
```

Único archivo preexistente modificado por M1: `tests/memory_v1/run_regression.py`, modo dirigido `m1` adicional. Los modos/exclusiones históricos y la higiene de perfil privado permanecen iguales. Como `m0` ya seleccionaba toda la carpeta de tests, futuras corridas de ese modo también recogerán los nuevos tests M1; **las evidencias M0 anteriores siguen siendo históricas y no se reetiquetan**.

## 7. Reproducción

Desde la raíz del repositorio, usando Python con pytest disponible y un **directorio de salida nuevo** en cada corrida:

```powershell
$taskMemoryPython = 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe'
& $taskMemoryPython -B -m tests.memory_v1.run_regression --mode head --output '<fresh-output>/before'
& $taskMemoryPython -B -m tests.memory_v1.run_regression --mode m1 --output '<fresh-output>/domain'
& $taskMemoryPython -B -m tests.memory_v1.run_regression --mode metrics --output '<fresh-output>/characterization'
& $taskMemoryPython -B -m tests.memory_v1.run_regression --mode head --output '<fresh-output>/after'
```

El harness utiliza HOME/USERPROFILE/state/temp privados para el proceso de tests, whitelist de variables de sistema y no auto-load de pytest plugins. No lee conversaciones/recuerdos privados ni perfiles de Nova reales. Los comandos exactos de cada corrida y exit codes están en `m1_evidence/*_run.json`.

Las evidencias originales, incluyendo JUnit XML, permanecen bajo:

```text
C:/Users/joseh/.codex/visualizations/2026/10/03/01a10197-de3b-77b3-b73d-045d080c7561/
  m1_before/
  m1_domain_1/
  m1_domain_2/
  m1_after/
  m1_m0_metrics/
```

Se copian sólo logs/metadata/reportes sintéticos nuevos a docs. No se copian profiles/stores temporales. Sus SHA y los de las fuentes/documentos están en los manifests; normalizar finales de línea/indentación de los snapshots no reescribe los originales.

## 8. UNKNOWN, deuda y OPEN DECISIONS

No bloqueantes para el gate M1, explícitamente **no implementados/verificados**:

- Persistencia real de SubjectId; canonicalización física por OS/aliases/workspace identity. El hash de entrada normalizada no prueba ese adapter.
- Store SQLite/FTS, transacciones/recovery/locks/migrations, persistencia de sources y deletions/no-resurrection: M2+.
- User control y rutas explícitas remember/correct/forget, detector/redaction/consent real: M3+.
- Recall/capsules/TAC/AWC, separación activa RAG/MEMORY y filtrado pre-index: M4+.
- Índice semantic/embedding availability operacional/fallback/hybrid/calidad real: M5+. Los puertos no son backends.
- Extraction/consolidation/conflict resolution/maintenance, subagents, privacidad y E2E de runtime: fases posteriores.
- Nueva ejecución nativa Linux/macOS o recertificación SECURITY host-real: no realizada aquí. La certificación host-real SECURITY conserva Windows 11 + NTFS + `HOST_UNISOLATED`, sin sandbox/process isolation; Core conserva sus capacidades multiplataforma previas, sin afirmar una nueva corrida remota ni ampliar soporte físico por añadir algebra multiplataforma.
- No se afirma protección del modelo frente a prompt injection a partir de un fixture de texto: sólo se demuestra que el candidate no puede fijar autoridad/scope en esta frontera.

MEM1-OD-01..07 continúan **OPEN**, sin resolución anticipada: backend semantic, modelo embedding, umbrales AUTO_SAFE, quotas finales, retención física EPISODE, cifrado at-rest y umbrales READY. Ninguna requiere decidir antes de cerrar los contratos M1.

No se observaron regresiones nuevas en la selección ejecutada. El costo O(historial) y los hallazgos legacy conservados no se “arreglan” en esta fase ni se convierten en métricas de calidad MEMORY.

## 9. Cierre

**M1 = PASS**: entregables de dominio/puertos y los siete grupos contractuales del gate están respaldados por pruebas sintéticas reproducibles. Core V1/SECURITY V1.2 productivos no se modificaron, salvo contratos MEMORY nuevos sin wiring; los cambios preexistentes se preservan.

No es `MEMORY_IMPLEMENTED` ni `NOVA_MEMORY_V1_READY`.

Siguiente fase lógica: **M2 — Durable MemoryStore + FTS5 + migrations**, **no implementada**. Sin commit ni push.
