# Source-Conflict Focal — SCF-R2

Revisión explícita exclusivamente del guard de parámetros del bridge.
No es K8 V2, V2-R5, otro benchmark, cambio de Nova ni una nueva expectativa
de respuesta. Mismo caso `ki35-scf-veltrion-20261009`, sólo 8K.

Parent freeze inmutable:
`549adb90296c8eb92dec6fb70994c1e4d61d62d611670764e937531c44f83364`.

Parent result inmutable: `SOURCE_CONFLICT_FOCAL_E2E = FAIL`.
El intento/reserva original sigue consumido: no reset, eliminación del ledger
o conversión retrospectiva a incidente. La autorización original no sirve
para el nuevo SHA. **No se crea AUTHORIZED para SCF-R2 ahora.**

## Única corrección funcional

Nova añade productivamente options.num_predict desde
BoundModelRuntime._prepare / budget.output_reserve. El guard anterior
comparaba literalmente todo options contra el preset sin esa clave.

El nuevo guard conserva el preflight inmediato y la identidad real
nombre+digest/runner/residencia. Exige los cuatro parámetros obligatorios
temperature=0, top_p=0.95, top_k=20 y num_ctx=8192, think=false,
sin response format/seed, drift o opciones adicionales.

Sólo permite la clave opcional num_predict si es entero y exactamente
igual al output_reserve del último reporte context_budget del Turn
propiedad de la sesión productiva. Para este caso ambos deben ser 1024
y selected_context_window debe ser 8192. No se toma ese valor del request,
gold, texto documental o un booleano del caller. Si falta el reporte,
hay drift de reserve o num_predict es distinto, bloquea.

Se usa el Turn propiedad de la sesión, que existe antes de arrancar el
worker; no se depende de que la asignación runner.last_turn haya terminado.
La validación observa las opciones, nunca las elimina ni las reescribe.
El preset anterior sin num_predict conserva su validez; no se amplía
ningún parámetro obligatorio ni se aceptan extras distintos.

## Preservación por bytes

Copias exactas de corpus, gold, execution profile, protocolo,
authorization schema, reglas semánticas, fixtures, scorer.py y runner.py.
Mismo seed/path/tree congelados; no nuevo import, source UUID, revisión,
chunk, Memory, query, retrieval/admission, presupuestos o modelo.

common.py sólo cambia dos referencias de ubicación para que ROOT resuelva
el mismo checkout y DOCS seleccione esta revisión. No cambia ningún control,
backend, función de preflight, autorización, ledger, retry o ejecución.
runner.py y scorer.py mantienen sus bytes íntegros; sus imports relativos
seleccionan la revisión nueva de bridge/common. Es metadata inevitable de
routing, no cambio del comportamiento productivo ni del protocolo.

Bridge fuera del guard permanece sin modificaciones. La cadena de pins
heredada se conserva; el nuevo freeze añade la revisión, tests y metadata.
Todas las diferencias están verificadas en manifest/diff antes del freeze.

## Tests y límites

55 tests focalizados del guard + 35 tests sintéticos originales del scorer:
90 PASS; ninguna solicitud de red, Application submit, inferencia,
retrieval o admission real. Se cubre reserve correcto, valor incorrecto,
parámetros ausentes/alterados, tipos inválidos, extras, think/model/format,
digest/runner/residencia, preflight previo, budget real ausente/drift,
report de Turn vigente y la adición productiva de num_predict a partir de
un budget sintético, sin llamar al proveedor.

No se ejecuta un Turn de calidad bajo SCF-R2. El preflight por defecto es
read-only y no crea autorización, output de campaña ni ledger.

Entrypoint congelado futuro:

`python -B -m tests.knowledge_inputs_v1.source_conflict_focal.revision_02.runner`

Sin --execute sólo preflight. --execute requiere una aprobación aditiva
separada ligada al nuevo SHA; no está autorizada en esta etapa.

Históricos intactos: K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14;
K8 POST-CERT REMEDIATION PARTIAL; 4K historical quality = 10/15;
KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS; K8 CERTIFICATION V2 FAIL.

No READY, commit, push ni tag. Detenerse para autorización humana.
