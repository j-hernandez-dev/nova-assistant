# NOVA Knowledge Inputs — Arquitectura V1

**Estado:** propuesta normativa para implementación  
**Etapa:** 4 — Knowledge Inputs  
**Base:** `AUDITORIA_KNOWLEDGE_INPUTS_NOVA_V1.md` (`AUDIT_COMPLETE`)  
**Dependencias normativas:** Nova Core V1, SECURITY V1.2, MEMORY V1  
**Perfil inicial de certificación:** Windows 11 + NTFS local + `HOST_UNISOLATED`  

---

## 1. Propósito

Knowledge Inputs V1 amplía Nova para que pueda **adquirir, extraer, organizar, recuperar y citar información externa** sin convertirla en memoria personal ni introducir todavía navegación web activa.

Incluye:

- attachments seleccionados por el usuario;
- archivos locales importados explícitamente;
- texto, Markdown, código y datos textuales;
- PDF textual;
- DOCX;
- URLs HTTP(S) públicas mediante adquisición pasiva;
- búsqueda web pasiva mediante provider configurable;
- extracción y normalización por formato;
- indexación documental;
- retrieval exacto/lexical obligatorio;
- retrieval semántico documental opcional;
- provenance y citas estructuralmente verificables;
- incorporación acotada de evidencia al contexto;
- coexistencia con MEMORY;
- delegación documental acotada a subagentes;
- backend común para CLI, JSONL y Desktop.

Knowledge Inputs V1 **no convierte a Nova en un navegador autónomo**.

---

## 2. Fuera de alcance

Queda fuera de V1:

- DOM controlado por el agente;
- ejecución de JavaScript de páginas para navegar;
- clicks y formularios;
- browser automation;
- cookies o sesiones autenticadas de sitios;
- navegación multi-step;
- acciones sobre sitios;
- scraping autenticado interactivo;
- OAuth agentic;
- CAPTCHA;
- sandboxing o process isolation;
- OCR obligatorio;
- visión obligatoria;
- soporte universal de formatos documentales;
- garantía universal contra prompt injection;
- DLP o detección universal de secretos;
- memoria automática derivada de documentos;
- recertificación de `SEMANTIC_PROFILE` de MEMORY.

Estas capacidades pertenecen a etapas posteriores o perfiles opcionales separados.

---

## 3. Precedencia normativa

En caso de conflicto:

1. **Nova Core V1** gobierna Session / Turn / Generation / Operation, comandos, eventos, snapshots, cancelación, outcomes, composición de contexto y AgentLoop.
2. **SECURITY V1.2** gobierna ToolRuntime, Policy, Approval, grants, filesystem broker, red, `web_fetch`, audit y el alcance `HOST_UNISOLATED`.
3. **MEMORY V1** gobierna MemoryStore, MemoryCapsule, correction/forget/no-resurrection y la separación Memory ≠ Knowledge.
4. **Knowledge Inputs V1** añade únicamente Source, SourceRevision, extracción, chunking documental, retrieval documental, provenance, citations, attachments e interfaces de búsqueda web pasiva.

Knowledge Inputs no redefine contratos ya cerrados.

---

## 4. Principio central de dominio

La siguiente separación es normativa:

```text
Current user input
≠ Conversation history
≠ MEMORY
≠ Knowledge source
≠ ToolResult
≠ System/Project instruction
≠ Security authority
```

Una fuente adquirida es **dato externo, no autoridad**.

Flujo válido:

```text
Documento
→ datos
→ extracción
→ evidencia
→ retrieval
→ contexto acotado
```

Flujos prohibidos:

```text
Documento → system instruction
Documento → grant/approval
Documento → memoria personal automática
```

---

## 5. Objetivos de diseño

Knowledge Inputs V1 debe ser:

- local-first;
- determinista en identity/version/lifecycle;
- útil sin embeddings;
- compatible con ventanas pequeñas;
- explícito sobre provenance;
- explícito sobre límites y degradación;
- fail-closed ante metadata/path no confiable;
- resistente a contenido instruction-like sin prometer inmunidad del LLM;
- separable de Active Web;
- compatible con Core, SECURITY y MEMORY ya certificados.

---

# Parte I — Modelo de fuentes

## 6. Entidades normativas

### 6.1 `Source`

Representa una fuente lógica:

```text
Source
- sourceId
- kind
- scope
- origin
- displayName
- trustClass
- createdAt
- currentRevisionId?
- lifecycleState
- remotePolicy
```

`sourceId` es un UUID generado por Nova. Path, URL, filename y hash no son identidad primaria.

### 6.2 `SourceRevision`

Cada adquisición concreta crea una revisión inmutable:

```text
SourceRevision
- revisionId
- sourceId
- contentDigest
- acquiredAt
- mediaType
- byteLength
- originFingerprint?
- extractorProfile
- extractionStatus
- extractedDigest?
- previousRevisionId?
```

Regla: **una revisión publicada nunca cambia de significado**. Si cambia el contenido, se crea otra revisión.

### 6.3 `ExtractedDocument`

```text
ExtractedDocument
- revisionId
- title?
- mediaType
- language?
- blocks[]
- warnings[]
- extractionCompleteness
```

### 6.4 `DocumentBlock`

```text
DocumentBlock
- blockId
- kind
- text
- locator
- order
- metadata
```

Tipos posibles: `heading`, `paragraph`, `code`, `table`, `list`, `json_value`, `html_section`, `pdf_text`, `docx_paragraph`.

### 6.5 `DocumentChunk`

```text
DocumentChunk
- chunkId
- revisionId
- ordinal
- text
- normalizedTextHash
- locatorStart
- locatorEnd
- lexicalProjection
- semanticSpaceId?
```

### 6.6 `SourceLocator`

Depende del formato:

- texto/código: líneas;
- PDF: páginas y rango interno opcional;
- DOCX: sección/párrafo;
- JSON: JSON Pointer + rango opcional;
- HTML/Web: URL canónica + bloque textual;
- Search result: rango y URL del resultado.

El locator debe permitir responder **dónde se obtuvo la evidencia** sin depender de texto inventado por el modelo.

---

## 7. Tipos de fuente V1

```text
LOCAL_FILE
ATTACHMENT
WORKSPACE_IMPORT
URL_SNAPSHOT
WEB_SEARCH_RESULT
LEGACY_KNOWLEDGE_NOTE
PROJECT_SOURCE
```

`WEB_SEARCH_RESULT` es efímero por defecto y no equivale a una página fetched.

---

## 8. Scope y ownership

V1 define sólo:

```text
SESSION
WORKSPACE
```

### SESSION

- attachments y fuentes transitorias;
- no cruzan automáticamente entre sesiones;
- pueden conservarse temporalmente para recovery;
- no se convierten a WORKSPACE sin acción explícita.

### WORKSPACE

- biblioteca documental persistente del proyecto;
- sobrevive reinicios;
- no cruza automáticamente a otro workspace.

V1 **no introduce biblioteca documental global**.

---

# Parte II — Adquisición

## 9. Caminos de adquisición

Se distinguen tres:

### 9.1 Host import

Acción explícita del usuario desde Desktop, CLI o JSONL trusted host interface. No es una tool del modelo.

### 9.2 Agentic acquisition

Tools como:

- `read`;
- `grep`;
- `glob`;
- `web_fetch`;
- `web_search`.

Siempre pasan por ToolRuntime y SECURITY.

### 9.3 Project corpus activation

Un directorio de proyecto puede convertirse en corpus, pero debe pasar por Source/Revision. El scanner RAG legacy no define por sí solo autoridad ni provenance suficiente.

---

## 10. Autoridad de archivos

### Desktop

```text
Renderer
→ request picker
→ trusted Desktop main process
→ selected file handle/path
→ Application ImportSource
→ validation
→ acquisition
```

El renderer no puede inventar un path y convertirlo directamente en fuente.

### CLI

Un path escrito explícitamente por el usuario es host intent, no model authority; aun así se valida.

### Metadata persistida

Nunca se abre un path arbitrario tomado de metadata externa. Toda referencia interna usa IDs y containment comprobado.

Se prohíbe resolver sin nueva autorización:

```text
../
absolute-path-from-metadata
symlink escape from managed artifact root
```

---

## 11. Adquisición HTTP(S)

Se reutiliza SECURITY S5 / `web_fetch`:

- `PUBLIC_ONLY`;
- HTTP(S);
- DNS/redirect verification;
- TLS validation;
- no ambient proxy/netrc/cookies;
- máximo 5 redirects;
- presupuesto HTTP 30 s;
- máximo 2 MiB body retenido para `web_fetch`;
- truncamiento según límites existentes.

Knowledge Inputs no relaja esos límites.

### URL snapshot persistente

Importar una URL a WORKSPACE crea una revisión con:

- requested URL;
- effective URL;
- acquiredAt;
- content hash;
- media type;
- headers seguros seleccionados;
- ETag / Last-Modified si existen;
- extraction profile.

Es un snapshot, no una vista “viva” de Internet. Refresh es explícito.

---

# Parte III — Formatos y extracción

## 12. Supported Formats V1

### Obligatorios para `NOVA_KNOWLEDGE_INPUTS_V1_READY`

- TXT;
- Markdown;
- código fuente textual;
- JSON;
- CSV;
- HTML;
- PDF textual;
- DOCX;
- texto HTTP(S) compatible con esos MIME.

### Opcionales, no bloqueantes

- OCR;
- image-only PDF;
- imágenes;
- XLSX;
- PPTX;
- ODT;
- RTF;
- EPUB.

Su ausencia no bloquea READY base.

Un archivo `.pdf` leído como texto heurístico **no cuenta** como soporte PDF.

---

## 13. Detección de tipo

Se usa, en orden:

1. acquisition context;
2. MIME confiable;
3. signature/sniff de bytes;
4. extensión;
5. fallback textual sólo si pasa validación.

Discordancias producen `TYPE_MISMATCH`; no se ignoran silenciosamente.

---

## 14. Encoding

### Remoto

1. BOM;
2. charset HTTP válido;
3. UTF-8;
4. fallback explícito del extractor.

### Local

1. BOM;
2. UTF-8;
3. Windows-1252 para legacy text si el perfil lo permite.

No se usa reemplazo silencioso para publicar una extracción como completa. Si hay pérdida:

```text
extractionCompleteness = PARTIAL
warning = LOSSY_DECODE
```

---

## 15. Extracción por formato

### Texto / Markdown / código

Preserva líneas, headings detectables, bloques de código y rangos.

### JSON

Se parsea como JSON; no se aplica stripping HTML. Conserva JSON Pointer y estructura. JSON inválido produce `CORRUPT_DOCUMENT`, salvo import explícito como texto.

### HTML

- elimina `script`;
- elimina `style`;
- decodifica entidades;
- conserva texto visible útil;
- conserva headings/links como metadata;
- no ejecuta JavaScript.

### PDF textual

Debe usar parser PDF real y conservar número de página. PDF cifrado/no legible: `UNSUPPORTED_ENCRYPTED_DOCUMENT`. PDF image-only sin OCR capability: `OCR_REQUIRED`.

### DOCX

Se trata como contenedor ZIP no confiable. Debe limitar entries/bytes expandidos, comprobar containment, extraer párrafos/headings/tablas básicas, no ejecutar macros y no seguir relaciones externas automáticamente.

---

## 16. Estados y límites de extracción

Estados:

```text
NOT_STARTED
EXTRACTING
READY
PARTIAL
UNSUPPORTED
CORRUPT
FAILED
CANCELLED
```

Defaults V1:

```text
maxLocalSourceBytes       = 50 MiB
maxPdfPages               = 500
maxContainerEntries       = 2_000
maxExpandedContainerBytes = 100 MiB
maxCompressionRatio       = 100:1
maxExtractedCharacters    = 5_000_000
maxChunksPerSource        = 5_000
```

Son límites operacionales/configurables, no cuotas del SO.

---

# Parte IV — Chunking, store e indexación

## 17. Chunking

V1 reemplaza el chunking fijo legacy.

Principios:

- respetar estructura;
- conservar locator;
- determinismo;
- bounds claros.

Defaults:

```text
targetChunkTokens ≈ 700
hardChunkTokens   ≈ 1_000
overlapTokens     ≈ 100
```

Si no existe tokenizer exacto se usa el estimador Core documentado y se registra en el profile de chunking.

## 18. Knowledge Store V1

Autoridad documental:

```text
<state_dir>/knowledge/v1/
```

Estructura conceptual:

```text
knowledge/v1/
├── knowledge.db
├── blobs/
├── staging/
└── cache/
```

`knowledge.db` debe usar schema versionado, `PRAGMA user_version`, foreign keys, migrations explícitas, transactions y recovery probado.

Tablas conceptuales:

```text
sources
source_revisions
documents
document_blocks
chunks
chunk_fts
semantic_spaces
semantic_vectors
source_tombstones
import_operations
```

Los bytes persistentes pueden almacenarse por digest. El path original no es la autoridad del contenido ya importado.

---

## 19. Lifecycle de sources

Estados:

```text
IMPORTING
READY
PARTIAL
SUPERSEDED
FAILED
DELETED
```

Al cambiar una fuente se crea una nueva revisión. La revisión anterior pasa a `SUPERSEDED` sólo después de publicar la nueva correctamente.

Delete de source:

- retira la revisión actual del retrieval;
- elimina FTS/vector projections;
- invalida caches;
- elimina blobs administrados cuando corresponda;
- registra tombstone mínimo;
- evita resurrection por rebuild.

No implica borrar transcript, Security Audit, backups externos o realizar secure erase.

---

## 20. Atomicidad de import

```text
Acquire
→ validate
→ extract
→ chunk
→ index staging
→ validate
→ atomic publish currentRevision
```

Si hay crash/cancel antes de publish:

- la revisión no se anuncia READY;
- no se mezcla con la anterior;
- staging huérfano puede limpiarse en recovery.

`currentRevisionId` nunca se actualiza antes de completar las proyecciones obligatorias.

---

# Parte V — Retrieval documental

## 21. Retrieval Core obligatorio

Knowledge Inputs V1 debe funcionar **sin embeddings**.

Obligatorio:

- exact match;
- SQLite FTS5;
- filtros por scope;
- source/revision state;
- MIME/kind cuando aplique;
- ranking determinista;
- abstention cuando no exista evidencia suficiente.

Embeddings no son dependencia de READY Core.

---

## 22. Semantic Document Profile

Es independiente de MEMORY Semantic Profile.

Estados:

```text
DISABLED
UNAVAILABLE
AVAILABLE
DEGRADED
NOT_CERTIFIED
CERTIFIED
```

Reglas:

- no auto-download;
- no auto-start de modelo;
- no obligación de residencia;
- no usar chat model implícitamente como embedder;
- fallback lexical siempre disponible;
- fallo semantic no elimina lexical;
- spaces no se mezclan.

`DocumentEmbeddingSpace` identifica al menos:

```text
provider
model
modelDigest/revision
dimension
preprocessingProfile
chunkingProfile
```

Cualquier cambio crea un space nuevo.

---

## 23. Fusión y caps

Cuando semantic esté habilitado:

```text
metadata filters
→ lexical candidates
+ semantic candidates
→ deterministic fusion
→ dedup
→ relevance floor
→ source/version validation
→ context admission
```

No se requiere LLM reranker pesado.

Defaults:

```text
lexicalCandidates  <= 32
semanticCandidates <= 32
mergedCandidates   <= 24
finalEvidence      <= 10
```

El ContextManager puede admitir menos.

---

## 24. Abstención

Si no hay evidencia suficientemente relevante:

```text
retrieval = NONE
```

No se rellenará contexto con chunks de score cero o irrelevantes. Los thresholds se congelan antes de medir calidad.

---

# Parte VI — Context admission y MEMORY

## 25. Un solo presupuesto de retrieval

Se conserva:

```text
MEMORY + Knowledge/RAG <= SharedRetrievalCap
```

No se crea un segundo presupuesto de retrieval.

Knowledge no puede saltarse:

- current user priority;
- system;
- schemas;
- continuidad tools;
- ToolResults;
- output reserve;
- safety margin.

---

## 26. KnowledgeCapsule

El material documental admitido se congela por Turn:

```text
KnowledgeCapsule
- turnId
- evidence[]
- sourceRegistry
- citationRegistry
- tokenCost
- retrievalMode
```

Una Generation posterior no relanza todo el retrieval salvo una nueva Operation explícita permitida por Core.

La evidencia se presenta como datos, no instrucciones.

---

# Parte VII — Provenance y citas

## 27. Citation Registry

Cada Turn asigna IDs opacos:

```text
K1
K2
K3
...
```

Cada ID referencia:

```text
CitationTarget
- sourceId
- revisionId
- chunkId?
- locator
- displayLabel
- originDisplay
```

Sólo se crean IDs para evidencia realmente admitida.

---

## 28. Citations emitidas por el modelo

El modelo puede emitir `[K1]`, `[K2]`, etc.

Application valida:

- que el ID exista;
- que pertenezca al Turn;
- que source/revision coincida;
- que locator sea válido;
- que la evidencia haya sido admitida.

Un ID inventado nunca cuenta como cita válida.

**Límite:** validación estructural no prueba entailment semántico. Una cita válida demuestra que la referencia existe y fue admitida, no que toda afirmación esté demostrada por ella.

---

## 29. Source mutable/deleted

Una respuesta histórica conserva `Source X / Revision Y` aunque después la fuente se actualice o elimine.

La UI podrá marcar:

```text
CURRENT
SUPERSEDED
DELETED
```

sin reescribir respuestas históricas.

---

# Parte VIII — Web Search pasivo

## 30. `WebSearchPort`

Contrato conceptual:

```text
search(query, options, cancellation) -> SearchResponse
```

Incluye provider id, query fingerprint, timestamp y resultados con title, URL, snippet, rank y metadata opcional.

No contiene browser session.

---

## 31. Search provider

Knowledge V1 no fija proveedor comercial único. El Composition Root elige uno.

Estados:

```text
DISABLED
UNAVAILABLE
AVAILABLE
DEGRADED
```

Un provider remoto está deshabilitado hasta configuración explícita. Sus credenciales nunca llegan al modelo ni al prompt.

Un snippet del buscador se marca como `SEARCH_PROVIDER_SNIPPET`. No se presenta como contenido completo de la página. Para adquirir la página se usa `web_fetch` y SECURITY existentes.

---

# Parte IX — Attachments e interfaces

## 32. Attachment input

`SubmitUserInput.content` sigue siendo texto. Attachments viajan en referencias separadas:

```text
SubmitUserInput
- content
- attachmentRefs[]
```

No se concatena silenciosamente un documento al mensaje del usuario. Así se conserva:

```text
user assertion ≠ document content
```

`AttachmentRef` contiene conceptualmente:

```text
attachmentId
sourceId
revisionId?
displayName
state
```

La UI no necesita conocer paths internos.

---

## 33. Paridad de backend

CLI, JSONL y Desktop usan Application.

Queda prohibido crear:

```text
Desktop parser propio
Desktop DB propio
Renderer → direct RAG bypass
```

Preview no equivale a ingestion.

UX mínima permitida en esta etapa:

- seleccionar attachment;
- mostrar importing/ready/partial/failed;
- remover attachment;
- listar sources;
- refresh explícito;
- delete;
- mostrar source/citation detail.

El rediseño completo queda para Nova Desktop.

---

# Parte X — MEMORY

## 34. Memory ≠ Knowledge

Prohibido:

```text
document text → AUTO_SAFE memory
RAG chunk → USER_ASSERTION
web search result → personal preference
tool output → global memory
```

Si el usuario pide explícitamente “recordar esto del documento”:

1. Application identifica intención explícita;
2. crea propuesta MEMORY;
3. adjunta provenance opcional;
4. MEMORY aplica su policy;
5. el write sigue perteneciendo a MEMORY.

Knowledge nunca escribe directamente en MemoryStore.

---

# Parte XI — Subagentes

## 35. Delegación

Un child no recibe acceso global al corpus.

El padre puede delegar:

```text
DelegatedKnowledgeCapsule
- selectedEvidenceRefs
- allowedSourceRevisionIds
- tokenBudget
- optionalAcquisitionCeiling
```

Nuevas adquisiciones del child pasan por el mismo ToolRuntime y ceiling heredado/atenuado.

---

# Parte XII — Trust, injection y privacidad

## 36. Trust classes

```text
USER_SELECTED_LOCAL
WORKSPACE_IMPORTED
PUBLIC_WEB_FETCH
WEB_SEARCH_SNIPPET
LEGACY_IMPORTED
```

Afectan presentación, privacy y provenance. **No** alteran system priority, grants ni instruction authority.

---

## 37. Instruction-like content

Texto como “ignore previous instructions” permanece dato. No se depende de un clasificador perfecto; la defensa primaria es:

```text
external content ≠ control plane
```

Detectores/warnings pueden existir, pero no son la frontera de seguridad.

---

## 38. Secretos y remote forwarding

Knowledge Inputs no afirma detectar todos los secretos.

Default:

```text
remoteDocumentForwarding = false
```

Fuentes locales sólo pueden enviarse a chat provider remoto si host/user lo autoriza. Habilitar web search remoto **no** autoriza envío de documentos locales.

No se loguean documentos completos por default.

---

# Parte XIII — Cache, refresh y retention

## 39. Cache

```text
source snapshot ≠ cache
```

Se permiten:

- extraction cache por content digest;
- query cache acotado en memoria;
- ETag/Last-Modified para refresh.

No existe cache remoto persistente ilimitado.

---

## 40. Refresh

Refresh es explícito en V1; no se requiere watcher, polling o background TTL fetch.

```text
refresh
→ acquire
→ compare digest
→ unchanged OR new revision
```

---

## 41. Capacity defaults

```text
maxSessionKnowledgeBytes   = 256 MiB
maxWorkspaceKnowledgeBytes = 2 GiB
maxWorkspaceSources        = 2_000
maxWorkspaceChunks         = 100_000
```

Son soft/operational limits, no cuotas OS. Al alcanzarlos se rechaza nueva importación o se pausa; delete/export siguen disponibles. No hay purge automático de contenido persistente estable.

Sources SESSION se limpian best-effort al cerrar/recover; no se promete secure erase.

---

# Parte XIV — Async, cancel y recovery

## 42. Imports como Operations

Estados conceptuales:

```text
QUEUED
ACQUIRING
EXTRACTING
INDEXING
COMMITTING
SUCCEEDED
FAILED
CANCELLED
OUTCOME_UNKNOWN
```

Cancel es cooperativo entre unidades acotadas: reads, páginas, entries, chunks y embedding batches. Cancel no significa que ningún byte haya sido leído.

Recovery:

- detecta staging huérfano;
- valida si hubo publish;
- no inventa success;
- conserva revisión anterior si la nueva no llegó a commit;
- limpia temporales sólo con ownership inequívoco.

---

# Parte XV — Compatibilidad legacy

## 43. RAG legacy

Los vectores legacy **no se reinterpretan** como V1 porque no tienen metadata suficiente de model/digest/dim/preprocess/space.

```text
legacy vectors → no direct migration
```

Si el corpus original existe, V1 lo reconstruye desde sources.

Legacy Knowledge notes se preservan y pueden exponerse read-only o importarse explícitamente. No se destruyen automáticamente.

---

# Parte XVI — Error model y capabilities

## 44. Errores tipados mínimos

```text
SOURCE_NOT_FOUND
SOURCE_NOT_AUTHORIZED
SOURCE_TOO_LARGE
SOURCE_CAPACITY_EXCEEDED
UNSUPPORTED_FORMAT
UNSUPPORTED_ENCRYPTED_DOCUMENT
OCR_REQUIRED
TYPE_MISMATCH
INVALID_ENCODING
CORRUPT_DOCUMENT
EXTRACTION_PARTIAL
EXTRACTION_FAILED
IMPORT_CANCELLED
INDEX_FAILED
SEMANTIC_UNAVAILABLE
SEMANTIC_SPACE_MISMATCH
REMOTE_SEARCH_DISABLED
REMOTE_FORWARDING_DENIED
CITATION_INVALID
STALE_SOURCE
LEGACY_REBUILD_REQUIRED
```

---

## 45. Capability Snapshot

Knowledge publica capacidades reales:

```text
attachments
pdfText
docx
html
webFetch
webSearch
workspaceLibrary
lexicalRetrieval
semanticRetrieval
ocr
```

Estados:

```text
AVAILABLE
UNAVAILABLE
DEGRADED
DISABLED
NOT_CERTIFIED
```

La UI sólo anuncia lo que el snapshot permite.

---

# Parte XVII — Observabilidad

## 46. Eventos mínimos

```text
knowledge.import.started
knowledge.import.completed
knowledge.import.failed
knowledge.import.cancelled
knowledge.source.refreshed
knowledge.source.deleted
knowledge.retrieval.completed
knowledge.semantic.degraded
knowledge.citation.invalid
knowledge.capacity.hit
```

Se registran IDs, scope, kind, mediaType, bytes, chunks, timings, counts y error type. No se loguea por default documento completo, raw attachment ni secretos.

---

# Parte XVIII — Calidad y certificación

## 47. Perfiles separados

```text
KNOWLEDGE_CORE
DOCUMENT_SEMANTIC_PROFILE
OCR_PROFILE
```

`NOVA_KNOWLEDGE_INPUTS_V1_READY` exige `KNOWLEDGE_CORE`.

No exige Semantic ni OCR.

---

## 48. Corpus prospectivo

Antes de K8 se congela un corpus nuevo que incluya:

- TXT/MD/código/JSON/CSV/HTML/PDF/DOCX;
- source updates;
- delete;
- stale/superseded;
- corrupt/unsupported;
- encoding;
- injection-like text;
- negative queries;
- conflictos entre fuentes;
- texto repetido con provenance distinta;
- citations;
- multi-session/workspace isolation.

No se seleccionan casos por outcome.

---

## 49. `KNOWLEDGE_CORE_QUALITY`

### Extraction

```text
supported-format parse success >= 98%
critical locator/source mapping = 100%
unsupported/corrupt typing = 100% en set crítico
```

### Lexical retrieval

En subset lexical-supportable:

```text
Recall@5 >= 90%
Precision@1 >= 85%
```

### Abstention

```text
correct abstention >= 95%
```

### Citation structural validity

```text
invalid accepted citation IDs = 0
citation → admitted revision/locator = 100%
```

### Critical invariants

Scope, delete/no-resurrection, metadata containment, source versioning, Memory separation, authority separation e injection authority:

```text
100%
```

---

## 50. `DOCUMENT_SEMANTIC_PROFILE_QUALITY`

Sólo aplica si se quiere publicar `CERTIFIED`.

Corpus propio de paraphrase/low lexical overlap:

```text
Recall@5 >= 85%
Precision@1 >= 80%
hybrid improvement over lexical >= +5 pp
```

Además exige spaces versionados, warm availability, no auto-download, bounded latency y lexical fallback.

Si falla:

```text
DOCUMENT_SEMANTIC_PROFILE = NOT_CERTIFIED
```

sin bloquear Knowledge Core READY.

---

## 51. E2E con modelo local real

K8 debe probar al menos:

- attachment → answer;
- PDF → answer + citation;
- DOCX → answer + citation;
- JSON/code → answer;
- workspace library multi-session;
- Memory + Knowledge coexistence;
- URL fetch;
- web search pasivo si provider está habilitado para la campaña;
- stale/superseded;
- delete/no-resurrection;
- prompt injection documentaria;
- source conflict;
- abstention.

El scorer distingue retrieval failure, citation failure, model behavior y product contract failure. Guesses no cuentan como retrieval success.

---

## 52. Performance

Core:

```text
FTS query p95 <= 100 ms
```

sobre corpus/host aprobados.

Semantic, si se certifica:

```text
warm retrieval pipeline p95 <= 500 ms
```

sin generación del chat.

Imports no necesitan SLA rígido total, pero deben progresar, cancelar cooperativamente, respetar límites y no bloquear un Turn no relacionado.

---

# Parte XIX — Invariantes

## 53. Invariantes normativos

1. **KI-INV-001** — Todo source publicado tiene `sourceId` y `revisionId` explícitos.
2. **KI-INV-002** — `SourceRevision` publicada es inmutable.
3. **KI-INV-003** — Cambio de contenido genera nueva revisión.
4. **KI-INV-004** — Knowledge no reutiliza MemoryRecord/tablas/lifecycle MEMORY.
5. **KI-INV-005** — Document content nunca se convierte en system/project instruction por adquisición.
6. **KI-INV-006** — Document content nunca crea grants/approvals/authority.
7. **KI-INV-007** — Knowledge no escribe MEMORY automáticamente.
8. **KI-INV-008** — Metadata que abre blobs/artifacts se valida por ownership/containment.
9. **KI-INV-009** — No se heredan claims S3 de rutas que no pasan por S3.
10. **KI-INV-010** — Agentic file/network acquisition usa ToolRuntime/SECURITY.
11. **KI-INV-011** — Host import y model tool acquisition se distinguen.
12. **KI-INV-012** — `web_search` no implica browser automation.
13. **KI-INV-013** — Search result no equivale a fetched page.
14. **KI-INV-014** — Cada formato anunciado tiene parser/extractor real.
15. **KI-INV-015** — Unsupported/corrupt/partial no se presenta como READY completo.
16. **KI-INV-016** — Todo chunk conserva locator hacia una revisión.
17. **KI-INV-017** — Toda cita válida apunta a evidencia admitida en el mismo Turn.
18. **KI-INV-018** — Citation ID inventado nunca se publica como válido.
19. **KI-INV-019** — Citation validity no se vende como entailment automático.
20. **KI-INV-020** — Exact/FTS funciona sin embeddings.
21. **KI-INV-021** — Fallo semantic conserva lexical.
22. **KI-INV-022** — Embedding spaces documentales están versionados y no se mezclan.
23. **KI-INV-023** — Legacy vectors no se reinterpretan como V1.
24. **KI-INV-024** — Delete retira projections V1 y evita resurrection.
25. **KI-INV-025** — Delete source ≠ Memory forget/transcript erase/audit erase/secure erase.
26. **KI-INV-026** — MEMORY + Knowledge usan un SharedRetrievalCap.
27. **KI-INV-027** — Current user mantiene prioridad.
28. **KI-INV-028** — Knowledge context puede ser cero.
29. **KI-INV-029** — Workspace isolation es obligatoria.
30. **KI-INV-030** — Subagents sólo reciben evidencia/authority delegada.
31. **KI-INV-031** — Remote search y remote document forwarding son controles independientes.
32. **KI-INV-032** — Habilitar web search no autoriza enviar documentos locales.
33. **KI-INV-033** — Imports publican revisión sólo tras commit obligatorio.
34. **KI-INV-034** — Cancel/crash no convierte staging incompleto en READY.
35. **KI-INV-035** — Bounds de bytes/páginas/chunks se aplican antes de crecimiento ilimitado.
36. **KI-INV-036** — OCR no es requisito de READY Core.
37. **KI-INV-037** — Semantic documental no es requisito de READY Core.
38. **KI-INV-038** — Active Web no se implementa como workaround.
39. **KI-INV-039** — CLI/JSONL/Desktop usan Application como autoridad de negocio.
40. **KI-INV-040** — Preview UI no constituye ingestion ni authority agentic.

---

# Parte XX — Resolución de Open Decisions

## 54. KI-OD-01…28

| ID | Decisión V1 |
|---|---|
| KI-OD-01 | `SourceId` UUID + `SourceRevision` inmutable con digest. |
| KI-OD-02 | Separar Source, Revision, ExtractedDocument, Block y Chunk. |
| KI-OD-03 | Scopes SESSION y WORKSPACE; sin biblioteca global. |
| KI-OD-04 | Attachments SESSION por defecto; persistencia WORKSPACE explícita. |
| KI-OD-05 | READY: text/MD/code/JSON/CSV/HTML/PDF textual/DOCX; OCR y otros opcionales. |
| KI-OD-06 | MIME/signature/extension + encoding explícito; no replacement silencioso. |
| KI-OD-07 | Extraction READY/PARTIAL/UNSUPPORTED/CORRUPT/FAILED con warnings. |
| KI-OD-08 | Chunking structure-aware con locators; target ~700, hard ~1000 tokens. |
| KI-OD-09 | Exact/FTS obligatorio; semantic/hybrid opcional. |
| KI-OD-10 | Embedding space documental separado/versionado. |
| KI-OD-11 | Dedup por revision/chunk hash sin perder provenance distinta. |
| KI-OD-12 | Refresh explícito; revisioning; delete con tombstone y retiro de projections. |
| KI-OD-13 | Citation registry turn-local validado estructuralmente. |
| KI-OD-14 | Reutilizar PUBLIC_ONLY S5; URL persistente = snapshot. |
| KI-OD-15 | `WebSearchPort` abstracto, provider configurable/opt-in; sin browser. |
| KI-OD-16 | Trust classes descriptivas; fuente nunca obtiene autoridad. |
| KI-OD-17 | Local-first; remote forwarding off por default; sin claim DLP universal. |
| KI-OD-18 | Reusar SharedRetrievalCap; sin segundo presupuesto. |
| KI-OD-19 | Memory separado; recordar fuente requiere intención explícita y policy MEMORY. |
| KI-OD-20 | Subagent recibe capsule/source refs delegados, no corpus global. |
| KI-OD-21 | Backend Application común; attachments por refs; renderer sin business logic. |
| KI-OD-22 | Cache acotado por digest/version; snapshots no se llaman cache. |
| KI-OD-23 | 50 MiB/source, 500 páginas PDF, 2 GiB workspace soft cap, 100k chunks. |
| KI-OD-24 | Imports = Operations con staging, cancel y recovery. |
| KI-OD-25 | Legacy RAG se reconstruye; no migración directa de vectores. |
| KI-OD-26 | Quality gates propios Core/Semantic/OCR con corpus congelado. |
| KI-OD-27 | Active Web queda fuera. |
| KI-OD-28 | READY principal: Windows 11 + NTFS local + HOST_UNISOLATED; portable tests no amplían claims. |

---

# Parte XXI — Plan de implementación

## 55. K0 — Baseline y contratos

- congelar HEAD y tags;
- reconciliar CI relevante;
- fijar fixtures/corpus iniciales;
- implementar Source/Revision/Locator/errors/capabilities;
- no anunciar capabilities todavía.

**Cierre:** Core/Security/Memory verdes y contratos versionados.

## 56. K1 — Store, lifecycle y authority

- KnowledgeStore V1;
- migrations/recovery;
- blobs/staging;
- scope SESSION/WORKSPACE;
- containment;
- delete/no-resurrection;
- legacy isolation.

**Cierre:** crash/cancel, cross-workspace y metadata traversal probados.

## 57. K2 — Attachments y host acquisition

- `attachmentRefs`;
- Desktop picker flow;
- CLI/JSONL import;
- SESSION sources;
- promote/import a WORKSPACE;
- progress/status/cancel.

**Cierre:** attachment no se convierte en user assertion y renderer no obtiene authority directa.

## 58. K3 — Extraction V1

Parsers obligatorios: TXT/MD/code, JSON, CSV, HTML, PDF textual y DOCX; MIME/sniff, encodings, locators y container bounds.

**Cierre:** no falso soporte PDF, locators correctos y errores tipados.

## 59. K4 — Retrieval documental

- structure-aware chunking;
- FTS5/exact;
- metadata filters;
- relevance floor/abstention;
- semantic spaces opcionales;
- hybrid deterministic fusion;
- legacy rebuild.

**Cierre:** Core lexical pasa calidad; semantic degrada seguro; no mixed spaces.

## 60. K5 — Context, provenance y citations

- KnowledgeCapsule;
- CitationRegistry;
- wrappers de evidencia;
- shared budget;
- citation validation;
- Memory coexistence.

**Cierre:** current user priority, citations válidas y authority separation.

## 61. K6 — Passive Web

- `WebSearchPort`;
- provider capability;
- remote opt-in;
- `web_search` en ToolRuntime;
- result provenance;
- URL snapshot import.

**Cierre:** sin browser/click/forms y PUBLIC_ONLY intacto.

## 62. K7 — Interfaces, subagents y hardening

- source list/status/detail DTOs;
- CLI/JSONL parity;
- integración Desktop mínima;
- delegated knowledge capsule;
- privacy/remote forwarding;
- quotas/observability;
- adversarial tests.

**Cierre:** no business logic renderer, no child global access y capacity states honestos.

## 63. K8 — Calidad y certificación

Ejecutar regressions Core/Security/Memory aplicables, contracts Knowledge, corpus de extraction, retrieval quality, abstention, citations, critical campaign, E2E local real, performance y Desktop contract regression.

No cambiar corpus, gold, thresholds, scorer o labels después de ver outcomes para fabricar PASS.

---

# Parte XXII — Gate final

## 64. Criterios `NOVA_KNOWLEDGE_INPUTS_V1_READY`

Deben demostrarse todos:

1. K0–K8 cerrados.
2. Core V1 continúa verde.
3. SECURITY V1.2 continúa verde en su alcance.
4. MEMORY V1 continúa verde y separado.
5. Source/Revision schema versionado/migrable.
6. Recovery de import/crash/cancel probado.
7. SESSION/WORKSPACE isolation probado.
8. Metadata/artifact containment probado.
9. Delete/no-resurrection documental probado.
10. TXT/MD/code/JSON/CSV/HTML/PDF textual/DOCX tienen camino productivo completo.
11. Unsupported/corrupt/partial se diferencian.
12. PDF usa parser real y conserva página.
13. DOCX aplica container bounds.
14. URL acquisition conserva SECURITY PUBLIC_ONLY.
15. `web_search` es pasivo y capability-gated.
16. Attachments no se convierten en user assertions.
17. Exact/FTS funciona sin embeddings.
18. Semantic documental es opcional y degrada seguro.
19. Embedding spaces documentales están versionados/no mezclados.
20. Legacy vectors no se reinterpretan.
21. Source deleted/superseded no aparece como current.
22. Retrieval tiene abstention honesta.
23. Knowledge+Memory respeta SharedRetrievalCap.
24. Current user no se sacrifica por Knowledge.
25. Document data no adquiere system/tool/security authority.
26. Knowledge no escribe MEMORY automáticamente.
27. Citations sólo aceptan IDs realmente admitidos.
28. Citation registry conserva source/revision/locator.
29. Subagent access documental está acotado.
30. Remote search y remote document forwarding son controles separados.
31. No auto-download de modelos semantic/OCR.
32. Capacity/retention limits activos.
33. Critical scope/delete/authority/citation invariants = 100%.
34. KNOWLEDGE_CORE_QUALITY supera thresholds congelados.
35. Un modelo local real apropiado completa E2E obligatorio.
36. Performance Core cumple thresholds publicados.
37. Regression final no oculta fallos con nuevos skips/xfails.
38. Limitaciones y capabilities no certificadas están documentadas.
39. Active Web permanece fuera.
40. Manifest reproducible con hashes/evidence publicado.

Si todo pasa:

```text
NOVA_KNOWLEDGE_INPUTS_V1_READY
KNOWLEDGE_CORE = READY
DOCUMENT_SEMANTIC_PROFILE = CERTIFIED | NOT_CERTIFIED
OCR_PROFILE = CERTIFIED | NOT_CERTIFIED
```

`DOCUMENT_SEMANTIC_PROFILE = NOT_CERTIFIED` y `OCR_PROFILE = NOT_CERTIFIED` **no bloquean** READY Core.

---

## 65. Qué significa READY

Dentro del alcance publicado significa que Nova puede:

- recibir attachments estructurados;
- importar fuentes persistentes por workspace;
- extraer los formatos V1 obligatorios;
- consultar fuentes sin depender de embeddings;
- usar semantic documental sólo cuando su profile lo permita;
- leer URLs públicas por el camino seguro existente;
- realizar búsqueda web pasiva si existe provider habilitado;
- incorporar evidencia al contexto con presupuesto;
- producir citations estructuralmente verificables;
- mantener Knowledge separado de Memory y authority;
- preservar lifecycle/version/delete documentales.

---

## 66. Qué NO significa READY

No significa:

- verdad garantizada de documentos o páginas;
- entailment perfecto de citas;
- resistencia universal a prompt injection;
- DLP universal;
- detección universal de secretos;
- soporte de todo PDF;
- OCR obligatorio;
- soporte universal de imágenes/Office/ODT/RTF;
- semantic retrieval universal;
- browser automation;
- sesiones autenticadas;
- Active Web;
- sandbox/process isolation;
- secure erase;
- borrado de backups externos;
- calidad idéntica en todo hardware/modelo/OS;
- certificación MEMORY Semantic;
- que un snapshot web siga siendo actual indefinidamente.

---

## 67. Claims de plataforma

El READY inicial se certificará para:

```text
Windows 11
local NTFS
HOST_UNISOLATED
```

Portable contract tests pueden ejecutarse en Linux/macOS/Windows, pero tests verdes no amplían automáticamente el claim de plataforma.

---

# Parte XXIII — Cierre normativo

## 68. Declaración de arquitectura

Knowledge Inputs V1 queda definida por cuatro fronteras:

```text
1. Source data is data, not authority.
2. Source revision/provenance is explicit.
3. Knowledge works without semantic embeddings.
4. Knowledge and Memory coexist but do not merge.
```

Secuencia objetivo:

```text
Source
→ Acquisition
→ Validation
→ SourceRevision
→ Extraction
→ Structured Document
→ Chunking
→ Index / Retrieval
→ KnowledgeCapsule
→ Citation Registry
→ ContextManager
→ Agent
```

Para web:

```text
web_search
→ result metadata
→ optional web_fetch
→ evidence
```

Nunca:

```text
web_search → browser automation
```

Una vez aprobado este documento:

```text
ARCHITECTURE_APPROVED
→ K0
→ K1
→ K2
→ K3
→ K4
→ K5
→ K6
→ K7
→ K8
→ NOVA_KNOWLEDGE_INPUTS_V1_READY
```

Hasta entonces:

```text
KNOWLEDGE_INPUTS_ARCHITECTURE = PROPOSED
KNOWLEDGE_INPUTS_IMPLEMENTATION = NOT_STARTED
```

---

## 69. Resumen ejecutivo de decisiones

```text
Knowledge Core:
  exact/FTS mandatory
  semantic optional

Scopes:
  SESSION
  WORKSPACE

Required formats:
  TXT/MD/code
  JSON/CSV
  HTML
  textual PDF
  DOCX

Web:
  public fetch
  passive search
  no browser automation

Memory:
  separate domain
  no automatic write

Citations:
  source/revision/locator registry
  structural validation
  no entailment overclaim

Legacy RAG:
  rebuild, do not reinterpret vectors

Security:
  reuse Core/Security
  no new sandbox claim

Initial READY profile:
  Windows 11 + local NTFS + HOST_UNISOLATED
```
