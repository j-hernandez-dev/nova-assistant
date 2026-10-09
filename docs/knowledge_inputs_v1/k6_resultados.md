# K6 — Passive Web

## Resultado

**K6 PASS** — gate §61 de `NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md`.

Perfil ejecutado: **Windows 11 + NTFS local + HOST_UNISOLATED**. No sandbox/process isolation. `DOCUMENT_SEMANTIC_PROFILE = NOT_CERTIFIED` y MEMORY `SEMANTIC_PROFILE = NOT_CERTIFIED` permanecen intactos. No K7 ni READY.

## Preflight y alcance normativo

- Branch `main`; HEAD/base `717a24218dea7fb60d8b630896d653e39091bc7b`.
- Working tree inicial: **161 entradas dirty/untracked**, **1784 archivos versionables**. Se preservan los cambios preexistentes K0–K5; estado inicial completo y tags en manifest.
- CPython **3.14.6 AMD64**, pytest 9.1.1; Windows 11 build 26200; volumen C: NTFS Fixed local.
- Baseline antes de editar: **573 Knowledge PASS** y **182 Core/context/S5 PASS**.
- Arquitectura Knowledge SHA-256: `417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432`.
- Pins K5 verificados al iniciar. Arquitecturas, evidencia K0–K5, K3 PDF repair, K4 BLOCKED/resume, corpus/gold y tags anteriores no se reescriben.
- Precedencia §3: Core conserva Session/Turn/Generation/Operation/context; SECURITY conserva Policy/Approval/grants/S5/audit; MEMORY conserva su dominio; Knowledge sólo añade evidencia externa.

K6 exige WebSearchPort, provider capability, remote opt-in, web_search en ToolRuntime, provenance de resultados e import URL snapshot. Cierre literal: sin browser/click/forms y PUBLIC_ONLY intacto. Aplican §§6–11,14–15,19–20,30–31,34,36–40,42,45–46,53/54/61. La certificación con buscador/LLM reales corresponde a la campaña K8 cuando esté habilitada, no a este gate contractual.

### Inventario antes de editar

| Pieza | Estado inicial | Reutilización / gap K6 |
|---|---|---|
| web_fetch/S5 | Productivo | Policy/grant exacto, DNS/pinning/redirects/TLS, límites y audit intactos. Su resultado público es texto limitado, no bytes para extracción. |
| Source/Revision/store K1 | Productivo | Scopes, staging/publicación atómica, tombstone, recovery y proyecciones. |
| Host controls K2 | Productivo | Actor verificado, idempotencia/revisión, Operations, progress/cancel, CLI/JSONL y backend Desktop común. Faltaba URL intent. |
| Parsers K3 / PDF repair | Productivo | pypdf 6.19.0 y parsers text/JSON/CSV/HTML. K6 reutiliza parsers sobre bytes remotos normalizados; no reabre PDF. |
| Retrieval K4 | Productivo | Exact/FTS, scopes/revision/state, chunking y locators. Sin cambios de scoring/thresholds/semantic. |
| K5 / MEMORY | Productivo | SharedRetrievalCap, cápsula/citas por Turn, remote forwarding off y no auto-MEMORY. |
| WebSearchPort/provider/tool | Ausente | Implementados en K6, no confundidos con RAG legacy o model_search (gestor de modelos). |
| Legacy RAG / knowledge notes | Independiente | No se migran ni se usan como transporte web. Vectores legacy intactos. |
| Active Web | Fuera de alcance | No browser sessions/DOM/clicks/forms/JavaScript/navigation loops. |

Archivos previstos y finalmente intervenidos: contratos Core pasivos/response privado; Application search/URL import/host controls; seams mínimos Policy/ToolRuntime/audit/network; adapters Infrastructure; config/composition CLI/server; tests/harness K6. Sin CI/dependencias/arquitectura nueva.

## Implementación y trazabilidad

| Requisito | Componente | Evidencia |
|---|---|---|
| §30 puerto pasivo | core/passive_web.py | SearchOptions/Result/Response schema 1; provider identity, query fingerprint SHA-256, timestamp, title/URL/snippet/rank; SEARCH_RESULT locator. |
| §31 capability/opt-in | infrastructure/web_search.py, bootstrap_passive_web.py, config.py, knowledge_host.py | DISABLED por default; UNAVAILABLE sin endpoint válido; AVAILABLE configura un adapter invocable, no una garantía de uptime; DEGRADED tras fallo. Opt-in exige boolean True. |
| §9.2 tool mediada | tools/web_search_tool.py, application/passive_web.py, policy.py, tool_runtime.py | Query/max_results solamente; URL del provider fijada por host, vinculada al grant; un claim y una cadena HTTP, no replay/retry ni override de endpoint. |
| §31 provenance | SearchResponse/ToolResult | SEARCH_PROVIDER_SNIPPET, WEB_SEARCH_SNIPPET, fetchedPage=false, rank/URL/fingerprint/timestamp. Nunca se presenta como página adquirida. |
| §11 URL snapshot | application/knowledge_web.py, knowledge.py/knowledge_host.py, infrastructure/knowledge_web_extraction.py | Host Operation → S5 → bytes privados → K3/K4 → K1 atomic publish. Source UUID / Revision UUID, requested/effective URL, acquiredAt, digest/MIME/contentType, ETag/Last-Modified seguros, profile y locators WEB_BLOCK reales. |
| §40 refresh explícito | source_refresh_url | Unchanged si contenido y representación coinciden; cambio → nueva revisión; fallo conserva la anterior; delete no reactiva una fuente. No watcher/polling/TTL fetch. |
| §§25–29/34/38 | K4/K5 existentes + integración | Source snapshot alimenta el mismo retrieval/cap/citation registry; no nuevas reservas. Search habilitado no autoriza enviar documentos a provider remoto. No write MEMORY. |

El adapter inicial **SearXNG JSON** usa GET y `q`/`format=json` según la [Search API oficial](https://docs.searxng.org/dev/search_api.html). No fija una instancia ni proveedor comercial exclusivo. No instala SearXNG ni dependencias. Su endpoint y el opt-in pertenecen a configuración confiable del host. No se admiten credenciales en URL ni se ofrece autenticación en este adapter; no hay credenciales de búsqueda que puedan llegar al modelo. No se contactó ninguna instancia pública durante esta tarea.

### Extensión privada mínima de S5 (necesaria para K6)

El contrato público/nombre/schema de `web_fetch` permanece intacto. La nueva seam `ToolRuntime.fetch_snapshot` entrega `FetchedSnapshot` exclusivamente al host/pipeline de extracción:

- después de la misma Policy/Grant/claim/cadena DNS/HTTP/TLS/redirect y validación;
- sin segundo request, fallback urllib, proxy, netrc/cookies o credenciales heredadas;
- body máximo **2 MiB**, timeout HTTP **30 s**, máximo **5 redirects**, texto publicado máximo **50.000** chars;
- sólo ETag/Last-Modified acotados como headers privados; no Set-Cookie/Authorization;
- bytes nunca se agregan a ToolResult metadata, transcript, eventos o Security Audit; no se cachean/reentregan por replay;
- los grants siguen usando el permiso network.fetch existente, no un nuevo authority model. Web search añade un tool invocable, no un bypass.

Los raw snapshots son bytes adquiridos acotados. El digest es del body retenido, no una promesa de hash del contenido remoto completo si hubo truncamiento. Una respuesta truncada extraíble es **PARTIAL** y conserva warning; una parse failure conserva error tipado, no READY vacío. S5 sigue restringiendo MIME remoto a textual: no se amplía el soporte remoto a PDF/DOCX binarios.

Remote decode: BOM → charset HTTP válido → UTF-8 estricto. No replacement silencioso. HTML se parsea sin script/style payload ni ejecución; JSON/CSV conservan su parser y locator original descriptivo como metadata, con locator público WEB_BLOCK hacia la URL efectiva. Cada actualización utiliza K4 chunking/profile y proyección FTS, sin reinterpretar vectores.

Los snippets son datos efímeros de la operación/ToolResult; no se importan/indexan automáticamente como Source ni MEMORY. El transcript canónico puede conservar su ToolResult por el contrato Core: «efímero» no promete borrar historia/audit.

### Backend y schemas

- Config aditiva: `web_search_enabled=false`, `web_search_endpoint=""`. No config global modificada ni variables de credenciales añadidas.
- Nuevo tool `web_search(query, max_results?)`; defaults operacionales: query ≤1024 chars, ≤10 resultados, título ≤512, snippet ≤4000, respuesta publicada ≤50k. Bounds registrados en protocol_v1, no quotas OS.
- Host commands schema 1 aditivos: `source_import_url(url, scope?)` y `source_refresh_url(url, sourceId)`. Actor, revision/idempotency/cancel y workspace host-bound existentes. URL nunca se reabre automáticamente desde metadata persistida.
- `source_refresh_url` es para sources URL_SNAPSHOT explícitos. Promotion K2 sigue siendo copia independiente; no se añade UX especial ni remote refresh de fuentes locales/legacy.
- CLI y server/Desktop componen el mismo tool/service Application. API host validada probada por CLI y JSONL; UX/list/detail/subagent work adicional queda en K7.
- Origin fingerprint URL JSON schema 1, Source/Revision/store schema existente; sin migración SQLite, nuevas tablas ni nuevos tool schemas para tools anteriores.

## Gate K6 — criterio por criterio

1. **WebSearchPort (§30/61) — PASS**. Core SearchOptions/Result/Response versionados; provider id, query SHA-256, timestamp, URL/title/snippet/rank; callback S5 bound/one-shot.

2. **Provider capability (§31/45/61) — PASS**. DISABLED/UNAVAILABLE/AVAILABLE/DEGRADED; adapter/config normal, snapshot de Application, errores observables.

3. **Remote opt-in (§31/38/61) — PASS**. Host boolean explícito + endpoint; default false/empty, no DNS/grant/dispatch en disabled; no credential support, no implicit instances.

4. **web_search en ToolRuntime (§9.2/61) — PASS**. Schema exclusivo query/max_results, policy/intent network.fetch exacto, claim único, S5 checked chain y Security Audit; dos Generations/ToolResult real.

5. **Result provenance (§6.6/7/30/31/61) — PASS**. SEARCH_PROVIDER_SNIPPET/WEB_SEARCH_SNIPPET, timestamp/fingerprint/rank, fetchedPage=false; no page autofetch, persist/index/write MEMORY.

6. **URL snapshot import (§11/19/20/40/61) — PASS**. Host Operation → ToolRuntime/S5 raw snapshot private → remote decode/K3 parser/K4 chunk/FTS atomic K1; Source/Revision/digest/MIME/URLs/headers/locators; explicit unchanged/new refresh, failed refresh preserves old.

7. **PUBLIC_ONLY intacto (cierre §61) — PASS**. 93 S5 contracts + 29 native private HTTP/TLS; denied private/mixed DNS/redirect downgrade; 30s/2MiB/5redirects/50kchars no ambient creds/proxy, TLS verified.

8. **Sin browser/click/forms (cierre §61) — PASS**. SearXNG GET JSON only; parsing bytes/HTML passive, no DOM execution/clicks/forms/cookies/sessions or Active Web adapter.

9. **Core/Security/Memory compatibles; scope/authority/context — PASS**. K6 61; Knowledge 634; MEMORY 790; PDF 26; Core/context 131; HEAD 4780 PASS + 53 subtests PASS, 0 FAIL/ERROR, same 11 historical skips. No architecture/dependency/CI change.

KI-OD aplicables: 14/15/16/17/18/21/22/24/27/28. KI-INV demostrados/reutilizados: 001–007, 010–017, 020–021, 024–029, 031–035, 037–039. Source/Revision, Memory y authority separation permanecen; strong S5 claims sólo sobre el cliente mediado, nunca sobre red de procesos HOST_UNISOLATED.

## Tests y regresión final

| Gate | Resultado | Clasificación |
|---|---|---|
| Baseline Knowledge | 573 PASS | Unit/contract/integration sintético |
| Baseline Core/context/S5 | 182 PASS | Contract/mock |
| K6 congelado | **61 PASS** | 38 contratos de tools con HTTP double; 22 integración Source/Application/lifecycle; 1 socket nativo privado |
| Knowledge K0–K6 | **634 PASS** | Real store/parsers/backend, doubles identificados |
| PDF repair K3 | **26 PASS** | Parser PDF real, PDFs sintéticos |
| MEMORY | **790 PASS** | Regresión contractual, sin embeddings/Ollama reales |
| Core/context/RAG/64K | **131 PASS** | Fronteras/budgeting |
| S5 contracts/runtime | **93 PASS** | Policy/grants/network mediation, HTTP double |
| S5/K6 host-network | **29 PASS** | 28 S5 + 1 K6, HTTP/TLS IPv4/IPv6 privados |
| HEAD Windows nativo | **4780 PASS**, **53 subtests PASS**, **11 SKIP históricos** | **0 FAIL, 0 ERROR**, exit code 0 |

Los conteos de gates se solapan y no se suman como casos únicos. Denominador HEAD: **4791 top-level testcases** = 4780 PASS + 11 SKIP; header XML **4844 outcomes** contando 53 subtests. No nuevos skips/xfails/exclusiones. Los 11 skips y 12 ignores coinciden exactamente con K5 y están listados en manifest.

Todos los comandos exactos, versiones, timestamps, exit codes y hashes de XML/log/run.json (incluidas corridas fallidas) se registran en manifest. Runners privados deshabilitan plugin autoload/cacheprovider y mantienen HOME/APPDATA/TEMP/basetemp/runtime fuera del workspace Git. Outputs: `C:/Users/joseh/AppData/Local/Temp/nova-k6-20261008`.

### HEAD completo verificable

- Inicio registrado UTC: `2026-10-08 07:51:49 UTC`.
- Inicio JUnit: `2026-10-08T01:51:54.216137-06:00`.
- Fin runner UTC: `2026-10-08T07:58:01.1751459Z`.
- Tiempo pytest: **365.71 s** (JUnit 365.639 s).
- XML: `C:/Users/joseh/AppData/Local/Temp/nova-k6-20261008/head-final/tests.xml`.
- SHA-256: `8747e73e29dee5d10630a58a9f38c96c9f8d0bde50ace5ce7f3b80f76a8f5e0e`.
- Exit code **0**. Comando completo: manifest → `head.run.command`.

### Native/host-real: alcance exacto

Las 28 pruebas S5 ejecutan sockets HTTP/TLS reales con fixtures privados, incluyendo límites 2MiB/50k, redirects, cancel/trickle/timeouts, TLS hostname, resolver ocupado y red provider separada. K6 agrega lectura de headers segura y extracción/publicación desde respuesta del broker real.

Para positivos locales se sustituyen DNS/admission **sólo en el fixture**, como en S5. Antes de ese positivo, el mismo cliente productivo deniega loopback sin conectar. No se presenta el positivo privado como demostración de acceso PUBLIC_ONLY a Internet ni como calidad de un buscador real. No modificaciones a política productiva ni excepciones por plataforma en assertions.

### Fallos iniciales conservados

- `block2`: 45 PASS / 2 FAIL. **HARNESS_BUG**: atributo MEMORY equivocado; query por clave JSON que no era contenido de la proyección K3. Se usa la API store.list y se compara la misma consulta de valor antes/después del refresh. Sin cambiar record/question/gold de un quality corpus.
- `block2-corrected`: 46 PASS / 1 FAIL. **HARNESS_BUG**: store.list_active no existe; corregido al contrato store.list real.
- `block3`: 54 PASS / 2 FAIL. **HARNESS_BUG**: fixture heredado reutilizaba operationId para requests distintos; fixture audit dentro de workspace violaba S7 y fue denegado correctamente. Se asignan nuevos IDs y audit sibling privado fuera del workspace.
- `block3-corrected`: 55 PASS / 1 FAIL; `block4`: 58 PASS / 1 FAIL. **HARNESS_BUG**: trataba el header/envelope JSONL de storage como record. Se valida mediante read_operation real, incluyendo request/policy/grant/dispatch/network/terminal. No assertions ni audit productivo debilitados.
- Inspección incremental detectó una inserción inicial K6 en la función CLI resources sin variable tools (**PRODUCT_BUG introducido durante desarrollo**, corregido antes del freeze y verificado en roots normales/HEAD). No se ocultó un fallo de baseline.
- Revisión del camino de refresh identificó el callback de host ligado a la primera Operation; ahora se vincula al host command actual, manteniendo la correlación Core. Es la mínima dependencia compartida necesaria para nuevas operaciones URL/refresh, sin refactor general.
- El intento inicial de leer runtime/CIM bajo sandbox falló por permisos (**ENVIRONMENT**, no fallo de tests/producto). El runtime lo prueban run.json nativos; C: NTFS Fixed se confirmó con consulta read-only autorizada.

No PRODUCT_BUG de regresión pendiente demostrado. Evidencia anterior no se borra ni se sustituye por verde.

## Performance y límites de claims

K6 no fija SLA rígido de import/HTTP ni nuevo benchmark retrieval. Se respetan los bounds S5 y los bounds K1/K3/K4. La evidencia K4 de FTS **p95 2.2483 ms ≤100 ms** (1000 chunks/60 queries) se conserva con hash verificado; no cambió FTS/ranking/corpus y no se reinterpreta como nueva medición K6.

Las duraciones de suites no son latencia de un buscador ni un SLA de inferencia. No se evaluó uptime/quality/latency de una instancia SearXNG pública ni un LLM real; K8 permanece separada.

## Archivos de esta fase

Modificados **respecto del working tree inicial**, no respecto del HEAD Git antiguo:

- `local_cli/application/tool_runtime.py`
- `local_cli/application/security_audit.py`
- `local_cli/application/network.py`
- `local_cli/bootstrap_cli.py`
- `local_cli/core/network.py`
- `local_cli/config.py`
- `local_cli/bootstrap_knowledge.py`
- `local_cli/application/knowledge_host.py`
- `local_cli/application/knowledge.py`
- `local_cli/infrastructure/http_fetch.py`
- `local_cli/bootstrap_server.py`
- `local_cli/application/policy.py`

Creados (producto/tests):

- `local_cli/application/knowledge_web.py`
- `local_cli/core/passive_web.py`
- `local_cli/application/passive_web.py`
- `tests/knowledge_inputs_v1/test_k6_passive_web.py`
- `local_cli/infrastructure/web_search.py`
- `local_cli/infrastructure/knowledge_web_extraction.py`
- `tests/knowledge_inputs_v1/run_k6_host.py`
- `tests/knowledge_inputs_v1/run_k6.py`
- `local_cli/bootstrap_passive_web.py`
- `local_cli/tools/web_search_tool.py`

Evidencia nueva:

- `docs/knowledge_inputs_v1/k6_evidence/implementation_freeze.json`
- `docs/knowledge_inputs_v1/k6_evidence/protocol_v1.json`
- `docs/knowledge_inputs_v1/k6_resultados.md`
- `docs/knowledge_inputs_v1/k6_manifest.json`

## Limitaciones / deuda / OPEN DECISIONS

- No Active Web ni browser sessions/cookies/forms/clicks/JavaScript ejecutado.
- Búsqueda apagada por default; necesita host endpoint con JSON habilitado. AVAILABLE significa integración configurada invocable, no un endpoint probado/garantizado.
- Adapter inicial sin auth; no proveedor comercial obligatorio ni instancia por default. No nuevos modelos/downloads/cloud/hardware changes.
- No inferencia real ni certificación de search quality aquí. Document Semantic y Memory Semantic permanecen NOT_CERTIFIED.
- MIME remoto limitado por S5 a textual; PDF/DOCX locales siguen reales e intactos.
- Snapshots pueden quedar stale; refresh explícito. No remote persistent cache ilimitado ni auto-fetch de resultados.
- Citations validan referencias estructurales, no verdad/entailment; datos externos nunca adquieren autoridad.
- No DLP/cifrado universal/sandbox/OS quotas/secure erase.
- K7 pendiente: UX mínima, source detail, delegación a subagentes y hardening adicional. No se implementa ahora.
- **OPEN DECISIONS bloqueantes: ninguna.** El adapter concreto es elección reemplazable de Composition Root bajo KI-OD-15, no cambio de la arquitectura.

**Se detiene en K6 PASS para revisión humana.** Sin commit, push, tag, K7 o declaración READY.
