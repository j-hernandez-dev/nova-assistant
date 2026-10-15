# S7 — Security Audit / Provenance

SEC12-OD-05 resuelta por autorización humana; implementación productiva S7.
Estado/gate y evidencia definitiva en `s7_resultados.md` y `s7_manifest.json`.
Core V1 y SECURITY V1.2 son normativos.

## Fronteras

Core declara `SecurityAuditPort`, `SecurityAuditRecord`, `AuditKind` y errores.
Application coordina `SecurityAuditService` y los puntos de registro.
Infrastructure implementa `JsonlSecurityAudit` con biblioteca estándar. No hay imports
de Application/Infrastructure en el nuevo contrato, ni cambios a AgentRuntime,
nombres/schemas de tools, transportes públicos o lifecycle Core.

Audit no se obtiene reconstruyendo texto de SessionLogger/transcript ni
reutilizando EventJournal. Tiene stream ID, sequence y record ID propios. La
composición host puede inyectar un port en AgentSessionCoordinator; CLI/Desktop
usan el mismo ToolRuntime/Application. No hay un flag del LLM/renderer ni una UI
de audit nueva. Las composiciones normales CLI y Desktop activan el adapter
durable común. Embedding directo puede inyectar fixtures explícitas; no es una
segunda ruta productiva ni elección de formato dentro de AgentRuntime.

## Schema 1 y privacidad

Envelope: schemaVersion, recordId, auditStreamId, auditSequence, timestamp,
kind, sessionId, turnId, operationId, toolCallId, agentId, tool, origin, data.
DTO profundamente inmutable; codec rechaza versión/campos/tipos inesperados,
objetos bearer y registros mayores de 64 KiB. Ese límite es del codec, no una
retención productiva ni cuota OS. IDs de audit nunca conceden autoridad.

Data es un resumen admitido explícitamente. No grant request completo, issuer
credentials, authority fingerprints, raw arguments, values de environment,
stdout/stderr, archivo/body bruto, task/prompt del subagente ni exception trace.
Grant sólo conserva ID/parent ID, permisos/scopes/controlClass resumidos y digest.
URLs descartan credentials/query/fragment incluso para valores no registrados.
La redacción S6 se aplica antes de append; selección host de variables registra
sus valores sensibles antes del registro de request. No se revisan secretos
arbitrarios del disco ni se reescribe evidencia histórica.

`origin` nombra la ruta main/subagent/Application, no prueba que el LLM sea el
actor original. `actor=cli_tty/desktop_host` procede de ApprovalGate y su actor
registrado, nunca de argumentos de la tool. Timeout/cancel/unavailable sin actor
humano quedan explícitos; no se inventa consentimiento.

## Registros de una operación

Request → policy → approval required/resolved cuando aplica → grant claimed →
dispatch solicitado → observaciones disponibles → terminal audit.
Denial/validación pueden terminar antes de grant/dispatch. No se fabrica digest
cuando el request no llegó a crearse. Reenvío idempotente no reejecuta ni añade
otro terminal. Audit nunca publica un segundo evento terminal Core.

En `StartSubAgent` host se registra la delegación realmente emitida/claimed;
no se inventa un ALLOW del PolicyEngine si ese servicio no fue invocado.
Lifecycle hijo guarda IDs de la operación real, sin inventar toolCallId para
comandos que no fueron tool calls. Tools hijas comparten el servicio y redactor,
con nueva identidad de sesión/agente y parent IDs/grant resumido.

## Qué efectos se conocen

- **Filesystem mediado:** plan/binding lógico y root/target identity; create/modify
  sólo cuando ToolResult informa `applied`; before/after hash e identidad cuando
  el broker los observó. Write-only no concede read para obtener un before hash:
  se informa `not_observed_no_extra_read_authority`. Error/partial/unknown no se
  presenta como modificación confirmada ni se añade un pathname read lateral.
- **Proceso:** se proyectan los reportes existentes S4. Launch/PID sólo si el
  launcher reportó PID; terminal/exit/states/cleanup/cancel/timeout/truncamiento
  conocidos. Observaciones post-report, no monitor continuo del proceso; un crash
  antes de retornar puede dejar sólo request/dispatch. El timestamp reportado de
  launch no certifica el instante OS exacto. `HOST_UNISOLATED`, árbol BEST_EFFORT.
  Nunca se inventa provenance de archivos internos del shell.
- **Red:** requested/effective URL, hops/destinos/status observados por cliente
  S5, truncamiento y errores/outcome; no socket/firewall claim del shell/provider.
- **Subagente:** lifecycle observado y correlación jerárquica. Su efecto global
  no se deduce automáticamente como `none` de un retorno exitoso.

`reconstruct_operation` ordena un stream/subject, rechaza mezcla/terminales
contradictorios y resume únicamente lo observado. `completeObservedLifecycle`
significa presencia de request/start y terminal, no cobertura de efectos OS.
Sin terminal: outcome `not_observed`, effect `unknown`, nunca éxito.

## Persistencia, durabilidad y fallos (OD-05 autorizada)

JSONL fuera del workspace: segmentos 10 MiB, retención de cerrados propios hasta
100 MiB o 30 días. Nunca purga un activo, evidencia previa ni archivos ajenos.
Header/namespace reservados, archivos regulares sin aliases/hardlinks, locks
nativos de writer/rotación. Capacidad llena de activos: fallo cerrado, no purga.
Detalles de paths, edad, ownership y limitaciones en `SEC12_OD_05_S7.md`.

Admisión durable después de policy/approval/grant y antes de dispatch efectivo:
`flush+fsync` incluye todos los registros previos. Fallo de append/validación o
sync previo → `SECURITY_AUDIT_PRE_EFFECT_FAILED`, denied/none, sin iniciar efecto.
Terminal audit hace flush+fsync; fallo posterior mantiene el outcome/effectState
observado y añade `metadata.securityAudit.gap`, código seguro y no-retry.
Eventos Core conservan terminal único; llevan el aviso, sin nuevo lifecycle.
CLI lo muestra directamente; Desktop usa su banner existente y la proyección
de snapshot/event, sin pantalla general de audit ni decisiones en frontend.
El health de Application informa delivery failures y storage gap codes.

Rotación/cierre sincronizan antes de sellar. Crash/reopen sella sólo huérfanos,
preserva bytes completos/tail, y el lector ignora filas incompletas/inválidas.
Gaps no contienen contenido/exception privada. Terminal ausente nunca equivale
a éxito ni autoriza replay/retry. Retención puede retirar partes del lifecycle.

Los tests distinguen el port en memoria, adapters de efectos mock y JSONL nativo.
Crash/reopen incluye un subprocess fixture real terminado con `os._exit(37)`;
no PowerShell/toolchain real, provider real, red externa o nueva certificación
S3/S4. No se presenta la redacción como detector universal de secretos.
