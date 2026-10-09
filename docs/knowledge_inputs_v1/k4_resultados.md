# K4 — Retrieval documental: preflight bloqueado

Estado: **K4 BLOCKED**.

Se auditó §59 y el baseline real antes de modificar producto. Se encontró un incumplimiento previo de la extracción PDF de K3 que afecta la validez de los documentos/locators de entrada a K4. No se implementó K4 ni se reparó K3 dentro de esta autorización. No se modificaron arquitectura, producto, tests, fixtures históricos, thresholds, skips ni xfails.

## Baseline

- Branch: `main`.
- HEAD: `717a24218dea7fb60d8b630896d653e39091bc7b`.
- Working tree: no limpio; cambios K0–K3 y MEMORY/CI anteriores preservados; sin staging.
- Windows 11 build 26200, NTFS local, `HOST_UNISOLATED`. Python 3.14.6, pytest 9.1.1.
- Arquitectura Knowledge SHA-256: `417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432`.
- Inventario inicial: 1745 archivos, congelados en `C:/Users/joseh/AppData/Local/Temp/nova-k4-preflight-20261007/preflight.json`.
- K3 permanece registrado históricamente como PASS; su informe/manifest/XML no se sobrescriben. La nueva caracterización evidencia un defecto no cubierto por aquella regresión, no un cambio en sus resultados históricos.

Tags (objeto annotated y commit destino), sin modificación:

- `nova-core-v1-stable 97f41c6dab89ee59332875bb8d89c29620b52156 158b60effa484cd34a58b991f3ee4ca3f808d924`
- `nova-memory-v1-ready fa6b2f7898692ddc6cec77a4d971dbc395b764a6 9911ad4ca0fc13edfef49e84441a759d35cbefda`
- `nova-memory-v1.1-ready 6a48c5252e40986ecf4180138d9d56bc519b3e49 3678d5b597a888b743e90d26efda6219943d58df`
- `nova-security-v1.2-ready e5bea6a4c2c559a1f5a2f8824316a83b548b2533 26dc87786d8ad1c1d879255a068c7fb50a25e6f2`

READY Security existente: PASS. READY MEMORY existente: NOVA_MEMORY_V1_READY, SEMANTIC_PROFILE=NOT_CERTIFIED. Los tests portables no amplían certificación de plataformas.

## Alcance normativo K4

§59 exige structure-aware chunking, exact/SQLite FTS5, filtros de metadata, relevance floor/abstención, spaces semánticos opcionales, fusión hybrid determinista y rebuild legacy.

Gate literal: **“Core lexical pasa calidad; semantic degrada seguro; no mixed spaces.”**

Requisitos relacionados: §§6/17–24/43/49/52/53/54. Calidad lexical: Recall@5 ≥90%, Precision@1 ≥85%, abstención ≥95%; no se modificaron ni evaluaron aún esos thresholds. Chunking: target ~700, hard ~1000 y overlap ~100 tokens, usando el estimador Core cuando corresponda; locators y límites preservados.

Decisiones aplicables: `KI-OD-01`, `KI-OD-02`, `KI-OD-03`, `KI-OD-08`, `KI-OD-09`, `KI-OD-10`, `KI-OD-11`, `KI-OD-12`, `KI-OD-16`, `KI-OD-19`, `KI-OD-23`, `KI-OD-24`, `KI-OD-25`, `KI-OD-26`, `KI-OD-27`, `KI-OD-28`.

K5 (KnowledgeCapsule, budget compartido, context admission, CitationRegistry) queda fuera. No existe autorización para transformar documentos en system/project instructions, grants, approvals o MEMORY.

## Inventario aplicable y reutilización

| Componente | Estado observado | Reutilización / gap K4 |
|---|---|---|
| core/knowledge.py, core/knowledge_store.py | Contratos V1 reales | Source/Revision/Document/Block/Chunk/Locator, scope y errores reutilizables; no contratos query/embedding space K4 |
| infrastructure/knowledge_sqlite.py, knowledge_migrations.py | Store y proyecciones reales K1 | Schema, FTS5, publicación transaccional, recovery/tombstones; una tabla FTS no equivale a retrieval terminado |
| infrastructure/knowledge_extraction.py | Integración K3 parcial respecto de su norma | Document blocks y proyección block-per-chunk; falta chunking K4. PDF usa heurística y falla locators |
| application/knowledge.py, bootstrap_knowledge.py | Pipeline compartido K1–K3 | Import, publish y promoción explícita; no servicio de consulta documental |
| core/context.py | TokenCounter/Core budgeting reales | Estimación numérica reutilizable sin modificar ContextManager |
| rag.py, infrastructure/rag.py, application/rag.py | Camino RAG legacy separado | Chunking fijo y vectores legacy sin identidad V1; no reinterpretarlos ni usar tablas MEMORY |
| tests/knowledge_inputs_v1 | 437 tests verdes | Cubren DTOs, store/recovery, scopes/containment, acquisition y cinco tests K3; falta cobertura que detecte los fallos PDF encontrados |

Archivos que serían previsibles **si se autoriza continuar**, no modificados/creados como producto ahora: contratos Core de retrieval/space, chunker e index/search adapters documentales, ampliaciones acotadas de `knowledge_sqlite.py`, `KnowledgeService` y composition root, y tests/corpus K4 prospectivos. No se fijan APIs nuevas ni se implementa K5.

Core mantiene Session/Turn/Operation y el único AgentLoop; Application coordina; SECURITY sigue controlando tools/FS/red/audit. MEMORY y Knowledge conservan stores, scopes y policies independientes. El bloqueo no justifica saltar esas fronteras.

## Bloqueo demostrado — K4-PREFLIGHT-01

No hay ambigüedad en la arquitectura: §12 indica **“Un archivo .pdf leído como texto heurístico no cuenta como soporte PDF”**; §15 exige **“Debe usar parser PDF real y conservar número de página”**; §58 exige **“no falso soporte PDF, locators correctos y errores tipados”**. KI-INV-014/015 y los locators requeridos por KI-INV-016 no permiten considerar esa heurística un productor documental terminado.

Observación directa:
`local_cli/infrastructure/knowledge_extraction.py:141–161` busca strings mediante regex, cuenta `/Type /Page` (también coincide con `/Pages`) y asigna número de página por ordinal del string. El test existente `test_pdf_text_and_docx_extract_without_external_parser_or_network` usa bytes sin un PDF completo y sólo exige un locator tipado, no un parser real ni el mapeo correcto.

Prueba controlada, runtime nativo, producto real, sin doubles:

| Caso sintético | Resultado normativo esperado | Resultado real | Clasificación |
|---|---|---|---|
| Header %PDF seguido de texto sin object graph/xref | error tipado; nunca READY | READY y locator PDF_PAGE=1 | HISTORICAL/PREEXISTING — defecto de producto K3 |
| PDF completo de dos páginas, dos strings en página 1 y uno en página 2 | pages [1,1,2] | pages [1,2,3]; inventa página 3 | HISTORICAL/PREEXISTING — defecto de producto K3 |

Denominador: **0/2 contratos cumplidos; 2/2 incumplidos**, exit code 1. Son caracterizaciones de validez, no benchmark de calidad K4 ni resultados de un LLM. No se transformaron en skip/xfail. Fixtures sintetizados en memoria, sin documentos del usuario ni secretos.

No es un defecto introducido por K4: ningún archivo producto/test se modificó. Tampoco es una contradicción entre arquitecturas: la implementación previa no satisface el contrato. Sustituir el parser y ampliar sus pruebas es una reparación K3 que requiere autorización de alcance separada, no un refactor mínimo de retrieval.

## Tests/evidencia

1. Baseline Knowledge K0–K3 nativo: **437 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, exit 0, 23.07 s.
2. Caracterización PDF independiente: **0 PASS / 2 FAIL**, exit 1, conserva resultados.
3. HEAD anterior verificado/reutilizado: **4583 PASS / 0 FAIL / 0 ERROR / 11 skips históricos / 53 subtests PASS**. XML SHA comprobado: `6a77d15c2d88405d983ac214ffe8b3479e31c3d030daee3f19aef54693b9c2fa`. Este verde no demuestra el contrato PDF adicional.
4. No suite/quality K4 ni HEAD post-implementación: **NOT_RUN**, porque se detuvo durante preflight sin implementación.
5. No inferencia/embeddings/provider/red/cloud/OCR/E2E nuevo.

Comandos:

```powershell
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m tests.knowledge_inputs_v1.run_k0 --mode contracts --output 'C:/Users/joseh/AppData/Local/Temp/nova-k4-baseline-knowledge-20261007' --extra-test-site 'C:/Users/joseh/AppData/Local/Temp/nova-memory-ci-0b333e9f1a8a48e8833849d343b756a8/python314-test-deps'
& 'C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B 'C:/Users/joseh/AppData/Local/Temp/nova-k4-preflight-20261007/pdf_probe.py'
```

Outputs, XML, runtime/profile/basetemp y el harness sintético están fuera de Git. Plugin autoload/cacheprovider/bytecode deshabilitados para baseline.

| Artefacto | SHA-256 |
|---|---|
| `C:\Users\joseh\AppData\Local\Temp\nova-k4-baseline-knowledge-20261007\run.json` | `c59b65fad249d5b3667157bad8608a322cca8cacb39597426d2a71d29f370142` |
| `C:\Users\joseh\AppData\Local\Temp\nova-k4-baseline-knowledge-20261007\run.log` | `a13e253a73c2ac368393a2bc665b4cba0ca41c7cc0b702bde440e7a84414aa70` |
| `C:\Users\joseh\AppData\Local\Temp\nova-k4-baseline-knowledge-20261007\tests.xml` | `a141452043f0954d7212d80d4d761e488e1fcbf68f814d116595c81a76305073` |
| `C:/Users/joseh/AppData/Local/Temp/nova-k4-preflight-20261007/preflight.json` | `f00b3d8f24f48cb0f4452b40dfd409826c1c6278a093219653382afce19b9270` |
| `C:/Users/joseh/AppData/Local/Temp/nova-k4-preflight-20261007/pdf_probe.py` | `584fb1e56ac24e99158b533bd6a47ffb2cd70a7699b082b2ec670a107d612d62` |
| `C:/Users/joseh/AppData/Local/Temp/nova-k4-preflight-20261007/pdf_probe_result.json` | `4699780c555e75282c57e7aae36e1a198ddc7ccceadbcbcb9286b15e844d7f7a` |

La primera ejecución sandbox del probe añadió un warning del intérprete antes del JSON; el framing del lector falló. Se repitió únicamente en runtime nativo, sin cambiar fixture ni assertions, y reprodujo los mismos dos defectos. Es un incidente ENVIRONMENT/HARNESS de salida, separado del defecto de producto.

## Criterios K4 uno por uno

| Criterio | Estado |
|---|---|
| structure-aware chunking y locators | BLOCKED; dependencia de extracción no conforme |
| exact/FTS5 y filtros | NOT_IMPLEMENTED / NOT_EVALUATED |
| calidad Core lexical y abstención | NOT_EVALUATED |
| semantic opcional con degradación segura/no mixed spaces | NOT_IMPLEMENTED / NOT_EVALUATED |
| fusión hybrid determinista | NOT_IMPLEMENTED / NOT_EVALUATED |
| legacy rebuild sin reinterpretar vectores | NOT_IMPLEMENTED / NOT_EVALUATED |

Las tablas existentes y suites anteriores no se presentan como implementación K4. No se certifica calidad semántica, OCR, Linux/macOS ni aislamiento de procesos.

## Decisión humana requerida

**OPEN DECISION operativa, no cambio normativo:** autorizar una reparación acotada de K3 (parser PDF real, mapeo de páginas y pruebas de rechazo/corrupción) antes de reanudar K4.

Recomendación: reparar y revalidar K3 manteniendo intacta la arquitectura y la evidencia histórica; después retomar K4. No se propone omitir PDF, reducir gates ni aceptar locators inventados.

## Archivos y preservación

Creado únicamente en el repositorio:
- `docs/knowledge_inputs_v1/k4_resultados.md`.
- `docs/knowledge_inputs_v1/k4_manifest.json`.

Producto, tests, arquitecturas, evidencia K0–K3, MEMORY/Security, tags y staging conservados. Sin commit, push ni tag. Sin K5.

Resultado: **K4 BLOCKED**. Detener para revisión humana.
