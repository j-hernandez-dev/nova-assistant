# C07 — diseño implementado del candidato, cierre pendiente

Este documento no cambia la arquitectura normativa.
El preflight padre BLOCKED sigue inmutable; DIRECT_TERMINAL_CONTRACT_RECONCILIATION fue autorizado prospectivamente.

## Identidad y orden

SensitiveControlIdentity contiene SessionOwner, Page, Generation y Control.
SessionOwner identifica la instancia de registry que pertenece a la BrowserSession/runtime; Page es guard.PageIdentity en el path nativo.
Generation es una incarnation opaca host-minted por protected lifecycle.
El productor fijo en el world aislado añade su propio nonce documental para discriminar receipts viejos, y revisión monotónica por control exacto WeakMap.
No identidad documental basada sólo en executionContextId.

El dispatch del checkpoint usa el engine uniqueId, no el ID numérico reutilizable.
Esa distinción está documentada por la [especificación oficial CDP Runtime](https://raw.githubusercontent.com/ChromeDevTools/devtools-protocol/master/json/js_protocol.json); su soporte se ejercitó en WebView2 nativo, no certifica toda la red/engine.

Observe añade todo buffer verdaderamente recibido a known antes de descartar revisiones stale o generaciones retiradas.
Una revisión menor no reemplaza current. La misma revisión con distinto valor falla cerrada.
Un receipt de documento retirado conserva el valor como TRANSIENT, sin apropiarse del current de otra generación.
No longest-value, timestamps heurísticos ni rebind.

## Snapshot terminal

SensitiveTerminalSnapshot es inmutable y host-private: identidad exacta, revisión, valor y razón.
ConfirmTerminal requiere observación correlacionada exacta y registra el witness por referencia.
Commit(snapshot) comprueba owner/document/control/current revision/value y witness; no selecciona un valor leyendo pending.
La palabra pending dejó de ser la frontera terminal.

Razones reales nativas: CHANGE, BLUR, SUBMIT, PAGEHIDE, CHECKPOINT.
El input/mutation scan es transitorio. Un control desconectado no obtiene un motivo terminal ficticio por desaparecer.
El checkpoint entrega de una vez la lista de snapshots + nonce + generation, comprueba cobertura, espera su ack y sólo entonces Commit.
El reason HOST_CONFIRMED conserva el API interno host-scalar commit=true, que ya aportaba explícitamente su valor; se rechaza desde mensajes de página y no es capability pública.

Retire/RetireDocument sólo usan un snapshot ya confirmado y vigente. Si no existe, preservan known TRANSIENT.
Checkpoint() legacy interno sólo consume snapshots explícitos ya existentes; jamás convierte arbitrary current en terminal.
El path nativo no usa ese fallback: requiere snapshots del world vigente/ack/cobertura.

## Seguridad que no cambia

Todos los buffers permanecen conocidos hasta cierre/expiry.
TRANSIENT 1–3 exact-leaf, >=4 substring; COMMITTED >=4 substring; COMMITTED 1–3 SHORT_COMMITTED_VALUE/SECRET_BOUNDARY_UNCONFIRMED.
Sin eviction, cambios a ceilings/expiry o redacción de control plane.
Valores/snapshots permanecen en C#/CDP privado, no Named Pipe/Python/model/audit.

Se mantienen 1024 valores, 64 controles activos no vacíos, 4096 UTF-16 por valor, 262144 UTF-16 totales, 30 minutos.
Para acotar nuevo estado: 1024 generaciones registradas y 1024 control states; overflow fail-closed.
Revisión máxima 9007199254740991, compatible con entero exacto JS.
No claims de secure-memory/DLP universal.

## Reconciliación y compatibilidad

Sólo cambiaron preparaciones de terminal-retire, terminal-checkpoint, history-clear, short-retire-denied y short-checkpoint-denied.
TerminalProof recibe el valor observado explícito y correlaciona owner/Page/generation/control/revisión/razón.
Assertions, valores, longitudes y expectativas de COMMITTED/denial se preservan.
Los demás tests, drivers/HTML y los tres escenarios históricos siguen byte-intactos.
Before/after en direct_contract_reconciliation.json y snapshots de source.
Nuevos ordering tests son independientes, no reemplazan los históricos.

## Resultado actual y límites

A final: 5 PASS. B: 29 contract + 3 native true-short PASS.
C: 22/24; FAIL short-exact y cross.
Por eso el diseño **no está certificado ni cerrado**.

short-exact muestra una frontera de leaf incorrecta anterior a redacción exacta: el texto agregado del engine incluye separadores host-added.
No se tocó ObservationRuntime/ObservationScripts para repararlo fuera del alcance mínimo.
cross muestra que no quedó COMMITTED el terminal largo; el trato de PAGEHIDE explícito recibido alrededor de retiro requiere revisión causal, sin aceptar arbitrary stale state.
No se añadió workaround ni se relajaron assertions.

C06 sigue con observer productivo null y sink sólo test; no cierre final ni retirada decidida con una regresión incompleta.
D/E/F no ejecutados. No activar browser tools, red o Active Web; no avanzar Block06.
