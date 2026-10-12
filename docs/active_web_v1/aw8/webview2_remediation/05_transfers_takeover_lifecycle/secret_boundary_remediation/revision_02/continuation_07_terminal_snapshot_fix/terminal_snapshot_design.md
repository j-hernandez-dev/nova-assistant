# Terminal snapshots — preflight de diseño interno C07

Estado: **propuesto, no implementado**. No modifica V1/V1.1 ni sus claims.
La reparación funcional está autorizada, pero su gate B exige reconciliar preparación contractual que sigue codificando la promoción implícita prohibida.

## Dirección autorizada

Separar current observado de terminal confirmado:

- Identity: BrowserSession owner + Page + document incarnation opaca + control opaco.
- Current: revision monotónica del productor fijo host-owned, currentValue sólo host-private.
- Terminal: snapshot inmutable realmente observado, terminalRevision, terminalValue host-private, reason existente y witness/correlación.
- Conocimiento: todo buffer observado se añade al conjunto conocido; edición, navegación y epoch no lo eliminan.

La incarnation no se reduce a executionContextId. Una reutilización numérica no puede adoptar un control anterior.
Una revisión vieja/duplicada sigue siendo conocida cuando corresponde, pero no reemplaza current más nuevo ni genera terminal para otro documento.
No escoger longest/newest por timestamp ni hacer heuristic rebind.

## Commit y retiros

Commit debe consumir el snapshot explícito y comprobar owner/session/Page/incarnation/control/revision y prueba de observación.
Terminal de longitud 1–3 continúa SHORT_COMMITTED_VALUE → SECRET_BOUNDARY_UNCONFIRMED.
No cambia TRANSIENT corto exact-leaf ni substring >=4, monotonicidad, bounds/expiry o schema-aware redaction.

Retire nunca fabrica terminal desde un current arbitrario:
usa prueba terminal ya confirmada, conserva TRANSIENT o falla cerrado si la continuidad requerida no puede establecerse.

Para un world vivo, el checkpoint debe recibir del productor exact current/revision/incarnation y ack correlacionado.
No puede limitarse a invocar Commit sobre el último pending local.
CHANGE/BLUR/SUBMIT/PAGEHIDE/CHECKPOINT sólo pueden usarse si el productor confirma esa frontera concreta.
La selección definitiva de estos eventos y los callers nuevos **aún no está implementada**; no se inventan razones ni se anuncian capabilities.

## Reconciliación necesaria del gate B

Los tests directos anteriores carecen de generation/revision/terminal witness:
terminal-retire exige State(longValue,COMMITTED) tras sólo Input(commit=false)+Retire.
terminal-checkpoint exige lo mismo tras un Checkpoint sin snapshot.
Mantener una compatibility branch que vuelva a seleccionar pending para satisfacerlos reintroduciría exactamente el defecto rechazado.

Se propone pedir autorización para adaptar **sólo la preparación y llamadas** de los contratos afectados:
suministrar prueba terminal correlacionada explícita antes del retiro/checkpoint.
Todas las assertions de protección, monotonicidad, clasificación y denial corto permanecen.

Los tres escenarios históricos, valores/driver/HTML/sleeps/timeouts/assertions no cambian.
Los casos short deben demostrar una credencial verdaderamente terminal corta, no usar el error por falta de proof como sustituto de SHORT_COMMITTED_VALUE.
No se realiza esa reconciliación sin nueva autorización.

## Diagnóstico y validación

C06 permanece aceptado y byte-intacto como historia. No se cambió su sink ni la clasificación interna en este preflight.
La decisión sobre conservar el diagnóstico sólo para tests se tomará al cierre real, no ahora.

Orden pendiente:
A ordering contracts → B policy 24 → C históricos 15 → D focal 33 → E full final.
A–E no ejecutados; ningún denominador medido.
Todos los gates siguen sin demostrar en un candidato reparado.

No existe nueva implementación, protocol schema, public authority, capability, network o Active Web disponible.
