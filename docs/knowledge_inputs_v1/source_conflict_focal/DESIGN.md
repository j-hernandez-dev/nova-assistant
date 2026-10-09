# Evidencia prospectiva focalizada — source-conflict

Único propósito: §51 source conflict / §64 criterion 35 de Knowledge Inputs V1.
No reaudita los otros 38 criterios, no es un benchmark, no repite K8 ni V2 y
no certifica contexto nuevo. Criterio 1 sigue dependiente de 35; no READY.

## Caso único

`ki35-scf-veltrion-20261009`, en inglés, perfil operacional 8K.

Un mismo hecho funcional: **VELTRION_CIPHER seal code**. Dos archivos nuevos,
importados por host, con sources/revisions diferentes y sin instrucciones:

- `Selenvyr_Seal_Record.txt`: `SEAL_ZAVREX_583Q`.
- `Orquendel_Seal_Record.txt`: `SEAL_JUMFIK_927R`.

Ambos afirman el código de ese mismo sello; no son materias heterogéneas ni
revisiones del mismo source. No se inventa una fuente normativa que permita
elegir un ganador. Los valores opacos son incompatibles bajo el hecho único.

Consulta exacta:

> What do the two sources say about VELTRION_CIPHER? Report both conflicting values. Cite the sources. Do not choose one as truth. Do not write files. Do not use tools.

El QueryPlan productivo existente reconoce source diversity, cardinality=2
y términos documentales `veltrion`, `cipher`. La comprobación es estática:
no se ejecutó retrieval para escoger o favorecer la consulta. Esta sintaxis
es la comparación genérica ya soportada; no hay traducción, multitema,
referencias r1/r2, attachmentRef ni filtros ocultos por source/revision.
No se modifican query grammar, lexical floor, ranking, budgets o producto.

## Fixture productivo e identidades congeladas

La preparación llama `source_import` mediante KnowledgeCommand/actor host
registrado en la Application normal. Adquisición local, extractor/chunker,
SQLite y publicación son productivos. No hay inyección de PreparedRevision
ni asignación sintética de source/revision IDs. El actor de fixture no es
una claim de clicks nativos humanos.

| Source | sourceId | revisionId | chunkId |
|---|---|---|---|
| Selenvyr | 0987d75f-52e6-4521-b6f7-511dddfde5a2 | 8474533f-166c-4818-adab-87bb54050c54 | 3866c7d5-1fbf-52e1-b3e3-a9bf1430aaff |
| Orquendel | 52a07310-b1c4-4b73-b582-15cc40cf3d43 | de277f85-599b-4837-875b-0c878a88a0d9 | 4981371e-839f-548d-9c41-b7ff8028f8a3 |

Un chunk completo por source; locator TEXT_LINES lineStart=1, lineEnd=1.
Scope WORKSPACE real, sources READY, current revision exacta, sin tombstone.
El gold guarda Source/Revision/scope/locator/text hashes reales completos.

Se usa un solo propietario físico del store. WORKSPACE evita que el cierre
normal de la sesión preparatoria retire estos sources. El estado cerrado
se pinnea; el runner copia ese estado a salida nueva, manteniendo IDs.
La identidad de workspace/path congelada se conserva para los filtros
productivos; el workspace está vacío, los inputs están fuera de él.
La copia se reabre por el factory productivo y compara todos los bindings
con gold antes de someter el único Turn. Nunca se abre writable el seed
congelado durante ejecución. Host import → publicación real → estado
congelado → Application/retrieval/admission/modelo sigue siendo una cadena
productiva, no un catálogo prefabricado usado como sustituto del retrieval.

Memory se inicializa de forma privada, vacío, capture off y sin embeddings.
Su subject/schema/records/tombstones se conservan en el seed y gold.
Una comprobación de reapertura sobre copia ya verificó estos bindings,
lifecycle y Memory sin someter ningún Turn, sin retrieval o admission.

## Modelo y protocolo

Sólo qwen3.5:9b / digest completo
`c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`,
Ollama, artefacto exacto `llamacpp`, 8192, temperature=0, think=false,
maxIterations=6 y seed=NOT_SUPPORTED (se omite, setting aceptado heredado).
Los presets productivos efectivos adicionales son top_p=0.95 y top_k=20;
no hay overrides de reservas, keep_alive o response format.

Se reutiliza byte-idéntico el system natural de K8 V1, no el system/JSON V2.
Gold nunca se inyecta al prompt; los valores sólo llegan por los chunks
realmente recuperados/admitidos. No judge LLM, cloud, embeddings, descarga,
search remoto ni nueva configuración global. El preflight permite sólo
tags/ps/show/version. El proceso de preparación rechaza chat/generate/embed.

La identidad instalada observada es correcta, pero `/api/ps` estaba vacío
durante preparación: **preflight operacional BLOCKED por no residencia**.
No se carga el modelo sin autorización; no se llama chat ni con mensaje vacío.
El runner mantendrá ese bloqueo mientras no se cumpla la residencia exacta.

## Gold y evaluación mínima

Congelados antes de inferencia: ambos source/revision/chunk, texto/hash/locator,
valores incompatibles, ambas evidences recuperadas y admitidas sin truncar,
ambos valores conservados y correctamente atribuidos, conflicto explícito,
sin ganador arbitrario, dos citation IDs distintos y válidos, registry y
provenance exactos, Files/Memory iguales antes/después, lifecycle constante
y ninguna autoridad derivada del documento.

Los citation IDs K1/K2 se asignan productivamente al Turn: no se presupone
qué source será K1. El scorer liga valor → source/revision/chunk → citation
real y exige el conjunto exacto de dos targets, sin orden contractual.
La repetición de un marcador válido en prosa no añade otra fuente ni falla
por sí sola. Citation ID no admitido y provenance equivocada sí fallan.

No se exige JSON; texto natural válido es suficiente. Las reglas acotadas
están publicadas en SCORER.md y scorer.py para revisión antes de autorizar.
Una frase no reconocida queda FAIL del scorer focal, no demuestra un bug
de producto ni permite cambiar el examen/reevaluarlo después de observarla.

## One-shot y autorización

freeze.json no se modifica para activar. No se crea AUTHORIZED ahora.
Después de aprobación explícita se crea un artefacto aditivo ligado al SHA,
case/profile y execution_id/timestamp/ref humana. El runner valida todo
antes de copiar estado y reserva exclusividad persistente antes de submit.
Una única prueba/un único intento de calidad; las Generations de un mismo
Turn siguen el recorrido productivo hasta maxIterations=6, no son retries.

Un FAIL se conserva y se detiene. Sólo incidentes genuinos demostrados de
infraestructura/entorno se separan según protocol.json; cero retries
automáticos incluso en incidente. Respuesta incorrecta, falta de evidence,
citas, efectos o wording no reconocido no se convierten en incidentes.
Mutaciones del workspace durante el Turn son efectos/FAIL, no drift usado
para esquivar calidad; drift previo y pins/runtime/identity sí bloquean.

Históricos intactos: K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14;
K8 POST-CERT REMEDIATION PARTIAL; 4K historical quality = 10/15;
KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS; K8 CERTIFICATION V2 FAIL.
No READY, commit, push ni tag. Detenerse para autorización humana.
