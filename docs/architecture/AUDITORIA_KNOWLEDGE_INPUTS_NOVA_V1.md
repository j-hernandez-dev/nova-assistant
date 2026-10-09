# Auditoría previa — Etapa 4: Nova Knowledge Inputs V1

Fecha: 2026-10-07. Estado de esta tarea: **AUDIT_COMPLETE**.

Este documento es evidencia técnica y preparación para revisión humana. **No es una arquitectura normativa, una implementación de Knowledge Inputs ni una nueva certificación READY.** Las direcciones futuras están marcadas `[P]`; no fijan fases, nombres definitivos, schemas, formatos soportados ni decisiones de producto.

## 1. Resumen ejecutivo

Nova no parte de cero, pero tampoco tiene hoy un sistema completo de Knowledge Inputs. Existen cuatro caminos distintos:

1. `[O/T]` Texto del usuario → `SubmitUserInput` → Turn → contexto presupuestado → modelo.
2. `[O/T]` Tools `read`/`glob`/`grep` y `web_fetch` → ToolRuntime/SECURITY → ToolResult → continuidad del agente. Son lecturas concretas; no crean por sí mismas un Source/Document indexado.
3. `[O/T]` Directorio de proyecto → RAGEngine → SQLite + embeddings Ollama → RAGService → contexto documental temporal. Está integrado en Application, pero conserva limitaciones del algoritmo anterior a MEMORY.
4. `[O/T]` `/knowledge save/load/list/delete` → repositorio explícito de notas/artifacts. `save` guarda el último mensaje del assistant; **no es un importador de documentos o attachments**.

`[O]` MEMORY V1 es un quinto dominio separado: recuerdos persistentes con subject/workspace, policy, correction/forget y cápsula acotada. **Memory != Knowledge/RAG.** Compartir presupuesto o patrones técnicos no implica compartir autoridad, tablas, namespace ni lifecycle de eliminación.

Hallazgos principales:

- `[O]` No se encontró una entrada integrada de attachments/uploads, un Source/Document versionado, búsqueda web general, parser PDF/documental, OCR ni verificación de citas. Los DTOs y la UI normales envían texto, no referencias documentales.
- `[O/T]` `web_fetch` sí tiene adquisición HTTP(S) productiva y mediada: PUBLIC_ONLY, DNS/redirects comprobados, TLS verificado y límites operacionales. Su extracción es un eliminador lineal de `<…>`, no un extractor HTML/JSON/XML consciente del formato. Una prueba sintética mostró pérdida de contenido JSON y conservación de texto de script/style.
- `[O/T]` RAG es productivo pese al nombre `LegacyProjectRetrieval`. Su índice no registra modelo/digest/dimensión/EmbeddingSpace; cambiar de modelo puede conservar vectores antiguos. La comparación no rechaza dimensiones diferentes.
- `[O/T]` RAG no elimina chunks de fuentes borradas o vaciadas. El SHA por archivo sirve para detectar modificaciones, no como contrato completo de versión/provenance presentado al modelo.
- `[O]` S3 brokered gobierna las tools del agente en Windows/NTFS. El scan RAG, la persistencia Knowledge y el visor Desktop usan otros caminos de I/O. No deben recibir automáticamente los claims de S3.
- `[T]` Regresión dirigida del HEAD: **313 PASS / 0 FAIL / 0 SKIP**. No se ejecutó una regresión HEAD completa ni inferencia real. Los fallos de CI comunicados previamente siguen siendo deuda; esta auditoría no los corrige ni los convierte en PASS.

Conclusión: hay bases reutilizables para adquisición, lifecycle y admisión de contexto; faltan contratos específicos de fuente, extracción, vigencia, aislamiento de datos frente a instrucciones y citas. **La siguiente acción es revisión humana de esta auditoría y sus decisiones abiertas, no implementación.**

## 2. Baseline real y alcance de la inspección

### 2.1 Git, plataforma y runtimes

| Elemento | Observación directa |
| --- | --- |
| Repositorio | `C:/Users/joseh/Downloads/nova-local-cli/nova-assistant` |
| Branch | `main` |
| HEAD | `717a24218dea7fb60d8b630896d653e39091bc7b` — `merge: integrate remote main` |
| Working tree inicial | Limpio: `git status --short` sin salida; no modificaciones ni untracked reportados |
| Versión Python package | `local-cli` / Nova `0.12.6`; requisito Python `>=3.10` |
| Python de esta auditoría | CPython `3.14.6`, Windows AMD64 |
| SQLite del runtime | `3.50.4` |
| pytest | `9.1.1` |
| Node disponible | `v24.19.0`; no se ejecutó build/E2E Desktop |
| Plataforma observada | `Windows-11-10.0.26200-SP0` |
| Volumen del checkout | `C:`, `NTFS`, `Fixed`; no certificación nueva de otros volúmenes/OS |
| Estado MEMORY publicado | `MEMORY_CORE=READY`; `SEMANTIC_PROFILE=NOT_CERTIFIED` |

No se midió GPU, RAM/VRAM, residencia de modelos ni hardware mínimo. No se modificó GPU, configuración, modelos ni entorno global.

| Tag | Objeto annotated | Commit objetivo |
| --- | --- | --- |
| `nova-core-v1-stable` | `97f41c6dab89ee59332875bb8d89c29620b52156` | `158b60effa484cd34a58b991f3ee4ca3f808d924` |
| `nova-security-v1.2-ready` | `e5bea6a4c2c559a1f5a2f8824316a83b548b2533` | `26dc87786d8ad1c1d879255a068c7fb50a25e6f2` |
| `nova-memory-v1-ready` | `fa6b2f7898692ddc6cec77a4d971dbc395b764a6` | `9911ad4ca0fc13edfef49e84441a759d35cbefda` |
| `nova-memory-v1.1-ready` | `6a48c5252e40986ecf4180138d9d56bc519b3e49` | `3678d5b597a888b743e90d26efda6219943d58df` |

`[O]` El mensaje del tag adicional dice «Nova Memory V1 READY on Core V1; Semantic Profile Not Certified». Su existencia no demuestra una nueva arquitectura MEMORY 1.1 ni Knowledge certificado. `git diff 3678d5b… HEAD --stat` muestra únicamente el cambio `LICENCE → LICENSE` y contenido de licencia. `git diff nova-memory-v1-ready HEAD -- local_cli tests docs/architecture docs/memory_v1` no muestra diferencias. El HEAD de esta auditoría y el HEAD precommit registrado dentro de READY no son el mismo identificador; se preserva esa diferencia histórica.

### 2.2 Documentos normativos y hashes observados

SHA-256 de los **bytes del working tree**; no se afirma equivalencia byte-a-byte con blobs Git normalizados por EOL:

| Documento/artefacto | SHA-256 |
| --- | --- |
| `docs/architecture/NOVA_CORE_ARQUITECTURA_V1.md` | `a5711f372cd9ac9bee5ac800e638665e2e06cdb4405974c2cd12c14587715792` |
| `docs/architecture/NOVA_SECURITY_ARQUITECTURA_V1_2.md` | `b13814a0f1c99528ab4f4d2f5c874dacdc1017c8f3f13b1053c90c67eb848147` |
| `docs/architecture/AUDITORIA_MEMORIA_NOVA_V1.md` | `3fb67df88dae2428217e937fc8d890a3bcdf5c80524f16c207a2d8ef8c10cc80` |
| `docs/architecture/NOVA_MEMORY_ARQUITECTURA_V1.md` | `886a4788d55282aefbbc776344ec507b779519e15ea940dcad62ea24ef57e9cd` |
| `docs/memory_v1/memory_v1_ready_manifest.json` | `ff1185bab2c45d0f1e33e67a80997e20d0281792dc01684fdf3214cc9a6e4c3c` |

`[O]` El hash actual de arquitectura MEMORY coincide con el que referencia su manifest READY. Se consultaron los manifests READY de MEMORY y SECURITY y las secciones pertinentes, pero **no se reejecutó ni revalidó toda la cadena histórica de hashes/gates**. READY previo es evidencia preservada de su alcance publicado, no un atajo para certificar Knowledge.

Precedencia aplicada: Core para lifecycle/contratos/budgeting; SECURITY V1.2 para permisos, brokers, red y procesos; MEMORY para su dominio e integración aprobada. Las auditorías históricas aportan contexto, no prevalecen sobre esos contratos o el código actual. Las propuestas de extensión de Core no cuentan como implementación existente.

### 2.3 Estado de tests y CI

- `[T]` Campaña dirigida nueva: 313 tests, 0 fallos, 0 errores, 0 skips; salida pytest `313 passed in 15.11s`.
- `[T]` Caracterización adicional con archivos/SQLite sintéticos y embeddings deterministas: terminó con exit code 0; es observación del comportamiento, **no un gate de calidad semántica**.
- `[O]` CI nativo Core y contratos MEMORY está definido en tres OS; host-real SECURITY y perfil MEMORY Windows/NTFS tienen jobs separados. Los workflows excluyen las suites S0/legacy ya clasificadas; esta auditoría no las reintroduce.
- Evidencia remota facilitada por el usuario: fallo común del hash de `run_m8_qwen4_chat7b.make_freeze`, más una aserción wall-clock de timeout en macOS. No se consultó GitHub ni se verificó la corrida exacta de este HEAD.
- **CI completo de HEAD: NO VERIFICADO aquí.** Una selección dirigida verde no convierte en verdes los jobs remotos fallidos.

## 3. Metodología y catálogo de evidencia

### 3.1 Etiquetas

- `[O]`: observación directa de código, configuración, contrato o artefacto preservado.
- `[T]`: prueba controlada ejecutada durante esta auditoría.
- `[I]`: inferencia técnica con fundamento, no demostración completa.
- `[P]`: propuesta para una futura decisión/arquitectura; no comportamiento actual.
- `UNKNOWN / NO VERIFICADO`: falta evidencia suficiente.

Estado de etapas del dataflow: `EXISTS` = camino implementado para el alcance indicado; `PARTIAL` = existe una parte, heurística o integración incompleta; `MISSING` = no se encontró camino integrado; `NOT_APPLICABLE` = etapa no necesaria para ese camino concreto. `EXISTS` **no equivale a calidad certificada**.

### 3.2 Procedimiento y límites

Se inspeccionaron Git, dependencias, fuentes Python y Desktop (`src`, `electron`, `shared`, tests), DTOs, composición, contratos y tests relevantes. Las búsquedas de ausencia abarcaron esos árboles de producto, no caches/generated bundles/dependencias vendorizadas como si fueran capacidades de Nova.

Se siguieron los callers de las implementaciones: un método aislado, una etiqueta vision, una clase `Legacy…` o un `search` de modelos no se consideraron prueba de una capability Knowledge integrada.

No se leyeron conversaciones, índices, recuerdos, credenciales ni configuración privada del usuario. No se abrieron fuentes de su workspace como documentos de prueba. Los tests usaron perfiles privados externos y los probes crearon/borraron exclusivamente sus fixtures temporales sintéticos. No se hizo red, inferencia Ollama/cloud, descarga, instalación, commit, push ni cambios de producto.

### 3.3 Anclas de código para reproducir la inspección

Referencias relativas al HEAD indicado; las líneas son puntos de entrada, no una promesa de estabilidad futura:

| ID | Archivo/ancla | Evidencia principal |
| --- | --- | --- |
| O-01 | `local_cli/application/commands.py:13,36,83` | Comandos; `SubmitUserInput.content` textual; no contrato attachments |
| O-02 | `local_cli/application/session.py:1188–1269` | RAG por Turn, MEMORY snapshot, admisión común y mismo AgentRuntime |
| O-03 | `local_cli/core/context.py:280–429` | Prioridades, grupos tools, cap retrieval/MEMORY y materialización |
| O-04 | `local_cli/application/tool_runtime.py:187,438,570` | Broker FS; dispatch sin fallback directo; red mediada |
| O-05 | `local_cli/tools/web_fetch_tool.py` | Schema `url`/`max_length`, composición productiva |
| O-06 | `local_cli/application/network.py:22,35,62,149` | URL/destino, grants, redirects, redaction y extracción |
| O-07 | `local_cli/infrastructure/http_fetch.py:239` y `local_cli/network_config.py` | Cliente limitado, MIME, TLS, bytes, timeout |
| O-08 | `local_cli/core/rag.py:15` | Port `index/query`, no Source/Document model |
| O-09 | `local_cli/application/rag.py:25,47,134,150` | Estados, respuesta, render, composición y exclusiones |
| O-10 | `local_cli/infrastructure/rag.py:14,44,59` | Adapter normal y bridge legacy; ownership SQLite por llamada |
| O-11 | `local_cli/rag.py:22,58,100,133,181,259,405,476` | Límites, schema, chunking, scan, cosine y API antigua |
| O-12 | `local_cli/knowledge.py:68,119,190,264` | Notas/artifacts, lectura metadata, eliminación y atomicidad por archivo |
| O-13 | `local_cli/infrastructure/persistence.py:33,210` | Validación de claves y wrapper Knowledge |
| O-14 | `local_cli/application/auxiliary.py:219` / `session.py:1798` | Save del último assistant; load explícito al transcript |
| O-15 | `local_cli/application/retrieval_context.py:12,22,36` | Knowledge/RAG como datos, dedup y delegación MEMORY |
| O-16 | `local_cli/infrastructure/filesystem_tools.py` / `windows_filesystem.py` | Read/grep brokered; lectura completa de bytes y validación NTFS |
| O-17 | `desktop/src/App.tsx:252` / `desktop/shared/application.ts` | Texto → Application; snapshots/DTOs actuales |
| O-18 | `desktop/electron/main.ts:505–540` / `src/components/FileViewer.tsx:4` | Preview directo, cap 1.000.000 bytes, PDF no preview |
| O-19 | `local_cli/interfaces/jsonl_application.py:199,306` / `cli_application.py` | RAG vía comandos/eventos Application |
| O-20 | `local_cli/config.py:12` / `bootstrap_cli.py:101` / `bootstrap_server.py:257` | Config/composición RAG, Knowledge y Memory independientes |
| O-21 | `local_cli/ollama_client.py:26,495` | Embeddings RAG `/api/embed`, timeout por request 30 s |
| O-22 | `local_cli/application/session.py:508,570` / `memory_extraction.py:139` | Capture sólo input del usuario; policy no RAG/tool auto-write |
| O-23 | `local_cli/infrastructure/memory_sqlite.py:80` y módulos MEMORY | Store separado fuera del workspace; no store Knowledge |
| O-24 | `local_cli/model_search.py:1` / `desktop/src/components/Markdown.tsx:9` | Search de catálogo no web search; links no citas verificadas |
| O-25 | `pyproject.toml` / `desktop/package.json` | No parsers PDF/document/OCR declarados |

En los hallazgos, `T-01` refiere a regresión dirigida; `T-02` a probes RAG; `T-03` a probes de extracción; `T-04` a metadata/artifact sintético alterado; `T-05` a pequeña medición SQLite. Detalle y reproducción en §17–18.

## 4. Inventario de capacidades y componentes

### 4.1 Entrada, acquisition e interfaces

| Componente | Naturaleza actual | Datos/scope/lifecycle | Integración y límites |
| --- | --- | --- | --- |
| `ApplicationCommand` + AgentSession coordinator | Contrato y producto | Texto, session/Turn/Operation, expectedRevision | Una sesión principal y backend compartido; no SourceRefs ni bytes attachments |
| CLI/JSONL | Producto | `SubmitUserInput`, tools, RAG y auxiliares | JSONL es transporte, no importador multipart/base64/binario integrado |
| Desktop composer | Producto | `sendMessage(text)` | Envía sólo `content`; no picker/upload/drop pipeline de attachments encontrado |
| Desktop FileExplorer/FileViewer | Producto de UI, **no acquisition del agente** | Path elegido por UI; preview transitorio | `fs` Electron directo; PDF/imágenes binarios no preview; cap distinto del FS broker |
| `read`, `glob`, `grep` | Tools productivas mediante S3 | ExecutionContext/grant; contenido/paths/lines | Windows/NTFS soportado; no PDF/parser ni ingestión persistente automática |
| `ReadTool.execute` y executors pathname antiguos | Compatibilidad/implementación legacy | Texto/path | La ruta normal ToolRuntime FS **no** los ejecuta ni cae en ellos si falla el broker |
| `web_fetch` | Tool productiva mediada S5 | GET URL pública; cadena finita; ToolResult por operación | No search, cookies, sesión autenticada, render JS, browser ni documento indexado |
| `HttpFetchPort`/broker | Contrato + adapter productivo | Endpoint DNS pinned y HttpHop | TLS/DNS/size/time/redirects; no middleware de extracción documental |
| `model_search` | Producto auxiliar de modelos | Catálogo Ollama.com | Search especializado de modelos; no proveedor general de búsqueda web del agente |
| `ToolResult.artifacts` | Contrato genérico existente | Tupla de strings | No registry/resolver/version/ownership de SourceRefs demostrado |
| Attachments/upload/source references | **MISSING**, no stub integrado encontrado | — | Mención extensible `ContentReference` en Core es dirección futura, no capability disponible |
| Web search provider general | **MISSING** | — | Ninguna tool `web_search` ni contrato de SearchResults general encontrado |
| PDF/OCR/DOCX/ODT/RTF extractors | **MISSING** | — | Ni dependencia ni adapter/pipeline registrado; leer bytes no es parsear un documento |

### 4.2 Extracción, almacenamiento y retrieval

| Componente | Naturaleza | Conserva/lee | Eliminación/reinicio y limitación |
| --- | --- | --- | --- |
| `RAGEngine` | Algoritmo productivo heredado | Chunks textuales, SHA de archivo y vectores CSV en SQLite | Sobrevive reinicio; no lifecycle source completo, spaces ni purge de fuentes desaparecidas |
| `LegacyProjectRetrieval` | Adapter **normal productivo**, no dead code | Abre/cierra engine/SQLite por llamada | Lock por adapter, conexión usada en el hilo correcto; no transacción de corpus completo |
| `ExistingEngineRetrieval` | Bridge de compatibilidad | Índice ya existente | No reindexa al recibir legacy engine; no constituye implementación nueva |
| `ProjectRetrievalPort` | Contrato Core | `index()` y `query(text, top_k)` | Listas/dicts sin Source versionado, locator documental o cancel/deadline en firma |
| `RAGService` | Coordinación Application productiva | Enable/state/topK/stats/errors y matches | Errores no fatales para chat; serializa trabajo; limita a 24 filas el render, no toda acquisition |
| `KnowledgeRepository` / `KnowledgeStore` | Port + persistencia explícita productiva | Metadata JSON y artifacts Markdown/texto | Save/load/list/delete, storage workspace/config; no subject, expiración, refresh ni integración de borrado de chunks |
| `PersistenceService` | Producto | Transcript/snapshots redacted y stores separados | RAG temporal no se guarda como RAG conversacional; Knowledge load sí agrega mensaje al transcript |
| `ContextManager` / prepared context | Core productivo | Proyección acotada del material disponible | No store persistente ni source registry; cap/clipping no corrige extracción deficiente |
| `retrieval_context.rag_message` | Producto M7 | JSON lines documentales + dedup exacta con MEMORY | Redacta y marca como datos; no dedup semántica de fuentes ni fusión de dominios |
| `MemoryCapsule`, MemoryStore/lexical/semantic adapters | Producto MEMORY independiente | Recuerdos canónicos y provenance MEMORY | Delete/scopes/policy propios; no certificado semantic en perfil publicado; no reutilizar como corpus documental |
| SessionLogger/EventJournal/SecurityAudit | Producto de observabilidad | Eventos/correlación/outcomes; transcript por su store | No Source/Document store ni corpus RAG; audit no se borra para forget/document delete |

### 4.3 Qué significa «existe» en este inventario

`[O]` No se localizaron stubs concretos de PDF/attachments/search que la UI pudiera anunciar como terminados. Los contratos genéricos Core permiten extensión, pero no describen acquisition/extraction específica. Los mocks de embeddings, los HttpHop sintéticos y providers capturadores de prompts son **test-only**, no motores de calidad real.

`RAGEngine.augment_prompt()` aparece como API legacy y en tests; la composición actual usa `RAGResponse.context_message()`/`rag_message` y ContextManager. No se atribuye al prompt normal el wrapper antiguo de `augment_prompt`.

## 5. Camino de datos real

### 5.1 Texto pegado o escrito

```text
CLI/Desktop/JSONL texto
 → ApplicationCommand(SubmitUserInput.content)
 → canonical transcript / Turn
 → ContextManager (current input obligatorio)
 → provider inference / tools / respuesta
 → transcript persistido y eventos
```

`[O/T]` No se clasifica automáticamente como Document/Attachment. El texto actual conserva prioridad; si system + schemas + current input no caben se devuelve error, no se elimina el input para acomodar retrieval. No existe citation/provenance externa sólo por pegar contenido.

`[I]` Si una futura UI concatena un attachment al texto del usuario, podría perder la distinción entre afirmación directa del usuario y documento citado para MEMORY auto-capture. La arquitectura futura tendrá que separar esa procedencia; hoy no hay pipeline de attachments que demuestre resolverlo.

### 5.2 Lectura local agentic

```text
ToolInvocation read/glob/grep
 → ToolRuntime validation/Policy/Approval/Grant
 → FilesystemAuthority + plan ligado a root/handles
 → WindowsFilesystemBroker
 → ToolResult redacted, identidad/hash/metadatos
 → siguiente Generation del mismo Turn
 → límites de ToolResults y continuidad Core
```

`[O]` No incluye extraction/chunk/index automático. Un path mencionado por el usuario o el modelo no es una autorización absoluta. Recursos externos requieren selección host/grant exacto; unsupported broker no activa fallback legacy. `read` aplica offset/limit **después** de leer/decodificar el archivo completo; su cap de contexto no es un límite de bytes leídos/RAM.

### 5.3 URL pública

```text
web_fetch(url, max_length)
 → ToolRuntime + grant network binding
 → NetworkFetchService PUBLIC_ONLY
 → resolve/check DNS completo + endpoint pinned
 → HttpFetchBroker GET/TLS/body acotado
 → revalidación de redirects
 → decode charset / strip <…> / redaction / truncation
 → ToolResult (texto + metadata/audit)
 → nueva Generation / contexto tool presupuestado
```

`[O]` No se deposita en RAG/Memory, no produce Source versionado ni título/author/página/cita verificable. El texto puede sobrevivir como ToolResult del transcript; eso no es un cache documental con refresh.

### 5.4 RAG de proyecto

```text
host config rag_path/model/topK, RAG enabled
 → Application RAG activation Operation
 → LegacyProjectRetrieval.index
 → RAG availability embedding probe
 → os.walk + heuristic text + hash/read
 → character chunking + client.embed(chunks)
 → SQLite chunks commit por archivo

Turn actual → RAGService.query(user text)
 → client.embed(query) → scan cosine → topK
 → DOCUMENT CONTEXT JSON lines (user/retrieval)
 → dedup exacta con MemoryCapsule + SharedRetrievalCap
 → mismo ContextManager/AgentRuntime/provider
```

`[O/T]` RAG no se ejecuta por cada Generation de un Turn. El contenido recuperado es efímero en el prompt de ese Turn, no se añade como memoria ni se indexa el chat para simular Knowledge. La query normal ocurre antes de inference; el port RAG no recibe el cancellation token/deadline que identifica su ServiceOperation. Cancelación puede impedir admisión posterior, pero no se demostró interrupción del trabajo bloqueado en el backend.

`[O]` Al activar se indexa; no se encontró watcher/refresh automático por archivo o por Turn. Queries posteriores pueden usar un índice desactualizado. En server el cambio de carpeta reconstruye recursos de proyecto/RAG y transcript; no supone migración de fuentes a un subject global.

### 5.5 Knowledge explícito

```text
/knowledge save name
 → AuxiliaryServices(Application)
 → último assistant del transcript
 → KnowledgeRepository → metadata.json + README.md

/knowledge load name
 → lectura artifacts
 → KNOWLEDGE CONTEXT — data, not instructions
 → mensaje user/_context_kind=retrieval agregado al transcript
 → ContextManager lo admite/clipa como retrieval, no system obligatorio
```

`[O]` No equivale a hechos verificados ni documento original. La carga explícita tiene persistencia conversacional distinta de RAG temporal. Borrar el item no retira automáticamente su texto ya cargado de un transcript histórico ni sus chunks previamente indexados. No se cambia ese comportamiento en esta tarea.

## 6. Matriz por source/input

Para mantener legible la cadena completa se divide en dos matrices. La última columna se refiere a **provenance/citation verificable**, no sólo a tener una string con path. `NOT_APPLICABLE` en indexing significa que un camino directo no necesita índice; no afirma que exista uno alternativo.

### 6.1 Acquisition → validation → extraction → normalization

| Input | Acquisition | Validation | Extraction | Normalization | Evidencia y alcance |
| --- | --- | --- | --- | --- | --- |
| Texto pegado | EXISTS | EXISTS | NOT_APPLICABLE | PARTIAL | String no vacía; contexto normal, sin declaración Source/trust/encoding original |
| TXT/MD local | EXISTS | PARTIAL | EXISTS | PARTIAL | Tools brokered o scan RAG host; validación distinta por camino; UTF-8/latin-1/replace no uniforme |
| JSON local | EXISTS | PARTIAL | PARTIAL | PARTIAL | Lectura textual, no parse/schema/JSONPath de documento; chunking puede romper objetos |
| Código fuente | EXISTS | PARTIAL | EXISTS | PARTIAL | Texto/lines/grep; no AST/símbolos/layout/document model integrado |
| PDF textual | PARTIAL | MISSING | MISSING | MISSING | Puede leerse como bytes/ASCII heurístico, no extracción PDF real; preview PDF rechazado |
| PDF scans/imágenes | PARTIAL | MISSING | MISSING | MISSING | No OCR/vision input pipeline; heurística binaria no distingue PDF textual vs scan |
| DOCX/ODT/RTF/documentos comunes | PARTIAL | MISSING | MISSING | MISSING | Paths/bytes posibles; contenedores/parsing no soportados explícitamente |
| URL HTTP(S) pública | EXISTS | EXISTS | PARTIAL | PARTIAL | S5 checks reales; sólo MIME textual; decode/strip no extractor fiel |
| Search result general | MISSING | MISSING | MISSING | MISSING | No acquisition/search provider general; catálogo de modelos es otro dominio |
| Archivo grande | PARTIAL | PARTIAL | PARTIAL | PARTIAL | RAG salta >256 KiB; preview >1.000.000 B; read no cap de bytes observado |
| Encoding no UTF-8 | EXISTS | PARTIAL | PARTIAL | PARTIAL | RAG reemplaza, grep salta, read latin-1 con nota, fetch charset/fallback |
| Vacío/corrupto | EXISTS | PARTIAL | PARTIAL | PARTIAL | Vacío RAG skipped, read vacío posible; no errores de parser específicos; chunks viejos pueden quedar |
| MIME/extensión discordante | EXISTS | PARTIAL | PARTIAL | PARTIAL | URL confía en Content-Type permitido; local heurística NULL o extensión UI, no sniffing consistente |
| Hostil/instruction-like | EXISTS | PARTIAL | PARTIAL | PARTIAL | Headers de datos, redaction y policy; no limpieza universal ni garantía de neutralización semántica |

### 6.2 Chunking → index/retrieval → admission → model → citation/provenance

| Input | Chunking | Index/retrieval | Context admission | Model consumption | Citation/provenance |
| --- | --- | --- | --- | --- | --- |
| Texto pegado | NOT_APPLICABLE | NOT_APPLICABLE | EXISTS | EXISTS | MISSING para fuente externa |
| TXT/MD local | EXISTS por RAG | EXISTS por RAG / grep | EXISTS | EXISTS | PARTIAL: path/chunk o línea/hash, no cita versionada |
| JSON local | PARTIAL: caracteres | PARTIAL: texto, no estructura | EXISTS | EXISTS textual | PARTIAL |
| Código fuente | PARTIAL: caracteres | EXISTS por RAG / grep | EXISTS | EXISTS textual | PARTIAL: no vínculo hash+range estable en respuesta |
| PDF textual | MISSING | MISSING como PDF | MISSING como PDF | MISSING como PDF | MISSING |
| PDF scans/imágenes | MISSING | MISSING | MISSING | MISSING | MISSING |
| Documentos comunes | MISSING | MISSING como documento | MISSING como documento | MISSING como documento | MISSING |
| URL HTTP(S) pública | NOT_APPLICABLE | NOT_APPLICABLE: ToolResult directo | EXISTS | EXISTS textual | PARTIAL: URL/audit, sin versión/locator/cita verificada |
| Search result general | MISSING | MISSING | MISSING | MISSING | MISSING |
| Archivo grande | PARTIAL | PARTIAL | EXISTS para texto obtenido | PARTIAL | PARTIAL |
| Encoding no UTF-8 | PARTIAL | PARTIAL | EXISTS si hay texto | PARTIAL por posible pérdida | PARTIAL: sin confidence/decoder version |
| Vacío/corrupto | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL/MISSING según camino |
| MIME/extensión discordante | PARTIAL | PARTIAL | PARTIAL | PARTIAL | MISSING validación de tipo/provenance completa |
| Hostil/instruction-like | EXISTS por RAG textual | EXISTS | PARTIAL: datos acotados | EXISTS como dato; resistencia UNKNOWN | PARTIAL; trust/provenance insuficiente |

La fila PDF no se convierte en EXISTS porque un archivo `.pdf` sin NULL haya sido indexado como texto. El fixture `ascii.pdf` de T-02 **no es un PDF válido** y prueba sólo un falso positivo de detección, no extracción PDF.

## 7. RAG actual: implementación, relevancia y límites

### 7.1 Config, acquisition y chunking

`[O]` Defaults: RAG apagado, `rag_path='.'`, `rag_model='all-minilm'`, `rag_topk=5`. CLI y server construyen RAG con un cliente Ollama; no convierten el provider chat activo en un embedding backend genérico. Cambiar a chat remoto no certifica RAG remoto ni exige que embeddings sean los mismos que MEMORY.

`[O]` `os.walk` omite directorios de desarrollo/cache y roots propios `state/projects`/`state/sessions`. No hay allowlist de extensiones; `_is_text_file` mira NULL en los primeros 8 KiB. `.env` está en **skip directories**, no es una exclusión general de archivos secretos `.env`. No se observó secret-deny en la persistencia de chunks.

`[O/I]` El directorio raíz se resuelve desde workspace/config y puede ser externo por config host; esa resolución no es el broker S3 ni un grant documental. El walk no recurre por symlink de directorio por default, pero `stat/open/read_text` sobre leaf files sigue paths/symlinks. No se ejecutó una prueba de escape por symlink; no se atribuye el rechazo de S3 a este scanner.

`[O]` Files >262.144 bytes se saltan, no se resumen/streamean. SHA-256 y lectura de texto son pasos separados. `[I]` Modificación concurrente entre ambos puede desalinear hash/texto; no se probó TOCTOU.

Chunks de 1.000 caracteres, overlap 200, no tokens/sentencias/páginas/símbolos. No offsets originales ni mapping de texto normalizado al archivo. Se embeberá una lista de chunks por archivo; no hay estrategia prospectiva de lotes, concurrencia/cancel o cap global de corpus.

### 7.2 Store y scoring

Schema observado y T-02:

```text
chunks(id, file_path, chunk_index, content, file_hash, embedding)
indexes: file_path; (file_path, file_hash)
PRAGMA user_version = 0
embedding = BLOB con floats separados por comas en UTF-8
```

`[O]` No hay FTS5 en este RAG, ANN, filtros subject/user, source trust, tiempo, vigencia, MIME, idioma, importance ni reranking. El wrapper valida tipos de resultado y score finito; no valida identidad del espacio de los vectores.

Query: embed texto → leer todas las filas → deserializar vectores → cosine Python → sort descendente → topK. La dimensión real del modelo RAG instalado es **UNKNOWN**; el nombre default no prueba modelo disponible. No se consultó `/api/tags` ni se infirió en esta auditoría.

`[T]` Cambiar de `fixture-A` 2D a `fixture-B` 3D sin cambiar texto dejó cuatro archivos como unchanged y ejecutó cero embeddings de reindexado. Query 3D sobre vectores 2D produjo scores 1.0 en el fixture. No se afirma una calidad semántica real; se demuestra ausencia de rechazo dimensional/space.

`[O/T]` No hay similarity floor ni abstención por ausencia de relevancia. Un vector de query cero retornó cuatro chunks con score cero. El estado AVAILABLE significa backend respondió, no que haya evidencia relevante.

`[O]` `top_k` sólo se exige positivo en RAGService; el render usa máximo 24 filas, pero query/DTO pueden contener más si config eleva topK. MEMORY tiene sus propios caps y filtros; no corrige automáticamente este RAG.

### 7.3 Refresh, borrado, error y crecimiento

`[O/T]` Reindexado reemplaza chunks de archivos modificados que se leen y embeberán exitosamente. Archivos borrados, vacíos, nuevos binarios, demasiado grandes o cuyo embed falla **no activan retiro de chunks anteriores**. T-02 confirmó deleted/empty retenidos; otros casos se infieren del branch de skip. No hay refresh por URL, watcher ni TTL.

`[O]` Locks por instancia y ownership de conexión por llamada resuelven la transferencia de SQLite entre hilos; no certifican concurrencia entre varios procesos/importers ni recuperación de un crash a mitad de corpus. Commit por archivo, sin snapshot consistente de toda la indexación; migración es CREATE IF NOT EXISTS, no schema versionado con recovery igual a MEMORY.

`[O]` Coste visible de query: scan O(chunks × dimensión), sort O(chunks log chunks), textos/vectores materializados O(chunks × dimensión + texto). Config puede indexar muchos archivos pequeños: límite por archivo no es límite del índice. Medición pequeña en §13; escalabilidad a miles/decenas de miles, calidad y consumo real con embeddings **NO VERIFICADOS**.

### 7.4 Degradación y latencia

`[O/T]` RAG disabled no consulta embeddings; unavailable/invalid config produce error tipado no fatal. El path integrado detecta errores de embedding mediante callback; no anuncia un índice vacío como capability funcionando.

Pero RAG **no** tiene fallback exact/FTS independiente de embeddings como MEMORY. El cliente RAG usa un timeout de request de 30 s; no hereda soft350/hard600/guard50 de semantic MEMORY. Es timeout de socket por request, no una garantía global de retorno RAG ≤30 s. `[I]` RAG previo a inference puede aumentar mucho el tiempo al primer token con un backend lento. No se midió contra Ollama real.

## 8. Knowledge explícito, stores, lifecycle y provenance

### 8.1 Stores relacionados

| Store/estado | Localización por código/default | Ownership/schema/durabilidad | Papel Knowledge |
| --- | --- | --- | --- |
| Índice RAG | `<workspace>/rag_index.db`; constructor acepta path explícito | SQLite chunks, no version de space/schema; commits por archivo | Corpus documental local actual |
| Knowledge notes | `<workspace>/.agents/knowledge/<name>/` salvo config diferente | `metadata.json` + `README.md`/artifacts; atomic replace por archivo | Notas explícitas; no source registry |
| Transcript/project persistence | `state_dir/projects`, `state_dir/sessions` por adapters | JSON/JSONL legacy envueltos; redaction y restore Core | Historial; no documentos automáticamente indexables |
| SessionLogger | Estado local de sesiones por config | Logs de lifecycle/eventos | Observabilidad, no corpus Knowledge |
| EventJournal | Memoria RAM acotada de Application | Eventos/replay/snapshot | No almacén de documents/blobs |
| Security Audit | JSONL local de SECURITY fuera del workspace por composición | Segmentos/durabilidad/retención propias | Correlación/outcome, no contenido documental completo |
| MEMORY | `<state_dir>/memory/v1/memory.db`, WAL/SHM; state fuera del workspace exigido | Versionado, FTS, provenance/tombstones propios | Dominio de recuerdos; no store de documentos |
| ToolRuntime cache/results | RAM por runtime/operación | Reutilización de outcome por invocation; `cached=false` FS/fetch | No cache persistente de URLs/fuentes |
| Desktop preview | RAM UI, lectura directa Electron | Texto UTF-8, máximo 1.000.000 bytes | Preview, no upload ni ingestion |
| Temp/blob/attachment store | MISSING como subsystem | Ownership/retención desconocidos | Decisión nueva |

Son paths reconstruidos del código; **no se inspeccionaron sus contenidos reales**. No se atribuye cifrado universal a ninguno.

### 8.2 Notas Knowledge no son Document Sources

`[O]` Metadata contiene `name`, `description`, `created`, `tags`, `artifacts`; falta schemaVersion, subject, source hash/version, MIME, extractor version, confianza, fecha fetch/expiry, URL origin y locator. El timestamp se genera en UTC pero sin sufijo Z en su string. La clave por nombre es identidad de una nota, no identidad inmutable de una fuente.

`[O]` El wrapper valida nombres de comandos/artifacts con `_key`; el raw KnowledgeStore tiene menos defensas y no debe exponerse directamente a una nueva importación. Atomic replace de cada archivo no garantiza atomicidad metadata+artifacts ni fsync transaccional. No se probó crash/concurrencia multiproceso de KnowledgeStore.

`[T]` En un store enteramente sintético, alterar metadata para listar `../outside.txt` hizo que incluso `LegacyKnowledgeRepository.load_item('note')` leyera el artifact vecino. Esto demuestra que validar el **nombre de item** no valida los paths provenientes de metadata persistida. No se accedió a datos reales; no se probó explotación remota/UI ni un escape S3. `[P]` Una futura ingestión no debería confiar en metadata/artifacts externos sin controles de ownership/containment apropiados.

`[O]` El save explícito del último assistant no pasa por secret-deny MEMORY ni aplica aquí un filtro Knowledge dedicado. El transcript normal tiene redaction en sus caminos comunes, pero eso no demuestra que cualquier artifact importado a este store quede sanitizado. No se atribuye al store una garantía que no tiene.

### 8.3 Provenance y citas

Hay metadatos parciales útiles: file path + chunk, líneas `read/grep`, hash/identidad brokered, requested/effective URL y audit correlacionado. `ToolResult.artifacts` son strings extensibles. Faltan:

- identidad/version común de source y extracted representation;
- vínculo entre chunk recuperado y SHA/version presentado al modelo;
- locators de página/sección/rango/offset con preservación tras normalización;
- estado vigente/stale/deleted de la fuente al usar evidencia;
- registro verificable que relacione la cita generada con contenido realmente admitido;
- citation DTO/render/validation común CLI/Desktop;
- política para source inaccessible/actualizado después de responder.

`[O]` Un link Markdown se puede abrir externamente; no certifica que sea una cita correcta o una URL adquirida por el agente. `[I]` El modelo puede inventar links/paths si no existe verificación; no se ejecutó un ensayo de alucinación.

## 9. Fronteras Core V1

### 9.1 Contratos ya resueltos que deben conservarse

`[O]` Core §§7–13,17–18,21–23,26 gobiernan una sesión principal, Turn/Generation/Operation, comandos versionados, snapshots/eventos, contexto explícito y cancel/outcomes. Nuevas fuentes no autorizan un segundo AgentLoop, sesión paralela o inferencia desde Electron.

- Application decide/coordina; Infrastructure implementa adquisición/extracción/stores como adapters; Interfaces muestran/envían comandos. Core no depende de SQLite, parsers, paths del host, Ollama o Electron.
- Una tool nueva usa ToolRuntime y Security, no una ejecución directa escondida detrás de un botón.
- Operaciones de servicio existentes, como RAG/Knowledge host, conservan su backend Application; no se presupone que toda persistencia interna sea una tool del modelo.
- Comando aceptado no equivale a efecto terminado. Un timeout no demuestra ausencia de efecto ni habilita retries arbitrarios.
- ContextManager recibe material acotado y mantiene grupos tool-call/result; no cambia el transcript canónico para simular compactación.
- Context windows manuales `4K/8K/16K/32K/64K`, AUTO seguro vigente, validación contra capability real. 64K no habilita cargar todo el corpus.
- Capability desconocida no se anuncia como disponible. Una etiqueta vision/embedding no demuestra acquisition de PDF/imágenes.

### 9.2 Lo que Core dejó para extensión

`[O]` Core §1 dejó attachments, PDF/vision y web search fuera de su certificación, no los prohibió para etapas futuras. §25 anticipa referencias/decoders como posible extensión, no establece un Source schema ya implementado. §22 mantiene Knowledge explícito separado del transcript/EventJournal; la política definitiva de formato/retención no está cerrada sólo por existir KnowledgeStore.

`[P]` Knowledge puede usar los lifecycle/errores/receipts existentes, añadiendo únicamente los contratos de fuente estrictamente necesarios después de decidir alcance. Esta auditoría no fija signatures ni enum values nuevos.

## 10. Fronteras SECURITY V1.2

### 10.1 Controles existentes reutilizables

| Superficie | Control demostrado/observado | Límite del claim |
| --- | --- | --- |
| Filesystem tools | S3 root/handle mediation, no reparse/direct fallback, permisos/grants y audit | Windows + local NTFS; no soporte POSIX artificial ni claim sobre todo I/O del host |
| URL/web_fetch | PUBLIC_ONLY, HTTP(S), mixed/private DNS denied, redirect checks + numeric pinning | Cliente mediado; no firewall de todo el equipo/proceso |
| Redirects | Máximo 5; fresh resolución/verificación por hop, scope ceiling y no HTTPS downgrade | No amplían grants silenciosamente; error posterior puede ser OUTCOME_UNKNOWN |
| Payload remoto | 2 MiB cuerpo retenido; 50.000 chars publicado incluyendo marcador, respeta menor max_length | Límites operacionales, no cuota OS; no parser PDF/HTML rico |
| Tiempo | 30 s presupuesto HTTP incluyendo redirects y deadline/cancellation Core | No debe extrapolarse al RAG embedding client u otros services |
| Transporte | TLS hostname/cert, sin proxy ambient/netrc/cookies/auth session; identity encoding | No browser/session navigation |
| Tool effects | Validation→Policy→Approval→Grant→Dispatch→Result→Audit | Grant no es autoridad documental ni verdad |
| Redaction/audit | Redactor de secretos conocidos + audit mínimo correlacionado | No DLP universal; audit no almacena conocimiento conversacional |
| Subagentes | Ruta tools común y ceiling atenuado | Shell sigue permisos normales del host |
| Proceso shell | `HOST_UNISOLATED` | Sin sandbox/process isolation, aunque un parser futuro sea local |

La antigua pregunta `SEC12-OD-04` aparece como OPEN DECISION en texto histórico de §33; el comportamiento actual y la evidencia S5 concretan PUBLIC_ONLY. Esta auditoría registra esa concreción, no abre de nuevo la decisión ni cambia policy.

### 10.2 Frontera no cubierta automáticamente

`[O]` RAGEngine hace `os.walk/stat/open/read_text` directo y KnowledgeRepository persiste con adapters de host; Desktop preview usa `fs.promises`. Son superficies existentes diferentes del dispatch S3. La arquitectura Core distingue preview UI de I/O que alimenta al agente (§23); **usar el preview como futura ruta de attachments requerirá revisión de autoridad**, no sólo copiar su código.

`[O]` Los handlers preview inspeccionados no muestran validación de sender/root igual a los endpoints Application protegidos. `[I]` Reutilizarlos para alimentar contenido agentic sin controles adicionales podría convertir una utilidad UI en una ruta no mediada. No se demostró vulnerabilidad de renderer ni se modificó IPC.

`[P]` SECURITY §38 exige clasificar cada nueva superficie/tool con permiso, scope, policy/approval, secrets, audit, lifecycle y límites. Knowledge debería reutilizar esos controles, no inventar SandboxPort, claims OS, permisos paralelos o excepción para attachments.

### 10.3 Privacidad e instruction injection

- `[O]` RAG almacena texto crudo obtenido del corpus; no se encontró secret-deny previo a su indexación. Redaction del prompt no garantiza limpieza del SQLite ni de toda fuente sensible.
- `[O]` `SecretRedactor` declara expresamente que no detecta todos los secretos/desconocidos/transformados. Metadata URLs de audit omite query values; eso reduce leakage pero no proporciona una source identity reversible completa.
- `[O/T]` Render RAG/Knowledge marca contenido como datos de rol user y no system; clipping conserva cierre/guard. Script/style survives en fetch; datos hostiles pueden llegar al modelo aunque no adquieran grants.
- `[I]` Headers/budgeting reducen riesgo y autoridad de datos, no prueban inmunidad del LLM a prompt injection. No se ejecutó campaña adversarial Knowledge nueva.
- `[P]` Imported text, query snippets y document metadata no deberían elevarse a project instructions, system o afirmaciones personales del usuario por la mera adquisición.
- `[O]` Network provider chat está separado de policy web_fetch. El opt-in MEMORY remoto no autoriza automáticamente enviar documentos locales; el estado actual no establece un consentimiento Knowledge común equivalente.

## 11. Fronteras MEMORY V1 y coexistencia

### 11.1 Separación del dominio

MEMORY §6 AD10 y §22 dicen que pueden compartirse abstracciones/patrones de retrieval, DTOs, métricas y presupuesto, pero no automáticamente tabla, namespace, chunking, scan o delete lifecycle. §22.2: «Knowledge explícito no se convierte automáticamente a memoria personal».

`[O/T]` En código:

- RAG y MemoryStore están separados; activar/consultar RAG no invoca `memory_remember`.
- Memory recall principal se congela por Turn; RAG documental tiene su propia operación y resultado.
- Dedup M7 compara texto canónico normalizado exacto; elimina duplicados del prompt sin fusionar persistencia ni afirmar equivalencia de fuentes.
- Auto-capture está off por default. Cuando habilitado, `_queue_memory` usa input directo del usuario ligado al Turn exitoso; no extrae automáticamente assistant/tool/subagent/RAG como USER_ASSERTION.
- Extractor produce propuestas y Application policy decide; una fuente nueva no emite grants ni un write MEMORY privilegiado.
- Delete MEMORY/no-resurrection no significa borrar documento original, logs, audit, Knowledge note o transcript. Delete de Knowledge tampoco equivale a memory_forget.

`[P]` Si se ofrece «recordar algo de un documento», hará falta una intención explícita y su procedencia/policy MEMORY, no una conversión implícita del documento entero. La selección del formato UX o del enlace de provenance es una decisión abierta.

### 11.2 Shared budget ya implementado

`[O/T]` ContextManager trabaja sobre ventana efectiva numérica `N`, no carga en proporción ilimitada al preset. Se protegen system, schemas, current input y continuidad tools necesaria. Reservas output/margin se descuentan antes de contenido opcional.

- Core caps sobre capacidad disponible: retrieval ≤15%, ToolResults agregados ≤30%, individual ≤15%, tools+retrieval ≤40%.
- SharedRetrievalCap se estrecha por 15% de capacidad después de reservas, cap post-fixed Core, espacio real restante y cap combinado restante.
- Memory ceiling ≤ `min(shared cap, 8% de N, 1024 tokens)`; reparto inicial flexible 60/40 y préstamo de sobrante, no dos caps independientes de 15%.
- Una MemoryCapsule, hasta ocho statements canónicos enteros; puede costar cero si no hay resultados relevantes. RAG/Knowledge ocupa espacio compartido restante y puede ser expulsado/clipeado.
- RAG y Knowledge tienen `_context_kind='retrieval'`; no se convierten en system obligatorio.
- Preservación current user y cap se prueban en ventanas pequeñas y avanzadas. Tests de presupuestos 32K/64K no certifican inference real a esas ventanas.

`[O]` Las tools de archivos/fetch siguen su presupuesto ToolResults; no se suman sin límite como si retrieval y tools fueran independientes del cap combinado. `[P]` Un futuro attachment resolver deberá declarar cómo clasifica su payload para no contabilizar dos veces o eludir estos límites.

### 11.3 Semantic Profile

`[O]` `SEMANTIC_PROFILE=NOT_CERTIFIED` permanece tal cual en manifest READY/CI. No se reevalúan candidatos MEMORY ni se reinterpretan fallos históricos. RAG usa embeddings, pero eso no certifica semantic MEMORY ni al revés. El fallback exact/FTS MEMORY no demuestra un fallback documental existente.

## 12. Desktop, CLI, JSONL y subagentes

### 12.1 Interfaces actuales

`[O]` CLI y Desktop/server comparten comandos/estado Application para RAG y chat. `/knowledge` actúa como auxiliar del mismo backend, no como tool nueva del modelo. JSONL admite mensajes RAG/command/snapshot/event, sin source upload contract.

Desktop tiene toggle/status/query RAG y visualización Markdown. El FileViewer bloquea PDF por extensión y muestra «Binary file — cannot preview»; el diálogo nativo inspeccionado selecciona **directorio**, no attachment. Preview 1 MB decimal no es límite de upload porque ese upload no existe.

No se encontraron Source list/detail/status, upload progress, cancel import, attachment extraction failure o source citation DTOs. El transporte genérico podría extenderse, pero esa posibilidad es `[P]`, no integración actual.

### 12.2 Subagentes

`[O]` SubAgentRunner utiliza el runtime/ToolRuntime común; las lecturas/fetch disponibles siguen grants ceiling, contexto explícito y resultados Core. MEMORY recibe sólo snapshot delegado acotado/revalidado del padre, no una nueva query global libre.

No se encontró un source/document delegation contract ni una instancia RAG documental automáticamente conectada al loop del subagente. No se infiere que todos los documentos del proyecto estén autorizados al child por existir RAG en la sesión principal.

`[P]` La futura arquitectura debe decidir qué references/chunks ya adquiridos delega el padre, si el child puede adquirir nuevos y cómo se preservan provenance/budget/authority. No basta heredar una lista de paths o URLs sin vínculo de scope.

## 13. Rendimiento y eficiencia observables

### 13.1 Límites que existen y no deben confundirse

| Camino | Límite actual | Qué no garantiza |
| --- | --- | --- |
| RAG source | 256 KiB por archivo | Corpus/DB/RAM/tiempo global acotado |
| RAG chunks | 1.000 chars / overlap 200 | Presupuesto de tokens uniforme o límites de lote embedding |
| RAG retrieval | topK default 5, render hasta 24 | Abstención, deadline, calidad, respuesta DTO acotada con config arbitraria |
| Desktop preview | 1.000.000 bytes | Acquisition del agente, streaming o parser seguro |
| Brokered read | Lines offset/limit después del read completo | Preventive byte/RAM quota |
| web_fetch | 30 s / 2 MiB / 5 redirects / ≤50.000 chars | Soporte PDF, fuente fiel, browser o firewall |
| ContextManager | N + reservas + caps compartidos | Bounds de acquisition, DB/log crecimiento o parsing previo |
| MEMORY | Caps/contracts propios certificados | Capacidad documental o certificación semantic |

### 13.2 Medición sintética pequeña ejecutada (T-05)

SQLite/algoritmo reales; embeddings de fixture inmediato **16D**, sin endpoint, calidad ni modelo real. Cada archivo contiene 45 líneas sintéticas repetidas; cinco queries diferentes por escala, sin warm-up/inferencia externa. Un índice nuevo por escala.

| Archivos | Chunks | DB bytes al cerrar | Index ms | Query mediana ms | Query máximo ms | n queries |
| --- | --- | --- | --- | --- | --- | --- |
| 8 | 48 | 106.496 | 242,487 | 5,920 | 10,982 | 5 |
| 32 | 192 | 352.256 | 600,222 | 23,946 | 27,727 | 5 |

Estas muestras caracterizan scan/decodificación/path checks/SQLite en este host y el coste de commits por archivo, **no** p95 confiable, benchmark de ANN o latencia RAG con Ollama. No se extrapolan esos números como SLA a 1.000/10.000 documentos, dimensiones reales, imports PDF o concurrency.

`[I]` El aumento observado concuerda con un scan creciente; el código demuestra trabajo O(n×d) y reconstrucción/deserialización por query. Abrir/cerrar una conexión por operación protege ownership pero agrega trabajo. No hay cache documental ni caché de query/version de embedding en este RAG. `[P]` Indexación/queries incrementales, caches o índices deben evaluarse después de fijar identity/version/staleness; no se optimizó nada aquí.

### 13.3 Coste de contexto

`[O/T]` MEMORY/RAG comparte cap y dedup exacta; pruebas con 10.000 mensajes confirman que un historial grande no fuerza 10.000 retrieval/hydrations. La proyección de contexto M7 evita equiparar transcript completo a prompt. RAG todavía procesa la pregunta completa para embed y su corpus completo para scan, independientemente del cap final.

`UNKNOWN`: consumo RAM máximo del parsing, tiempo al primer token RAG real, calidad de extracción por formato, relevancia documental real, latencia con modelo local, rendimiento de índice persistente grande y E2E simultáneo Knowledge+Memory con fuentes reales. No se descargaron ni ejecutaron modelos para llenar esos UNKNOWN.

## 14. Hallazgos, gaps y deuda

Prioridades orientativas de auditoría, **no fases aprobadas**: P0 = frontera/validez crítica antes de exponer acquisition nueva; P1 = capacidad/lifecycle esencial; P2 = eficiencia/UX posterior; P3 = mejora opcional. Propuestas siempre `[P]`.

| Hallazgo | Evidencia/clasificación | Impacto / limitación actual | Dirección posible [P] | Prioridad |
| --- | --- | --- | --- | --- |
| KIN-01 — No Source/Document común | [O] O-01,08,25 | Paths/URLs/artifacts no representan ownership/version/locators; falta pipeline completo | Evaluar identidad/version/provenance común sin imponer store ahora | P1 |
| KIN-02 — Tres rutas FS diferentes | [O] O-04,10,18; [I] riesgo de reutilización | Broker claims no cubren scan/preview/host store; nueva ruta podría evitar authority | Fijar acquisition por superficie sobre Security existente, no duplicarlo | P0 |
| KIN-03 — RAG sin spaces | [O/T] O-11, T-02 | Vectores de otro modelo/dimensión reutilizados/comparados silenciosamente | Contratos documentales de space/version/rebuild y error tipado; no copiar namespace MEMORY | P0 |
| KIN-04 — Fuentes retiradas permanecen | [O/T] O-11, T-02 | Documento borrado/vacío puede seguir recuperándose como evidencia actual | Definir source lifecycle, vigencia, retiro de proyección y snapshots | P1 |
| KIN-05 — Extracción remota no fiel al tipo | [O/T] O-06, T-03 | JSON pierde `< b >`; HTML conserva script/style y entidades | Separar adquisición S5 de extraction MIME-aware con errores/limits | P1 |
| KIN-06 — PDF/document/OCR no existen | [O] O-18,25 y búsqueda source | Leer bytes/heurística no habilita PDF/scan; experiencia no anunciable como terminada | Elegir supported formats y capability gating/failures explícitos | P1 |
| KIN-07 — Attachments ausentes | [O] O-01,17,19 | No input de references/blobs ni lifecycle/cancel/progress | Diseñar entrada compartida Application y distinguir texto usuario/fuente | P1 |
| KIN-08 — No general web search | [O] O-24/tool registry | Catálogo Ollama no cumple búsqueda de información externa | Decidir provider/search abstraction sin browser actions | P1 |
| KIN-09 — Sin cita verificable | [O] O-09,15,24 | Path/URL presente no prueba que claim derive de fuente/version admitida | Evaluar locators/citation DTO y verificación de referencias | P1 |
| KIN-10 — Encoding/tipo inconsistentes | [O/T] O-11,16,18, T-02 | RAG pierde caracteres; read/grep/UI difieren; falso positivo `.pdf` | Especificar decoder/type policy y errores de extracción observables | P1 |
| KIN-11 — Byte acquisition no acotada uniformemente | [O] O-16; [I] riesgo RAM | Read completo antes de offset/cap, corpus RAG ilimitado | Decidir bounds de bytes/pages/chunks/tiempo y streaming por formato | P1 |
| KIN-12 — Scan vectorial y dependencia embedding | [O/T] O-11,21, T-05 | No lexical documental; coste crece; primer response puede esperar RAG | Comparar exact/lexical/semantic y graceful degradation para Knowledge, no asumir solución vectorial | P1 |
| KIN-13 — Persisted artifact metadata confiada | [O/T] O-12,13, T-04 | `../outside.txt` sintético se carga desde metadata; no containment del artifact leído | Ownership/containment/validation del store documental importable | P0 |
| KIN-14 — Secret policy no equivale a index redaction | [O] O-11,22 y SecretRedactor | Texto crudo puede persistirse; excluir dir `.env` no excluye todos los secrets | Fijar privacidad/consentimiento/retención local y límites de redaction | P0 |
| KIN-15 — Datos/instrucciones parcialmente separados | [O/T] O-15, T-01,03; [I] resistencia LLM UNKNOWN | Markers no garantizan inmunidad; origen perdido si attachment se pega como usuario | Provenance/trust explícitos; campañas injection; no promoción a system/user assertion | P0 |
| KIN-16 — Knowledge load queda en transcript | [O] O-14 | Delete nota no borra cargas previas; storage y contexto tienen lifecycle distinto | Definir source deletion vs derived context/history sin borrar audit | P1 |
| KIN-17 — Subagent source delegation ausente | [O] SubAgentRunner/O-15 | Memory delegate no es document authority/corpus compartido | Evaluar delegación finita de refs/chunks/acquisition con ceiling | P1 |
| KIN-18 — Budget compartido sí reutilizable | [O/T] O-03,15,T-01 | Base sólida; no ampliar por doble cap ni usar system para documents | Integrar admission como dato con N y prioridad existente | P0, preservar |
| KIN-19 — Semántica RAG no certificada | [O] tests usan doubles; [I] calidad real UNKNOWN | READY Memory no avala calidad documental/semantic | Definir corpus prospectivo y quality gates propios, sin recertificar candidatos Memory | P1 |
| KIN-20 — CI/hashes/deadline pendientes | [O] workflows + logs aportados | HEAD completo no demostrado verde; nueva etapa no debe ocultar deuda | Reconciliación separada antes de un gate de implementación futuro | P1, deuda baseline |

### 14.1 Contradicciones aparentes y tratamiento

1. **«Core admite Knowledge futuro» vs «Core dejó attachments/PDF fuera».** No hay contradicción: extensión prevista no certifica implementación. Se mantiene explícita esa ausencia.
2. **«FS S3 fail-closed» vs «RAG/preview leen paths».** Son caminos distintos. El scanner host actual no hereda claims de tool broker. El riesgo de expandirlo como authority agentic debe decidirse, no ocultarse.
3. **«Memory semantic opcional» vs «RAG depende de embeddings».** Son dominios con contratos diferentes. No se cambia MEMORY ni se presenta su fallback como característica ya existente de RAG.
4. **«Knowledge explícito» vs «save assistant».** La función presente guarda una nota elegida por el host; no certifica origen factual ni personal Memory.
5. **«README/tags READY» vs «CI actual falló».** READY publicado delimita una evaluación histórica; los logs remotos y los checks de HEAD son evidencia diferente. Esta auditoría no reescribe ninguno.
6. **Raw hashes de evidencia vs checkout EOL.** Los fallos aportados de `make_freeze` son compatibles con un harness que fija SHA de bytes CRLF y obtiene LF en Git. La diferencia de normalización ya diagnosticada no autoriza reescribir evidencia; está fuera de esta tarea. El fallo macOS de 0,6269 s frente a `<0,6` sigue con causa productiva/scheduling **NO VERIFICADA** aquí.

No se detectó permiso normativo para fusionar Memory y Knowledge ni para convertir fuentes en instrucciones. Los gaps no se resuelven silenciosamente mediante una arquitectura nueva en este informe.

## 15. Decisiones abiertas para la arquitectura futura

Clasificación: **RESUELTA** = contrato existente reutilizable; **PARCIAL** = parte definida y falta contrato Knowledge; **NUEVA** = elección propia de la etapa. Ninguna alternativa de esta tabla está aprobada por esta auditoría.

| ID | Tema/estado | Base ya resuelta | Alternativas/trade-offs pendientes |
| --- | --- | --- | --- |
| KI-OD-01 | Source identity/version — NUEVA | Path/hash RAG y URL parcial existen | Hash de bytes, identidad lógica+revisiones o ambas; dedup vs URLs/paths cambiantes y extracción reproducible |
| KI-OD-02 | Source/Document representation — NUEVA | DTO/event versioning Core | Separar bytes/extracted/chunks o representación única; trazabilidad frente a complejidad de migrations |
| KI-OD-03 | Scope/ownership — PARCIAL | Workspace/grants Core/Security, subject MEMORY separado | Turn/session/workspace/library; qué acceso explícito autoriza host y qué se puede compartir |
| KI-OD-04 | Temporary vs persistent — NUEVA | RAG DB y notas actuales persistentes | Per-Turn ephemeral, cache de sesión o biblioteca durable; privacidad, rendimiento y refresh |
| KI-OD-05 | Formats V1 — NUEVA | Texto local/remoto parcialmente soportado | TXT/MD/JSON/code primero; PDF textual; documentos comprimidos; OCR opcional. Dependencias/licencias/limits/hardware |
| KI-OD-06 | Type/encoding policy — NUEVA | Content-Type remoto/heurísticas locales | Extensión+sniff, charset declarado, fallback explícito/strict; fidelidad frente a aceptación de archivos imperfectos |
| KI-OD-07 | Extraction fidelity/failure — NUEVA | Errores Core/S5 y truncation disponibles | Preserve structure, texto plano normalizado o ambas; parse parcial/unsupported/corrupt distinto de documento vacío |
| KI-OD-08 | Chunking/locators — NUEVA | Chunks chars RAG y lines de tools | Token-aware, layout/section/code-aware, límites numéricos; citation estable vs simplicidad/CPU |
| KI-OD-09 | Retrieval/index — PARCIAL | RAG cosine scan; MEMORY FTS sólo su dominio | Lexical documental, hybrid opcional, rebuild/index incremental; comparar costes antes de elegir vectores/ANN |
| KI-OD-10 | Embedding spaces — PARCIAL | Pattern/contracts MEMORY versionados | Espacio documental separado, revision/dim/preprocess, invalidación/migration; no mezclar vectores existentes |
| KI-OD-11 | Dedup — PARCIAL | File hash por path; dedup texto del prompt | Byte-level, source-version o chunk-level; conservar diferentes provenance aunque texto idéntico |
| KI-OD-12 | Refresh/staleness/delete — NUEVA | Memory forget no aplica a documentos | Reimport explícito, TTL o refresh host; cuándo retirar chunks/capsules, qué history/backups permanece |
| KI-OD-13 | Citations — NUEVA | Paths/chunks/URLs parciales | SourceRefs con locator verificable, footnotes/UI, output validation; qué hacer con source borrada/mutable |
| KI-OD-14 | Remote acquisition — PARCIAL | PUBLIC_ONLY HTTP(S), redirects/limits/security ya resueltos | URL source/cache contract y consentimientos específicos; no reabrir private-network/file URL policy |
| KI-OD-15 | Web search provider — NUEVA | Provider network distinto de fetch y tools comunes | Provider local/API/opt-in remoto; coste, privacidad query, rate limits y resultados con provenance |
| KI-OD-16 | Source trust/injection — PARCIAL | Dato no system; Policy/grants no emitidos por contenido | Trust classes/provenance, quoted data, detección y tests; no confiar en self-declared authority de un documento |
| KI-OD-17 | Privacy/secrets — PARCIAL | Redactor y MEMORY secret/sensitivity controls existentes | Raw bytes retention, local-only/remote opt-in, qué se indexa/excluye y qué se elimina; no prometer DLP/cifrado universal |
| KI-OD-18 | Admission/budget — PARCIAL | N, prioridades, caps comunes resueltos | Peso/admisión de source snippets/attachments dentro del cap ya vigente; no ampliar con un segundo retrieval budget |
| KI-OD-19 | Memory interaction — RESUELTA en separación, PARCIAL en UX | Memory != Knowledge; write sólo por policy | Confirmación/enlace de provenance si usuario pide recordar algo; no auto-write por adquisición |
| KI-OD-20 | Subagent exposure — PARCIAL | Ceiling/delegación Memory/tools Core | Sources adquiridas delegadas vs nueva adquisición; scope/ranges/versions y sharing sin autoridad ampliada |
| KI-OD-21 | CLI/Desktop/JSONL exposure — PARCIAL | Backend Application y comandos/eventos existentes | Refs vs streaming/upload transport; progress/cancel/errores, parity, UX sin lógica de negocio en renderer |
| KI-OD-22 | Cache — NUEVA | Outcome idempotente tools, no source cache | Cache ephemeral/durable por version/ETag/hash; invalidación, disk bounds y privacy |
| KI-OD-23 | Capacity/retention — NUEVA | Límites S5/client y context ya resueltos | Bytes/documents/pages/chunks/index/global footprint; maintenance/purge explícito vs automático |
| KI-OD-24 | Async/cancel/recovery — PARCIAL | Operation lifecycle Core | Import en worker, cooperative/bounded work, partial commit/recovery; no simular cancel/rollback |
| KI-OD-25 | Existing RAG compatibility — NUEVA | Legacy DB/formato y wrappers actuales | Migrar/rebuild/adapter sólo lectura; mantener índices legacy sin reinterpretar spaces o datos corruptos |
| KI-OD-26 | Quality/certification — NUEVA | MEMORY Core/semantic separation no certifica Knowledge | Corpus documental prospectivo, extracción/relevance/citation/abstention/latency; coverage real vs doubles |
| KI-OD-27 | Active Web boundary — RESUELTA por alcance humano | No browser/actions/authenticated sessions en esta etapa | No elegir browser stack ni browsing loop aquí; interfaces futuras no implican implementarlo |
| KI-OD-28 | Platform claims — PARCIAL | Core portable; S3/READY Windows NTFS | Qué acquisition/parsers son portables y qué fail-closed se anuncia fuera del perfil; pruebas no equivalen a soporte completo |

## 16. Riesgos principales y exclusiones Active Web

### 16.1 Riesgos a evaluar prospectivamente

`[I/P]` Además de los gaps demostrados: archivos comprimidos/decompression bombs, PDFs con estructuras costosas/embedded objects, parsers colgados, documentos gigantes o millones de chunks, zip-path traversal, HTML remoto hostile, metadata falsificada, URLs con datos sensibles, extracción incompleta presentada como completa, fuente stale usada como actual, citas inventadas y duplicación documental/memoria consumiendo contexto.

No se afirma que esos exploits se hayan ejecutado ni que todos los formatos se soporten. Son motivos para diseñar límites/recovery y campañas futuras antes de anunciar capacidades.

### 16.2 Exclusiones verificadas

`[O]` El fetch actual no tiene DOM, JS runtime, clicks/forms, cookies/authenticated browser session ni browser automation. Abrir links externos o iniciar OAuth del provider desde Desktop es interacción de usuario/administración, **no Active Web agentic**. `model_search` tampoco es una cadena de acciones del agente en sitios.

Por el alcance de esta etapa, quedan fuera:

- DOM interaction o análisis dependiente de render/browser control;
- automatización de click/form/action;
- sesiones/autenticación de sitios web mediante navegador;
- loops de navegación e interacciones multi-step;
- website actions, descargas mediante navegador o scraping autenticado interactivo.

`[P]` Fetch/search pueden adquirir información pública pasiva dentro de Security; no se propone un browser tool encubierto para resolver páginas JS/auth. `UNSUPPORTED`/error honesto es preferible a anunciar esos casos como soportados.

## 17. Evidencia nueva y pruebas ejecutadas

### 17.1 T-01 — Regresión dirigida

Comando pytest efectivo, con CPython 3.14.6:

```powershell
python -B -m pytest -q -p no:cacheprovider `
  --basetemp <audit-temp>/pytest-private `
  --junitxml <audit-temp>/tests.xml `
  tests/test_rag.py tests/test_knowledge.py `
  tests/test_nova_core_phase10_rag.py `
  tests/test_nova_core_phase14_architecture.py `
  tests/test_nova_core_phase9_context.py tests/test_context_64k.py `
  tests/security_v12/test_s5_contracts.py `
  tests/security_v12/test_s5_runtime.py `
  tests/memory_v1/test_m7_context.py `
  tests/memory_v1/test_m7_integration.py
```

`python` en esta campaña fue `C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe`, no un alias WindowsApps. El launcher copió sólo system/toolchain/locale, deshabilitó plugin autoload y bytecode, conservó el site pytest existente y asignó HOME/USERPROFILE/APPDATA/LOCALAPPDATA/XDG_CONFIG_HOME/XDG_STATE_HOME/XDG_CACHE_HOME/TEMP/TMP privados. No cargó `.env`, secrets ni configuración del usuario.

Output externo: `C:/Users/joseh/AppData/Local/Temp/nova-knowledge-audit-0f5cefbec70b48b4bce24a85d54b4b7d`.

- pytest: **313 passed in 15.11s**, exit 0.
- JUnit: tests 313, failures 0, errors 0, skipped 0, time 15.101 s.
- SHA-256 `tests.xml`: `4d4b01e1e883ec93d1ae11fc11cd8f250155aa305692d811ec96084040e33865`.

Unit/contract: chunking/hash/cosine/KnowledgeStore, URLs/IPs/limits/text, architecture/budgeting.
Integration: Application/RAG SQLite real con embedding doubles, operación/grant/HTTP port controlado, MEMORY+RAG/context/subagent con providers de fixture y estado privado.
**No host-real red, parser PDF, calidad embedding real, E2E LLM ni nueva campaña READY.** Las operaciones locales de SQLite/FS sintético son reales en Windows; eso no convierte los doubles de embeddings o HTTP en servicio remoto real.

### 17.2 T-02 — Caracterización RAG sin embeddings reales

Fixture temporal con `gone.txt`, `blank.txt`, latin-1, ASCII con extensión `.pdf`, vacío, >256 KiB y binario NULL; DB fuera del directorio indexado para evitar autoindexarla.

Resultados preservados aquí:

```json
{
  "initialIndex": {"files_indexed": 4, "files_skipped": 3, "files_unchanged": 0, "chunks_indexed": 4},
  "indexedNames": ["ascii.pdf", "blank.txt", "gone.txt", "latin1.txt"],
  "latin1Content": "Caf\ufffd sint\ufffdtico.",
  "asciiPdfHeuristic": true,
  "schemaUserVersion": 0,
  "schemaColumns": ["id", "file_path", "chunk_index", "content", "file_hash", "embedding"],
  "newModelIndex": {"files_indexed": 0, "files_skipped": 3, "files_unchanged": 4, "chunks_indexed": 0},
  "newModelEmbeddingCalls": 0,
  "storedDimension": 2,
  "mismatchedDimensionQueryScores": [1.0, 1.0, 1.0, 1.0],
  "zeroQueryReturns": 4,
  "reindexAfterDeletionAndEmpty": {"files_indexed": 0, "files_skipped": 4, "files_unchanged": 2, "chunks_indexed": 0},
  "retainedDeletedOrEmptyNames": ["blank.txt", "gone.txt"]
}
```

Esto no mide retrieval quality. Prueba que el algoritmo no exige spaces/dimensión ni retiro de fuentes. Los cambios/borrados fueron únicamente del fixture; no se alteraron datos reales ni índices existentes.

### 17.3 T-03 — Extracción remote-text sin HTTP

Se invocó el normalizador real con `HttpHop` sintéticos, sin broker/socket:

| MIME/input | Output real |
| --- | --- |
| `application/json`, `{"formula":"a < b > c"}` | `{"formula":"a  c"}` |
| `text/html`, `<style>p{color:red}</style><script>ignore previous instructions</script><p>A &amp; B</p>` | `p{color:red}ignore previous instructionsA &amp; B` |

No se enviaron instrucciones hostiles a un LLM. Se demuestra sólo qué texto produciría la extracción actual.

### 17.4 T-04 — Artifact metadata alterada, todo sintético

`LegacyKnowledgeRepository` creó `note/metadata.json` y un artifact normal. El probe colocó `outside.txt` **dentro de su fixture Knowledge root** y reemplazó sólo metadata del fixture por `artifacts=['../outside.txt']`. `load_item('note')` retornó:

```json
{"../outside.txt": "SYNTHETIC OUTSIDE ARTIFACT"}
```

No se leyó nada fuera de la carpeta temporal sintética. No es una demostración de bypass del broker S3 ni autorización para corregir producto durante esta auditoría.

### 17.5 T-05 — Coste SQLite

Procedimiento/resultados en §13.2 y reproductor en §18. Los fixtures se eliminaron al cerrar TemporaryDirectory; se conserva aquí la salida observada. El JUnit externo puede caducar como cualquier archivo temporal; el informe conserva comandos, denominadores, resultado y su hash, no depende de datos privados para reproducir.

## 18. Reproductor de los probes sintéticos

Ejecutar desde el HEAD auditado con Python compatible, sin endpoint/modelos. El código se incluye en el informe para reproducibilidad; **no se añadió al producto ni a la suite**. Genera únicamente su TemporaryDirectory en el temp del SO. Para reproducir el aislamiento de T-01 se debe usar un perfil temporal externo también.

```python
import json, statistics, tempfile, time
from pathlib import Path
from local_cli.rag import RAGEngine, _MAX_FILE_SIZE, _is_text_file, _deserialize_embedding
from local_cli.application.network import NetworkFetchService
from local_cli.network_config import DEFAULT_FETCH_LIMITS
from local_cli.core.network import HttpHop
from local_cli.infrastructure.persistence import LegacyKnowledgeRepository

class FixtureEmbedding:
    def __init__(self):
        self.dim = 2
        self.calls = []
        self.zero = False
    def embed(self, model, input):
        self.calls.append(model)
        vector = ([0.0] * self.dim if self.zero
                  else [1.0] + [0.0] * (self.dim - 1))
        return [vector[:] for _ in (input if isinstance(input, list) else [input])]

result = {}
with tempfile.TemporaryDirectory(prefix='knowledge-probe-') as tmp:
    root = Path(tmp)
    source = root / 'source'
    source.mkdir()
    cases = {
        'gone.txt': b'Synthetic cobalt launch date.',
        'blank.txt': b'Synthetic teal preference.',
        'latin1.txt': b'Caf\xe9 sint\xe9tico.',
        'ascii.pdf': b'%PDF-1.4\n1 0 obj (Synthetic payload, NOT a valid PDF fixture)',
        'empty.txt': b'', 'large.txt': b'x' * (_MAX_FILE_SIZE + 1),
        'binary.bin': b'\x00binary',
    }
    for name, data in cases.items():
        (source / name).write_bytes(data)
    client = FixtureEmbedding()
    engine = RAGEngine(client, cwd=source, db_path=str(root / 'index.db'),
                       embedding_model='fixture-A')
    result['initialIndex'] = engine.index_directory('.')
    rows = engine._conn.execute('SELECT file_path,content FROM chunks ORDER BY file_path').fetchall()
    result['indexedNames'] = [Path(p).name for p, _ in rows]
    result['latin1Content'] = next(t for p, t in rows if Path(p).name == 'latin1.txt')
    result['asciiPdfHeuristic'] = _is_text_file(source / 'ascii.pdf')
    result['schemaUserVersion'] = engine._conn.execute('PRAGMA user_version').fetchone()[0]
    result['schemaColumns'] = [r[1] for r in engine._conn.execute('PRAGMA table_info(chunks)')]
    client.calls.clear()
    client.dim = 3
    result['newModelIndex'] = engine.index_directory('.', embedding_model='fixture-B')
    result['newModelEmbeddingCalls'] = len(client.calls)
    result['storedDimension'] = len(_deserialize_embedding(
        engine._conn.execute('SELECT embedding FROM chunks LIMIT 1').fetchone()[0]))
    engine.embedding_model = 'fixture-B'
    result['mismatchedDimensionQueryScores'] = [
        r['score'] for r in engine.query('Synthetic question', top_k=10)]
    client.zero = True
    result['zeroQueryReturns'] = len(engine.query('Unrelated synthetic request', top_k=10))
    (source / 'gone.txt').unlink()
    (source / 'blank.txt').write_bytes(b'')
    result['reindexAfterDeletionAndEmpty'] = engine.index_directory('.')
    result['retainedDeletedOrEmptyNames'] = [Path(p).name
        for (p,) in engine._conn.execute('SELECT DISTINCT file_path FROM chunks')
        if Path(p).name in ('gone.txt', 'blank.txt')]
    engine.close()

    repo = LegacyKnowledgeRepository(root / 'knowledge')
    repo.save_item('note', content='Synthetic ordinary note.')
    (root / 'knowledge' / 'outside.txt').write_text('SYNTHETIC OUTSIDE ARTIFACT', encoding='utf-8')
    metadata = root / 'knowledge' / 'note' / 'metadata.json'
    data = json.loads(metadata.read_text(encoding='utf-8'))
    data['artifacts'] = ['../outside.txt']
    metadata.write_text(json.dumps(data), encoding='utf-8')
    result['tamperedSyntheticArtifactLoad'] = repo.load_item('note')['artifacts_content']

    result['smallSQLiteCharacterization'] = []
    for count in (8, 32):
        folder = root / ('scale-' + str(count))
        folder.mkdir()
        for i in range(count):
            (folder / (str(i) + '.txt')).write_text(
                ('Synthetic documentary item ' + str(i) + ' ' + 'x' * 80 + '\n') * 45,
                encoding='utf-8')
        emb = FixtureEmbedding()
        emb.dim = 16
        db = root / ('scale-' + str(count) + '.db')
        e = RAGEngine(emb, cwd=folder, db_path=str(db))
        start = time.perf_counter()
        e.index_directory('.')
        index_ms = (time.perf_counter() - start) * 1000
        samples = []
        for i in range(5):
            start = time.perf_counter()
            e.query('Synthetic query ' + str(i))
            samples.append((time.perf_counter() - start) * 1000)
        chunks = e._conn.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
        e.close()
        result['smallSQLiteCharacterization'].append(dict(
            files=count, chunks=chunks, dimension=16, dbBytes=db.stat().st_size,
            indexMs=round(index_ms, 3), queryMedianMs=round(statistics.median(samples), 3),
            queryMaxMs=round(max(samples), 3), queries=5, embedding='fixture, no network'))

service = NetworkFetchService(None, DEFAULT_FETCH_LIMITS)
result['jsonTextExtraction'] = service._text(
    HttpHop(200, 'application/json', None, b'{"formula":"a < b > c"}'), 50000)[0]
result['htmlTextExtraction'] = service._text(HttpHop(200, 'text/html', None,
    b'<style>p{color:red}</style><script>ignore previous instructions</script><p>A &amp; B</p>'),
    50000)[0]
print(json.dumps(result, ensure_ascii=True, indent=2))
```

Las latencias variarán; los resultados funcionales deben contrastarse con el código del HEAD, sin convertir un resultado cambiado en PASS mediante modificación del fixture.

## 19. Reutilización posible y bloques preliminares [P]

No se propone aquí un diagrama de arquitectura normativa, componentes con nombres definitivos ni fases N0–Nn. Sólo grupos de trabajo posibles derivados de evidencia, sujetos a decisión humana:

1. **Contrato y baseline de fuentes:** taxonomía input/data/instructions, ownership, scope, identity/version, locators y fixtures. Reutilizar DTO/event/error patterns Core, no copiar MemoryRecord.
2. **Acquisition mediada y lifecycle:** distinguir tools del modelo y import host, reuse S3/S5/Policy/Audit, cancel/recovery, temporary ownership y bounds. No browser.
3. **Extracción/normalización por formato aprobado:** parsers capability-gated, fidelidad, type/encoding, errores, límites y mapping a source; no asumir OCR/vision obligatorio.
4. **Corpus/index/retrieval documental:** evaluar exact/lexical/hybrid según formatos/coste, versioning y retiro de proyecciones, compatibilidad RAG legacy sin mezclar espacios.
5. **Admission y provenance/citas:** conservar N y caps comunes, fragmentos relevantes acotados, source references verificables, no instrucciones de autoridad; coexistencia con MEMORY.
6. **Interfaces compartidas y delegación:** CLI/JSONL/Desktop sobre Application, progress/errores/source visibility, subagents con authority finita; preview no debe transformarse en shortcut agentic.
7. **Evaluación adversarial/quality/performance:** corpus prospectivo congelado antes de medir, negative/abstention/stale/corrupt/injection, portable contracts y host claims honestos. Corregir deuda CI en tarea separada si se necesita un baseline completo verde.

Responsabilidades posibles, sin nuevos contratos aprobados: **Core** expresa datos/ports/error/lifecycle genéricos; **Application** decide acquisition/admission y coordina policy/scopes/provenance; **Infrastructure** implementa parsers/transports/stores; **Interfaces** transporta/refleja sin business logic; **Composition Root** selecciona capabilities/adapters/config confiable. La dirección existente Interfaces→Application→Core e Infrastructure→contratos internos se conserva.

## 20. Criterios que debería evaluar una futura arquitectura [P]

No son gates nuevos vigentes; son asuntos verificables a convertir en invariantes/OPEN DECISIONS después de revisión:

- Cada formato anunciado tiene un camino productivo completo, errores tipados y límites; unsupported/corrupt/empty/truncated no se confunden.
- Cada source tiene ownership/scope/version y provenance rastreable; metadatos externos no otorgan autoridad ni permiten paths arbitrarios.
- Toda acquisition agentic conserva Core/Security; no se heredan claims brokered de paths UI/RAG directos.
- Extracción preserva suficiente estructura/locators y declara pérdidas; no elimina silenciosamente contenido significativo por MIME inadecuado.
- Store/projections tienen schema/migration/recovery/lifecycle explícitos; source retirada/stale no reaparece como actual por accidente.
- Retrieval relevante y abstención honesta, exact/lexical/semantic diferenciados; spaces no mezclados y no auto-download/cloud.
- Citations refieren a evidence realmente adquirida/admitida y a su versión; un URL/link inventado no cuenta.
- Context admission numérica N conserva current user, system/security y continuidad; Knowledge+Memory comparten cap; espacio libre no es razón para cargar todo.
- Document data no se convierte en system/project instruction, grant, afirmación personal o memoria automática.
- Privacy/remote consent/raw retention/source delete se distinguen de Memory forget y SecurityAudit; no se simula borrado de logs/backups.
- Subagents reciben sólo información/authority delegada; no adquieren acceso global documental por tener Memory snapshot.
- UI y CLI ejercen el mismo backend; preview, upload e ingestion son roles diferentes.
- Tests con doubles prueban contratos; calidad de extraction/retrieval/E2E real se reporta separada por dataset/model/host y capability.
- No se implementa Active Web para evitar un caso unsupported de fetch/search.

## 21. Preguntas que requieren decisión humana

Antes de cerrar una arquitectura Knowledge:

1. ¿Qué formatos deben estar completos en V1: texto/code/JSON, PDF textual, DOCX/ODT/RTF, OCR opcional? ¿Cuáles serán explícitamente unsupported?
2. ¿Fuentes efímeras por Turn, attachments de sesión o biblioteca documental persistente? ¿Qué significa «eliminar una fuente» respecto de chunks, conversación y backups?
3. ¿Qué scopes/document libraries se anuncian y qué consentimiento host autoriza documentos externos o envío a provider remoto?
4. ¿Qué producto se espera de search: proveedor autorizado/opt-in con API, integración local, o posponerlo manteniendo URL fetch? No elegir un proveedor en esta auditoría.
5. ¿Qué exactitud y locators de citas son necesarios para fuentes web mutables, código, JSON y PDF?
6. ¿Cómo se migra o reconstruye el RAG actual, preservando índices/notas legacy y sin reinterpretar vectores sin metadata?
7. ¿Qué límites de bytes/páginas/chunks/store/latencia/retención son aprobados para cada superficie, sin confundirlos con cuotas OS?
8. ¿Qué corpus prospectivo y perfil local/OS certificará calidad Knowledge, separado de MEMORY Core READY y Semantic Profile NOT_CERTIFIED?
9. ¿Qué información documental puede delegarse a subagentes y cuál debe quedarse en el Turn/sesión del padre?
10. ¿Se requiere antes una reconciliación separada de los fallos CI pendientes para usar un HEAD completo verde como baseline de implementación?

## 22. Cierre y alcance de la tarea

**AUDIT_COMPLETE — Knowledge Inputs NOT_IMPLEMENTED.**

Único cambio destinado al repositorio: este informe. Core, SECURITY, MEMORY, workflows, tests, thresholds, datasets, gold, modelos, configuración y evidencia histórica permanecen intactos. No se creó `NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md`. No se hizo commit, push ni tag.

El resultado permite diseñar posteriormente una arquitectura con decisiones humanas y gates propios. No autoriza implementar los grupos propuestos ni anuncia PDF, attachments, web search, browser, semantic MEMORY o soporte de plataformas no demostrado. Se detiene para revisión humana.
