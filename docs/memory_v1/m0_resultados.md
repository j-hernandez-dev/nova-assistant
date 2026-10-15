# M0 — Baseline, taxonomy y evaluation harness

Fecha: 2026-10-06. Estado: **PASS para M0 exclusivamente**.

MEMORY no está implementada ni READY. No se inició M1. No hay cambios de producto,
Core V1, SECURITY V1.2, schemas públicos, dependencias o workflow. No commit/push.

## 1. Baseline y autoridad

Branch `main`, HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`
(`ci: align unsupported filesystem gates across platforms`). Nova `0.12.6`;
Python `3.14.6`, Windows 11 build 26200, volumen local NTFS.

Tags anotados: `nova-core-v1-stable` (commit `158b60effa484cd34a58b991f3ee4ca3f808d924`)
y `nova-security-v1.2-ready` (commit `26dc87786d8ad1c1d879255a068c7fb50a25e6f2`);
objetos de tag y hashes SHA-256 de los cuatro documentos están en
[m0_manifest.json](m0_manifest.json).
No se movieron tags ni HEAD.

Antes de actuar, el working tree no tenía modificaciones tracked. Ya estaban
untracked `AUDITORIA_MEMORIA_NOVA_V1.md` y `NOVA_MEMORY_ARQUITECTURA_V1.md` en
`docs/architecture`; se conservaron byte a byte. Al terminar sólo se añadieron
`tests/memory_v1/` y `docs/memory_v1/`.

Se leyeron Core V1, SECURITY V1.2, la auditoría y la arquitectura MEMORY V1.
Se contrastaron sus afirmaciones con código y pruebas de HEAD. El gate aplicable
es §37 M0: «baseline reproducible y dataset suficientemente definido para probar
M1–M8». M0 no exige un E2E con modelo local real. M5/M8 deberán aportar esa
evidencia: un adapter scripted o embeddings 2D no la sustituyen.

El alcance SECURITY permanece Windows 11 + local NTFS + `HOST_UNISOLATED`.
No existe sandbox/process isolation; M0 no certifica SECURITY en Linux/macOS.
No se modificaron las exclusiones históricas/legacy de CI ni la evidencia S0–S8/READY.

## 2. Metodología

- [O]: código/configuración/contratos leídos.
- [T]: ejecución controlada sobre fixtures sintéticos y stores privados.
- [I]: inferencia técnica, identificada como tal.
- `UNKNOWN` / `NOT_IMPLEMENTED`: sin evidencia o capacidad aún inexistente.

Las etiquetas gold describen resultados esperados por MEMORY V1 futura. No son
MemoryRecords existentes, escrituras autorizadas, outcomes de un LLM ni nuevas
policies. Las clases de evaluación se quedan en tests: no se crearon contratos
de dominio/puertos públicos que corresponden a M1.

## 3. Taxonomy, identidad, scope y provenance

[corpus_v1.json](../../tests/memory_v1/fixtures/corpus_v1.json) contiene 34 ejemplos
de fuente, 26 casos y cuatro timelines: corrección, delete/rebuild, conflicto
ambiguo y repetición. `schemaVersion=1`, `datasetVersion=m0-synthetic-v1`.

Incluye los cinco kinds normativos: PREFERENCE, SEMANTIC_FACT, WORKSPACE_FACT,
EPISODE y PROCEDURE explícita. Distingue RAG_DOCUMENT, TRANSCRIPT, SECURITY_AUDIT,
DERIVED_CACHE, WORKING_STATE, OPERATIONAL_SUMMARY e instrucciones confiables.
Un chunk documental o summary no se etiqueta como memoria personal.

Se fijaron dos `subjectId` UUID sintéticos, dos `workspaceId` de 64 caracteres hex
y dos session IDs distintos. Son fixtures, **no** implementación del algoritmo
de identidad, canonicalización de paths o composición de scope confiable.

Las siete source classes normativas están representadas, con session/turn/message,
timestamp y locator sintéticos. Hay lineage de corrección/migración, ejemplos de
tool/assistant/hijo que no adquieren autoridad global, una preferencia sensible
ficticia y un credential dummy explícitamente no real. No se leyó material sensible
del usuario ni se cargó `.env`.

El validador rechaza subject inválido/session como subject, binding de workspace
inválido, provenance incompleta, lineage roto, gold cross-scope y procedure no
explícita. Los casos incluyen paráfrasis ES/EN, irrelevancia/abstención, conflicto,
corrección, expiración, borrado/no-resurrección y separación de stores.

## 4. Contrato de métricas

[metrics_contract_v1.json](../../tests/memory_v1/fixtures/metrics_contract_v1.json)
define unidades, denominadores y representación de UNKNOWN. El evaluator puro
`evaluation.py` puntúa observaciones suministradas; no busca ni guarda recuerdos.

| Métrica | Definición de evaluación |
|---|---|
| precision@k | IDs gold recuperados / k |
| precision_returned | IDs gold / IDs retornados; null si no retorna |
| recall@k | IDs gold recuperados / total gold; null si gold vacío |
| scope_leaks | IDs seleccionados de otro sujeto/workspace no elegible |
| forbidden_hits | IDs seleccionados prohibidos por el caso |
| resolution_correct | Resolución exacta; conflicto ambiguo exige CLARIFY |
| abstention_correct | Ranking vacío cuando gold está vacío |
| Context cost | Contador estimado real Core, categorías y presupuesto |
| Tiempo/allocations | Mediana de tres prepares sin tracing; peak trazado aparte |

Corrección, estado activo/lineage, delete en derivados y no-resurrección tras
rebuild/reopen también quedan definidos como métricas de estado futuras. No se
implementan esas operaciones en M0. Los tests negativos detectan el ranking con
la versión antigua, un conflicto respondido como certeza y un delete retornado.

El self-check con gold es **ORACLE_SELF_CHECK_NOT_PRODUCT_QUALITY**: comprueba
la aritmética del evaluator, no demuestra recall. Incluso el oracle puede tener
precision@k menor que 1 si hay menos de k gold; precision_returned lo distingue.
IDs desconocidos/duplicados invalidan la observación, no producen un éxito.

Las métricas productivas MEMORY son null con motivo `NOT_IMPLEMENTED`. No se
eligieron umbrales de calidad, AUTO_SAFE, quotas ni latencia READY.

## 5. ContextManager real y TAC de referencia

Se midió la implementación Core ejecutada con schemas sintéticos, system/base,
project/skills, historia creciente, RAG tagged, current user Unicode y un grupo
de dos tool calls/results. No hubo inferencia. El mismo dataset conserva su
canónico antes/después; `_context_*` no llega al provider y los IDs de tools
permanecen completos. Overflow obligatorio produce `CONTEXT_BUDGET_EXCEEDED`;
orphan actual produce `CONTEXT_TOOL_CONTINUITY`, no un resultado inventado.

| Ventana | 20 mensajes históricos (ms) | 200 (ms) | 2000 (ms) | 10000 (ms) |
|---|---:|---:|---:|---:|
| 4K | 2.839 | 4.207 | 18.390 | 80.453 |
| 8K | 2.942 | 4.204 | 19.683 | 83.336 |
| 16K | 4.042 | 4.945 | 21.011 | 87.718 |
| 32K | 3.949 | 5.781 | 17.920 | 81.234 |

[T] Corrida final ligada al SHA-256 del corpus definitivo; mediana de tres
samples, no benchmark de modelo. Se preservaron otras dos corridas independientes;
a 10000 mensajes sus rangos fueron 76.099–79.043 y 73.771–83.173 ms. Peak
trazado durante prepare: aproximadamente 1.39 MB a 20, 1.77 MB a 200, 5.59 MB a
2000 y 22.58 MB a 10000. No incluye RAM total del proceso, source/original ya
creados, KV cache ni VRAM. No se introduce un umbral PASS de rendimiento M8.

Todas las ventanas preservan el current user exacto. En historia larga quedan
aproximadamente 22/49/93/181 mensajes preparados según ventana; la entrada
canónica completa sigue presente. [I/O] El acotamiento del prompt no evita el
trabajo repetido de serializar/copiar/clasificar el historial completo.

Tokens usan `utf8_bytes_div_3`, `estimated=true`; presets manuales sin inventar
límites del provider/host: `selection_verified=false`. 32K es caracterización
adicional solicitada, no recomendación ni certificación de capacidad del equipo.

El oracle separado de §19 calcula ceilings MEMORY 327/655/1024/1024 cuando hay
espacio y cero cuando el material obligatorio consume A. Es sólo aritmética de
evaluación: no se añadió categoría `memory`, split 60/40 ni capsule al producto.
Los tokens RAG reales del Core pueden superar 1024 en 16K/32K: eso no prueba un
fallo del ceiling MEMORY porque aún no existe esa categoría. Cap Core retrieval
y oracle MEMORY no son el mismo contrato ni reservas aditivas.

## 6. Baseline legacy preservado

[m0_legacy_stores.json](m0_legacy_stores.json) inventaría 24 stores/estados y sus
paths de código, scopes, formatos, lectura/escritura, eliminación y reinicio.
No es inventario de contenidos reales del disco del usuario.

[T] Caracterizaciones reproducidas con almacenes privados:

- Autosave: 450 mensajes de entrada, 400 restaurados, 21812 bytes. Snapshot
  manual: 450 restaurados, 24190 bytes. Reinstanciar servicio conserva formatos.
  Save/load medidos 7.521/14.396 ms en una muestra; no generalizar como benchmark.
  El header incluye workspace temporal: el tamaño puede variar entre corridas.
- Dos paths sintéticos `Alpha_One`/`Alpha-One` colisionan en el slug legacy.
  Un snapshot manual por key puede restaurarse desde otro workspace del state
  root. Esto no implementa ni certifica separación MEMORY por sujeto/proyecto.
- Doce repeticiones y dos assertions contradictorias permanecen sin consolidar.
  Clear elimina autosave, pero conserva snapshot y flight recorder. No es forget.
- Una principal por coordinator; nueva instancia inicia base/nuevo session ID.
  Resume explícito restaura mensajes, no Turns/grants/operaciones. Se simuló
  reapertura por nuevas instancias sobre disco, no cierre real Electron/OS.
- Cambio idle de modelo/provider conserva historia; rebind de workspace también.
  El input anterior llega a una generación posterior. Provider scripted sólo
  como sonda de plumbing; no se presenta como calidad de Ollama real.
- Hijo sin tools recibe sólo la tarea delegada, no historia privada implícita del
  padre. No crea conversation store propio en el fixture. No es aún un test de
  autorización de MemoryStore: tal store no existe.
- Knowledge explícito sigue entrando como system obligatorio sin tag retrieval.
  Artifact sintético de 30000 chars provoca overflow en 4K. No se corrigió esta
  limitación legacy ni se reutilizó como futura MemoryCapsule.

## 7. Lexical, semantic y ausencia de embeddings

[T/O] Lexical existente: SkillsLoader, keyword/substring case-insensitive sin
embeddings. Match `PARSER` positivo; paráfrasis sin trigger no recupera skill.
No es búsqueda lexical conversacional/personal ni FTS MEMORY.

[T/O] Semantic documental existente: RAGService → LegacyProjectRetrieval →
RAGEngine, SQLite real y cosine scan Python. Fixture de dos chunks, top-k=2;
vectores 2D sintéticos, scores 1/0 según datos controlados. Query 1.719 ms incluye
adapter/SQLite, pero **no** latencia de un embedding model. El default de código
es `all-minilm`; dimensión/disponibilidad/calidad real permanecen UNKNOWN.

RAG off no pide embeddings. Backend ausente reporta `RAG_UNAVAILABLE`; embedding
que falla reporta `RAG_EMBEDDING_UNAVAILABLE` y no inyecta contexto. No se
demuestra un fallback lexical RAG: hoy está ausente. Borrar/reindexar fuente
sintética sigue devolviendo su chunk anterior; evidencia preservada, no arreglada.

No se añadieron SQLite/FTS MEMORY, motor lexical nuevo, semantic adapter MEMORY,
extracción, consolidation, auto-download, reranker ni nuevas rutas de recall.

## 8. Gate M0, por criterio

| Criterio §37 | Resultado | Evidencia |
|---|---|---|
| Fixtures versionados sintéticos | PASS | corpus v1 + validación negativa |
| Prefs/facts/conflicts/scopes/deletes | PASS | 26 casos, cuatro timelines |
| Context 4K/8K/16K | PASS | 16 mediciones, incluye 32K adicional |
| subjectId/workspaceId fixtures | PASS | UUID/64-hex fijos, sesiones distintas |
| Stores legacy a preservar | PASS | Inventario 24 entries + caracterización |
| Metrics contract | PASS | Fórmulas, negativos, UNKNOWN explícito |
| Matriz inicial MEM1-INV | PASS | 001–040, trazabilidad y fases pendientes |
| Regresión relevante Core/SECURITY | PASS | Before 3314 / after 3359 passed |

[m0_invariants.json](m0_invariants.json) conserva todos los invariantes. Su campo
`memoryEnforcement=DEFERRED_NOT_IMPLEMENTED` impide convertir fixtures o tests de
Core/RAG en certificación de MEMORY. Gate M0 cerrado ≠ gates M1–M8 cerrados.

## 9. Pruebas y fallos conservados

| Corrida | Resultado |
|---|---|
| Baseline inicial, host restringido | 7 failed, 3307 passed, 11 skips, 53 subtests; 288.53 s |
| Baseline nativo antes de cambios | 3314 passed, 11 skips, 53 subtests; 207.94 s |
| Primer bloque evaluación/contexto | 39 passed |
| Legacy inicial | 43 passed |
| Legacy con cleanup incorrecto | 1 failed, 44 passed |
| Legacy corregido / M0 completo | 45 passed |
| Primera regresión post-M0 | 3359 passed, 11 skips, 53 subtests; 210.53 s |
| Regresión final, runner versionado/corpus definitivo | 3359 passed, 11 skips, 53 subtests; 214.66 s |
| Runner versionado M0 inicial | 45 passed; 0.57 s |
| Runner versionado M0, corpus definitivo | 45 passed; 0.63 s |
| Harness de métricas | Tres corridas, 26 casos/16 mediciones cada una; última con corpus definitivo |

M0: 21 unit de dataset/evaluator, 18 contract/context y seis integrations con
stores/context/backend real más providers/embeddings mock. La regresión actual
incluye el smoke nativo de procesos/PowerShell; no se repitió el gate SECURITY
host-real separado de symlinks/NTFS ni un E2E de modelo local, no exigidos por M0.
Los 11 skips existentes se conservaron; los tests M0 no introducen skips/xfail.

Los siete fallos iniciales se enumeran sin ocultarlos en el manifest/log. Se
observaron WinError 5 de hardlink, rechazos broker alias/handles, fallo de launch
(no timeout) y un fixture HOME/USERPROFILE incoherente. [T] Los mismos tests
pasaron en contexto nativo con perfil privado coherente, sin cambiar assertions,
timeouts o producto. [I] Restricción del host explica plausiblemente seis; no se
aisló por separado cada causa OS. HOME distinto de USERPROFILE fue HARNESS_BUG.
Un error de impresión cp1252/Unicode del runner inicial y warning de teardown
pyreadline se registraron como problemas de reporting, no outcomes de producto.

El fallo intermedio M0 fue HARNESS_BUG: se asumió un handler CloseSession para
cleanup aunque HEAD expone DTO y rechaza el comando. Los Turns ya habían
terminado; se retiró esa suposición de cleanup, sin eliminar garantías MEMORY
ni cambiar lifecycle Core. No se implementó una feature adyacente.

En revisión manual final se corrigió sólo una inconsistencia sintética de
provenance: el fixture SYSTEM_MIGRATION ahora conserva la assertion de `fact-os`
y referencia esa fuente, en lugar de asociar texto de otro hecho a una preferencia
de idioma. Se añadió una assertion de evaluación dentro de un test ya existente.
Las primeras dos mediciones conservan su corpus SHA-256 original, no se editan.
`m0_characterization_final.json`, `m0_tests_final.json` y `baseline_final.json`
corresponden al corpus definitivo; no se presentan los fixtures preliminares
como evidencia de ese hash. La corrida HEAD final también verifica el runner
versionado y mantiene las mismas exclusiones de CI.

No quedó demostrada una regresión nueva del producto. No se corrigieron ni
reinterpretaron los gaps legacy de la auditoría como si fueran MEMORY resuelta.

## 10. Reproducción

Desde el root del repo, con el runtime del proyecto y pytest instalado:

```powershell
python -B -m tests.memory_v1.run_regression --mode m0 --output "$env:TEMP/nova-m0-new-tests"
python -B -m tests.memory_v1.run_regression --mode metrics --output "$env:TEMP/nova-m0-new-metrics"
python -B -m tests.memory_v1.run_regression --mode head --output "$env:TEMP/nova-m0-new-head"
```

Cada directorio debe ser nuevo. El runner no sobreescribe evidencia; conserva
logs/JSON/JUnit y usa perfil/config/state/temporales privados, sin heredar secrets
ni cargar configuración global. `head` mantiene exactamente las exclusiones CI
vigentes, incluidas las cuatro caracterizaciones FS Windows-specific en POSIX;
no cambia workflow. Un host restringido puede no ejecutar los contratos OS.
No añadir retry/skip para convertir esa limitación en PASS.

Directo, cuando el entorno ya está aislado:

```powershell
python -B -m pytest -q tests/memory_v1 -p no:cacheprovider
python -B -m tests.memory_v1.run_m0 --output <new-report.json>
```

En esta tarea se usó Python absoluto
`C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe`.
Los comandos completos ejecutados están en los JSON de evidencia. Raw JUnit y
outputs intermedios se conservan en el directorio privado `memory_m0_468d213`
del workspace de artefactos de Codex; los logs relevantes se copiaron aquí sin
sobreescribir las corridas fallidas. No se descargaron modelos ni alteró GPU.

## 11. UNKNOWN, deuda y OPEN DECISIONS

UNKNOWN: recall/calidad/conflict/correction con modelo local real, dimensión y
latencia de embeddings reales, tokens del modelo, ventanas verificadas del
provider/host, RAM/VRAM/KV y ejecución de M0 en Linux/macOS desde este host.
El workflow previo sigue intacto y multiplataforma; no se declara una nueva
corrida remota ni certificación MEMORY de otros OS.

Pendiente por fase, no omitido: dominio/identidad confiable (M1), store durable,
FTS/migrations/tombstones (M2), controles remember/correct/forget (M3), recall/TAC
productivo (M4), semantic (M5), extracción/consolidation/subagentes (M6), eficiencia
(M7), evaluación real/READY (M8). Se deben conservar y reevaluar los gaps legacy
en el alcance de la fase normativa correspondiente, sin reabrir SECURITY aquí.

Siguen **OPEN**, sin decisión arbitraria: MEM1-OD-01 backend semantic; OD-02
embedding model; OD-03 AUTO_SAFE; OD-04 quotas finales; OD-05 retención física
EPISODE; OD-06 cifrado at-rest opcional; OD-07 umbrales READY. Ninguna bloquea M0;
`all-minilm`, 20k/128 MiB y cifras orientativas no se promovieron a decisiones
cerradas por estas mediciones.

Siguiente fase lógica: **M1 — Domain contracts: identity, scope, provenance,
validity**, únicamente cuando el usuario la solicite. No implementada.
