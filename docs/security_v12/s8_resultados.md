# SECURITY V1.2 — cierre exclusivo de S8

Estado: **S8 = PASS**. Gate S8: **SATISFECHO** en Windows 11/NTFS para las
superficies y pruebas anunciadas. **READY no se declara**, por instrucción del
usuario; `NOVA_SECURITY_V1_2_READY = false`. Fecha de contexto: 2026-10-04.
Sin avance de fase, commit, push, cambios de GPU, tuning ni descarga de modelos.

## Resultado y diagnóstico

Clasificación del fallo original: **MODEL_BEHAVIOR**, no PRODUCT_BUG.
El modelo produjo read(seed), write con placeholder y read(result) en la primera
respuesta, antes de recibir el primer ToolResult. La generación siguiente recibió
correctamente el resultado real. La repetición diagnóstica observó los mensajes
preparados que realmente se enviaron a Ollama, no sólo el transcript.

La inferencia única **no** es un requisito de Core V1 ni SECURITY V1.2; el test
anterior tampoco la exigía: pedía explícitamente esperar cada resultado. Su
restricción adicional era un único **Turn**. La copia es realizable con varias
Generations en ese Turn; no se presenta el fixture anterior como imposible.

Core §§6/7/15/17/18 y §27 criterio 5 exigen el ciclo modelo→tools→resultados→modelo,
Ollama local adecuado, ToolResults reales y E2E multi-tool; una sesión admite
varios Turns. SECURITY §29 exige todos los invariantes y límites honestos.
Revisión completa y evidencia de causa: [s8_normative_diagnostic.md](s8_evidence/s8_normative_diagnostic.md).

Se sustituyó sólo el criterio no normativo de un Turn por dos SubmitUserInput
normales en **la misma AgentSession/backend productivo**:

1. El modelo local solicita read real de seed.txt y termina sin escribir.
2. Sin suministrar el marcador en el nuevo prompt, solicita write con ese valor
   del ToolResult anterior y read real de result.txt.
3. Se observa el POST que genera write: debe ser posterior al read y contener
   exactamente su ToolResult. Se exige coincidencia literal de los argumentos,
   comparación **byte por byte** de archivos, resultado de verificación real
   recibido en otra inferencia y correlación de lifecycle/audit persistido.

El caso definitivo usó qwen2.5:7b instalado (7,6B, Q4_K_M), digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`,
localhost. Read se emitió en request 1; write en request 4 con el ToolResult
real en su input; request 5 recibió la verificación real. Hubo cinco Generations,
dos Turns y tres operaciones de tools completadas, cada una con terminal único,
`durable_terminal` y sin gap. El SHA-256 del archivo final coincide con el
afterHash observado por el broker:
`4f142a6a0781307007ab9b4fcd35b001133bb359c47689dac93ecab8463a2f60`.

Evidencia: [ollama_dependency_proof.json](s8_evidence/closure_final_e2e/ollama_dependency_proof.json),
[ollama_backend_closed.json](s8_evidence/closure_final_e2e/ollama_backend_closed.json)
y los POST/NDJSON observados. Se copiaron los bytes originales del segmento
JSONL productivo cerrado, no una reconstrucción de audit.
No inferencia scripted/cloud, ToolResults simulados ni ejecución directa de tools
en el E2E que califica. No se inyectó el valor mediante prompts o configuración.

## Symlinks host-real: evidencia manual aceptada

Corrida nueva: [after_symlink_permission/run.json](s8_evidence/after_symlink_permission/run.json),
UTC 2026-10-05T00:28:19 (2026-10-04 local). Sus **365 hashes** coincidían con el
snapshot previo a este cierre. Producto y tests nativos siguen idénticos; las
únicas diferencias actuales de esos inputs son tres archivos del harness S8.

Los casos directory_symlink (0,071 s) y file_symlink (0,085 s) son **PASS sin skip**.
El código cuya huella coincide ejecuta os.symlink y falla explícitamente ante
cualquier error de creación; sólo después instala la autoridad/broker productivo
y solicita read/write/edit/glob/grep. El fallback legacy falla si se usa. Ambos
casos llegaron al broker real, verificaron las denegaciones y que el sentinel
externo permaneciera intacto. No son PASS de fixtures inexistentes ni de mocks.

La corroboración es source hash + XML sin skip/failure + control de flujo del test.
Las fixtures temporales ya fueron limpiadas por el runner; no se afirma haber
inspeccionado enlaces que sigan existiendo hoy. La evidencia anterior con
WinError 1314 permanece intacta y sigue registrando fallo de creación antes del
broker; no se cambió su resultado ni se sustituyó por el PASS histórico de S3.

## Baseline, fronteras y preservación

Se leyeron íntegramente Core V1 y SECURITY V1.2. Branch main, HEAD
`158b60effa484cd34a58b991f3ee4ca3f808d924`, staging vacío. Se conservó el working
tree previo, incluidas las eliminaciones de README.easy-ja.md, README.ja.md y
hello.py. No se leyó, copió, migró ni reutilizó código SECURITY deprecated.

Antes de editar se repitieron **147 PASS** pertinentes a runtime, provider,
integración y harness: [closure_baseline/run.json](s8_evidence/closure_baseline/run.json).
Snapshot previo del cierre: 1.237 archivos en
`s8_evidence/closure_before_snapshot.json.gz.b64`; ninguno desapareció.
Los 376 pins anteriores coincidían antes de editar. Sus cambios autorizados
son el harness S8 y este informe; los raw logs/XML históricos no cambiaron.
Informe/manifest y fixtures anteriores se conservan en
[s8_evidence/pre_normative_review](s8_evidence/pre_normative_review/s8_resultados.md).

**Cero modificaciones de producto en este cierre**. Se conservan las fronteras
AgentRuntime→puertos Core, ToolRuntime común, Application coordinadora,
Infrastructure adapters/broker/launcher y backend Application CLI/Desktop.
No cambios de schemas, lifecycle productivo, políticas, opciones de modelo,
dependencias SECURITY o arquitectura. La modificación previa de S8 a los probes
Git (stdin DEVNULL/close_fds) permanece; no se amplió.

## Archivos de este cierre

| Archivo | Cambio |
|---|---|
| tests/security_v12/test_s8_e2e.py | E2E real dependiente entre inferencias en dos Turns; bytes exactos; Generations/operaciones/audit y raw segmentos. Espera terminal ligado al Turn solicitado. |
| tests/security_v12/s8_backend_entry.py | Observador opt-in de los inputs preparados y chunks reales, sólo en fixture privada. |
| tests/security_v12/run_s8.py | Incluye las nuevas pruebas unitarias del observador/validador en regresión. |
| tests/security_v12/s8_inference_observer.py | Nuevo observador pasivo y validador causal; nunca sustituye request/chunk/tool/model. |
| tests/security_v12/test_s8_dependency.py | Once unit tests: forwarding sin mutación, seis negativos, errores, endpoint no-chat y terminal stale del harness. |
| docs/security_v12/s8_resultados.md / s8_manifest.json | Estado, procedencia, revisión normativa, tests, criterios y hashes actualizados. |
| docs/security_v12/s8_evidence/s8_normative_diagnostic.md / verify_closure.py | Diagnóstico normativo y revisión reproducible del gate/preservación. |
| docs/security_v12/s8_evidence/closure_* / pre_normative_review | Evidencia nueva y copias de contenido anterior; no reemplazan raw históricos. |

## Tests y naturaleza de la evidencia

| Corrida | Naturaleza | Resultado |
|---|---|---|
| closure_baseline | Unit/mock/contract/integration pertinente antes de editar | 147 PASS |
| closure_observer_unit | Unit del observador y seis controles negativos; no E2E | 8 PASS iniciales |
| closure_diagnostic_original | Prompt original, backend/Ollama reales, observador pasivo | **1 FAIL**, 54,86 s; conserva el write incorrecto |
| closure_dependency_candidate | Modelo real/backend normal; nuevo criterio causal | 1 PASS, 90,47 s; candidato, no sustituye la final |
| closure_regression/s8_adversarial | Contratos/static + integración con doubles + once unit observer/harness | 61 PASS |
| closure_regression/security_regression | S1–S7 unit/contract/integration, disco real en fixtures | 554 PASS |
| closure_regression/core_regression | Core/mock/integration; RAG opcional non-fatal | 694 PASS + 10 subtests; 1 smoke opt-in skip; 3 GPU deselected |
| closure_regression/desktop_* | Node con doubles; tsc y build Vite reales | 28 PASS; tsc/build PASS |
| after_symlink_permission/s3_windows | Broker Windows/NTFS real, symlinks/junction/alias/TOCTOU | **25 PASS**, 0 skip, incluidos ambos symlinks |
| after_symlink_permission/s4_process | Procesos/launcher/canales/stdin/output/cancel reales | 29 PASS |
| after_symlink_permission/s5_network | HTTP/TLS/DNS/IPv4/IPv6 fixtures nativas con admisión/resolver de fixture | 28 PASS; no prueba firewall ni salida pública arbitraria |
| after_symlink_permission/s6_secrets | Environment root/child real, valores/actor de fixture | 4 PASS |
| after_symlink_permission/s8_host | Shell destructivo sobre hojas propias; approval actor fixture; frontera shell/S3 | 3 PASS |
| after_symlink_permission/core_native | Shell/cwd/Unicode/quoting/fallback Windows real | 4 PASS |
| closure_final_e2e | Cinco casos definitivos, procesos backend/CLI/Electron reales | **5 PASS**, 181,93 s |

Los cinco E2E finales son: multi-tool/Ollama real; spoof JSONL y denegación exacta
con inferencia scripted (caso distinto); CLI/Ollama real; Desktop lifecycle con
inferencia/embeddings scripted; Desktop/Ollama real y PATH realmente sin Git.
No se atribuyen inferencias reales a los casos scripted ni intervención humana UI
al actor de approval fixture. Los tres casos de Ollama no usan cloud ni scripted.
La corrida manual repite también 1.298 pruebas de regresión anteriores: no se
suman a las 1.309 actuales como pruebas únicas nuevas.

## Gate, regresiones, deuda y decisiones

**28/28 familias de invariantes PASS**, sin familia requerida sin ejecutar ni fallo
en las corridas definitivas. El review combina regresión actual, 93 host-real de
la corrida manual y los cinco E2E actuales; verifica hashes, no sólo conteos.
[closure_review.json](s8_evidence/closure_review.json) conserva el detalle por
familia. Los límites por superficie siguen publicados en
[s8_limits.md](s8_limits.md): HOST_UNISOLATED no es aislamiento OS; S3 sólo media
sus operaciones; red shell/provider no es web_fetch; límites operacionales no
son cuotas preventivas; cleanup tree sigue BEST_EFFORT.

Todos los criterios **de S8** están cumplidos. Ningún fallo previo fue renombrado
PASS: final_e2e anterior sigue 4 PASS/1 FAIL, final_native anterior sigue
91 PASS/2 fallos de fixture; diagnóstico original nuevo sigue FAIL.
La tarea original de un Turn continúa mostrando comportamiento insuficiente de
este modelo, no un bug probado de transporte. La nueva evidencia verifica una
dependencia real y fuerte permitida por Core; no garantiza alineamiento universal,
éxito en cualquier prompt ni comportamiento determinista del modelo.

Regresiones nuevas: ninguna en las suites definitivas ejecutadas. Deuda S8:
ningún criterio pendiente en Windows; Linux/macOS no certificados aquí.
No se implementan mejoras adyacentes para corregir batching/relatos del modelo.
OPEN DECISIONS S8: ninguna. SEC12-OD-01..05 conservan las decisiones humanas;
OD-06/07 permanecen fuera de este cierre, sin resolver.

Siguiente paso lógico: **esperar autorización del usuario antes de evaluar READY**.
No se declara READY ni se implementa otra fase.
