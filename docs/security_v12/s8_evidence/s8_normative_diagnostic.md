# S8 — revisión normativa y diagnóstico del E2E local

Fecha de contexto: 2026-10-04. Clasificación del fallo original: **MODEL_BEHAVIOR**.
Esta clasificación no convierte las corridas fallidas en PASS ni declara READY.

## Qué exigen los documentos

Se leyeron completos Core V1 (621 líneas) y SECURITY V1.2 (1.971 líneas).
No se consultó ni reutilizó código SECURITY deprecated.

- Core §6, línea 129: ciclo modelo → tool calls → resultados → modelo.
- Core §7, líneas 180–185: un Turn admite varias Generations y una sesión muchos
  Turns. Turn, Generation y Operation son entidades distintas.
- Core §15, línea 335: conversación/tool calling normal con Ollama local adecuado
  7B–9B, sin depender de Claude/cloud.
- Core §17, líneas 384–405: contexto preparado, continuidad de roles/tool IDs;
  working context no equivale al transcript canónico.
- Core §18, línea 421: ToolRuntime común; ToolResult estructurado y adaptación
  al texto legacy que recibe el modelo.
- Core §27, línea 576, criterio 5: E2E multi-tool Ollama local sin cloud frontier.
- SECURITY §1, línea 27: prevalece Core para lifecycle/contratos.
- SECURITY §§15/23/24: ruta común, outcome observado/terminal único y auditoría.
- SECURITY §29, líneas 1542–1566: gate S8 incluye Ollama/CLI/Desktop/regresión,
  invariantes anunciados y publicación honesta de límites HOST_UNISOLATED.

Ninguno exige copia literal read→write→read en **una sola respuesta/inferencia**,
ni fija este problema de copia o el número de Turns como criterio universal.
El test anterior tampoco imponía una inferencia: su prompt pedía explícitamente
esperar cada resultado y no agrupar llamadas dependientes. Exigía **un Turn**,
orden de efectos y copia literal; no comprobaba separación entre Generations.
La tarea era realizable con varias inferencias dentro de ese Turn. No era una
expectativa lógicamente imposible: el modelo incumplió su instrucción.

## Evidencia de la causa

Evidencia anterior intacta: `final_e2e/ollama_backend_attempt.json` y su XML/log.
Primera respuesta: read(seed), write("read(result.txt)"), read(result) agrupados.
El read real devolvió el marcador aleatorio correcto. La generación posterior
incluso lo citó, pero aseguró incorrectamente que el archivo contenía ese valor.
El archivo conservó el placeholder; la corrida sigue siendo FAIL.

Repetición diagnóstica con el mismo prompt y modelo local real:
`closure_diagnostic_original/selected.xml`: **1 FAIL**, 54,86 s.
Observación pasiva en el último límite de mensajes preparados antes del POST:

- `ollama_request_15932_0001.json`: input sin ToolResults; respuesta contiene
  read(seed), write(content="seed.txt\n1\n2\n3"), read(result). Todos los argumentos
  del write se generaron antes de ejecutar el primer read.
- `ollama_request_15932_0002.json`: input real enviado a `/api/chat` incluye el
  ToolResult del read con `NOVA_S8_111229ae154648e88e531e6b11f70d27`, el resultado
  del write y el read del archivo incorrecto. No se sustituyeron mensajes/chunks.
- Eventos: primera GenerationCompleted secuencia 6; ToolCompleted read/write/read
  secuencias 10/15/20; siguiente GenerationStarted secuencia 22. Ambos modelos
  runtime snapshots son Ollama qwen2.5:7b, digest 845dbda0…b697e, localhost.

La lectura llegó correctamente a una generación posterior. AgentLoop ejecutó
secuencialmente los argumentos ya emitidos; no existe una promesa de evaluar
expresiones como contenido de write o regenerar argumentos dentro de un batch.
BoundModelRuntime prepara/redacta contexto y OllamaClient lo entrega al provider;
el observador confirma esa ruta, no sólo el transcript. No se encontró un defecto
de pérdida/reordenamiento de ToolResults en AgentLoop/provider/harness.

**Diagnóstico principal: MODEL_BEHAVIOR**, batch dependiente prematuro y relato
final incorrecto. La restricción de un Turn era un criterio adicional del fixture,
no un MUST de las arquitecturas; no se denomina PRODUCT_BUG. Tampoco se atribuye
al test un requisito de inferencia única que no tenía.

## Sustitución acotada del criterio de fixture

Se conserva el nombre del E2E y se utiliza la misma sesión/backend productivo:

1. SubmitUserInput normal: modelo local solicita read real de seed.txt y termina
   sin escribir. El marcador aleatorio sólo existe en la fixture.
2. SubmitUserInput normal, sin suministrar el marcador: modelo usa el ToolResult
   anterior para write(result.txt) y pide read real del resultado.
3. Se exige que el POST que produce write sea posterior al read y contenga
   exactamente su ToolResult real; el contenido emitido debe coincidir con el
   marcador. La verificación real debe llegar a otra inferencia posterior.
4. Se comparan bytes de ambos archivos, no una afirmación verbal. Se correlacionan
   requests/Generations, ToolResults, operaciones y terminales/audit persistido,
   incluido afterHash del broker. Una operación fallida o gap hace fallar el caso.

Sólo se sustituye el requisito no normativo de un Turn. Se refuerza la prueba
causal entre inferencias y la igualdad final (antes strip, ahora bytes exactos).
No se inyecta el valor al prompt, no se scriptan inferencias, no se invoca una
tool/broker directamente, no se alteran tools habilitadas, schemas, políticas,
opciones del modelo, límites del harness ni código productivo.

La observación es test-only, opt-in y registra únicamente fixtures privadas.
Sus ocho pruebas unitarias iniciales incluyen seis controles negativos (batch en una
inferencia, resultado ausente, placeholder, scripted, valor en prompt, request
fallida). La regresión final añade tres casos (error original, endpoint no-chat,
terminal stale del harness), para once en total. No califican como el E2E real
ni sustituyen su ejecución. El caso candidato pasó en 90,47 s; la corrida final
con los cinco E2E pasó en 181,93 s, conservando comparación de bytes y audit real.
