# V12-B5 — Recertificación transfers / takeover / secrets

Fecha de la entrega: 2026-10-11, America/Mexico_City. Baseline humano aceptado:
B0–B4 PASS. Cierre exclusivamente B5; detener para revisión humana.

```ini
V12_B5 = PASS
SAFE_TO_START_V12_B6 = true
interactiveBrowser.networkIsolation = NOT_PROVIDED
interactiveBrowser.controlClass = HOST_UNISOLATED
interactiveBrowser.productiveAvailability = NOT_ENABLED
```

## Composición candidata

Perfil `IB_B5_WEBVIEW2_V5_TRANSFERS_TAKEOVER_KNOWN_VALUES_WINDOWS_X64_V1`.
WebView2 Runtime `154.0.4258.62`, SDK `1.0.4258.31`, X64; .NET SDK `10.0.203`,
runtime observado `10.0.7`; private IPC v5. El host nativo y las decisiones de
SensitiveValueRegistry/terminal authority permanecen byte-intactos respecto al
baseline. No actualización de SDK/runtime, Chromium/CEF ni migración de engine.

DLL evaluada:

```text
6c38ae8509259693a59a162fa2e14da7c80fd373236f054cc9e5d40a205217ab
```

El runner terminal carga la misma DLL exacta. [candidate_identity.json](candidate_identity.json)
fija fuentes, configuración, módulos .NET y digest de la composición.
La disponibilidad productiva sigue deshabilitada; no integración B6.

## Gates

| Gate | Resultado |
| --- | --- |
| UPLOAD_AUTHORITY / UPLOAD_IDENTITY_REVALIDATION | PASS |
| DOWNLOAD_AUTHORITY / DOWNLOAD_DRIVE_BY_DENIAL | PASS |
| DOWNLOAD_STAGING / TRANSFER_OUTCOME_INTEGRITY | PASS |
| HUMAN_TAKEOVER / TAKEOVER_EPOCH_INVALIDATION | PASS |
| AGENT_PAUSE_DURING_TAKEOVER | PASS |
| SECRET_NON_EXPOSURE / MONOTONIC_SENSITIVE_KNOWLEDGE | PASS |
| SECRET_CONTINUITY | PASS |
| TERMINAL_AUTHORITY / TERMINAL_PROVENANCE | PASS |
| UNCONFIRMED_TERMINAL_DENIAL / LATE_EVENT_REJECTION | PASS |
| OWNED_CLEANUP | PASS |
| HISTORICAL_EVIDENCE_WRITE_GUARD | PASS |

Los nombres completos `INTERACTIVE_BROWSER_*` y sus evidencias están en
[manifest.json](manifest.json).

## Implementación acotada

Nuevas fuentes:

- `local_cli/application/browser_actions_v12_b5.py`: extensión focal opt-in de
  B4 para upload/download/takeover. Reutiliza ToolRuntime, PolicyEngineV2,
  ApprovalGate, GrantIssuer y BrowserTakeoverService existentes.
- `local_cli/core/browser_transfers_v12.py`: binding cerrado con namespace,
  owner/workspace/task/operation, epochs/refs, metadata de archivo y permit.
- `local_cli/infrastructure/active_web/webview2_transfers_v12.py`: selección
  Windows exacta sobre el mecanismo de read lock existente, expiry y scope
  sellado; browser download permit de un uso y provenance/owner/TTL del staging.
- `native/nova-browser-host/tests/v12_b5/`: fixtures, contratos, guard de
  almacenamiento y runner terminal separado. No action JS/eval productiva.

Tres cambios causales en fuentes existentes:

- `browser_actions.py`: fence de autoridad después de preparar el locked read,
  justo antes de entregar el payload al engine; libera el lock si falla.
- `browser_actions_v12.py`: hook de validación para extender el binding B4,
  conservando su comportamiento por defecto.
- `browser_authority_v12.py`: extensiones explícitas del validator para el
  perfil B5; defaults B4 conservan closure y taxonomía estrictas.

Las evidencias B0–B4 no se reabrieron. El host, el protocolo v5 y la lógica
terminal histórica no se editaron. No nueva Policy/Approval authority.

## Upload: archivo exacto antes de disclosure

El único origen es HostFileSelectionRef host-issued. Selección queda ligada a
owner, workspace/task, turn/operation, sesión/página, context/navigation epoch,
observación/version, ElementRef/fingerprint, origin, deadline y path identity
privada; file identity/revision, size, MIME y digest se conservan exactos.

El modelo no suministra paths/handles/selectors ni “whatever is in Knowledge”.
Approval se liga a archivo, target, origin y operación exactos. UPLOAD se
clasifica FILE_UPLOAD + DATA_DISCLOSURE + REMOTE_MUTATION. Entregar el archivo al
input constituye disclosure antes de submit.

Justo antes del efecto se revalida el archivo bajo read lock sin write/delete
sharing y se comprueban identidad/revisión/size/digest/MIME. El lock se mantiene
hasta dispatch; la copia inmutable privada queda bajo el UDF owned del request
y lifetime del browser. No crea permiso reusable y se limpia con ese UDF.
Después del prepared read se revalidan Grant consumido, Policy vigente,
deadline/ticket y no-bypass. La prueba de cambio de Policy en ese punto niega
antes de disclosure y confirma que el lock se libera.

WebView2 real observa la asignación al nodo exacto y la página confirma el archivo
esperado. Esto demuestra entrega al DOM, no aceptación/submission del servidor.
File replaced/modified, revision/digest/owner/operation/origin/expiry falsos,
wrong node/page y stale epoch/ref quedan sin archivo accesible en el DOM.
Replay del Grant no consume ni entrega otro upload.

## Browser download y staging

Download exige permit browser exacto, FILE_DOWNLOAD, session/page/document/epoch,
operation/ref, destino conocido y límites de size/time/MIME. No hereda proof,
Grant ni PUBLIC_ONLY de Controlled Fetch. La red del browser no se certifica.

Drive-by real: DownloadStarting cancela pre-effect. Se verifican cero staging,
cero partial files, cero `.crdownload`, pending vacío y ningún download
aceptado. Una denegación nominal del evento no se usa como única prueba.

Un download autorizado sólo se declara STAGED tras el evento nativo
DOWNLOAD_COMPLETED con State=Completed, lectura del artifact owned, size y
digest coincidentes. Filename remoto es dato no confiable; no selecciona path
final. No auto-open/execute/export/Knowledge/import a otra capability.

El staging es independiente del UDF. Se demuestra que un artifact completado
retenido sobrevive al browser close, conserva owner/expiry/provenance y digest,
y desaparece sólo con discard explícito o cleanup del fixture owned. No se
declara un artifact existente después de borrarlo. Pending, oversized, cancel,
disconnect/crash después de STARTED quedan UNKNOWN/PARTIAL y no COMPLETE.
No retry ni segundo consumo del permit.

## Takeover / epochs

La propuesta entra por la autoridad V1.2 B4 y Approval exacta; BeginTakeover es
host-owned y pausa la sesión. Se prueba humanActive, prohibición de agent actions,
EndTakeover, incremento de epoch, refs antiguas inválidas y nueva observación
antes de usar el estado reanudado. Login humano no autoriza otra mutación ni
Controlled Fetch.

El guard absoluto de external protocols permanece activo durante el takeover
completo y después del end. Se observa cancelación nativa del intento durante
humanActive y DENY_ALL después. El mecanismo/SDK/guard no cambiaron; la prueba de
handler registrado pre-effect de B3 se reutiliza con su alcance original.
No se repite la campaña B3.

## Secret boundary y terminal authority

Scope: declared-sensitive / known values protegidos de superficies públicas de
Nova. No universal DLP, detección de transformaciones arbitrarias, borrado
forense ni protección frente al sitio receptor.

La credencial sintética nace en el driver UI nativo y no llega completa a Python,
Named Pipe público, archivos de evidencia ni argumentos de tool. Se registra
sólo SHA-256 y booleans. Se comprueban Observation/ElementRef metadata,
ToolResult/ToolRuntime result, audit, descriptor, metadata pública, IPC,
contexto del modelo y errores/proyección terminal. La regresión focal cubre
text/title/label/form/dialog/URL/href/state con instrumentación fija/schema-aware.

Caso histórico importante recertificado: humano introduce un secreto sintético,
la página intenta reflejarlo, hay checkpoint legítimo, end/epoch, navegación
same-origin y observación de documento nuevo; el valor conocido sigue redactado.
Sólo se reintenta observación read-only cuando la navegación termina de asentarse,
sin repetir el click. La sensibilidad es monotónica.

Se conserva literalmente la decisión:

```text
Sólo SUBMIT_CONFIRMED y TAKEOVER_END_CHECKPOINT producen
TerminalSnapshot COMMIT-able.
```

INPUT/CHANGE/BLUR/PAGEHIDE/ENGINE_WORLD_RETIRE, silencio, close, timeout o
desaparición DOM no son terminales. Retirement preserva valores y lineage,
no manufacture snapshot ni Commit. Si se destruye la lineage sin terminal
válido: SECRET_BOUNDARY_UNCONFIRMED, sin resume ni publicación previa de una
observación nueva.

El runner real prueba ambos terminales legítimos, valores terminales len 1..3
SHORT_COMMITTED_VALUE, retiro sin snapshot y late checkpoint en un documento
retirado. El late event no puede Commit, limpiar incertidumbre ni reanudar.
Los contratos focales cubren wrong owner/page/generation/world/revision,
snapshot stale/forged y late new/stale/duplicate. No se amplía FORM_SUBMIT:
el caso SUBMIT_CONFIRMED usa sólo la primitive histórica host-fixed de harness.

## Guard de evidencia histórica

Durante todos los tests: outputs a temp owned. Un audit hook veta antes del
efecto escrituras Python en `docs/active_web_v1/**` y `docs/active_web_v1_2/**`.
Para subprocesses .NET, un deny NTFS temporal impide write/delete en esos
directorios; las ACL originales se restauran exactamente al finalizar.
No se cambia ExecutionPolicy ni se reclama sandbox de OS/browser.

Probes Python y .NET confirman denegación sin archivo creado. Los helpers B3/B4
reutilizados se redirigen **antes de ejecutar** a temp owned. Cero escrituras
históricas exitosas; no “restaurar después por hash”. Tras la ejecución y restore
del guard se congelan outputs únicamente bajo B5. La integridad vuelve a
comparar el baseline completo.

## Pruebas y cleanup

| Clasificación | Resultado |
| --- | ---: |
| Nuevas B5 | 98 PASS: 36 nativas + 62 contratos |
| Regresión focal reutilizada | 365 PASS |
| Total final | 463 PASS, 0 fail/error/skip |

No se suman denominadores históricos, ni se reejecutan los 561 tests completos.
Los intentos previos quedan congelados sin recalificación: spelling de evento,
epoch mal consultado en fixture y observación durante navegación asíncrona.
No cambiaron el diseño terminal ni redujeron los gates.

Se confirman los 29 browser instances de la suite final y los 7 roots del runner
terminal. Los read locks/copies, staging y listeners propios se liberan. Se
verifican también 87 instancias owned de las pasadas B5, sus UDF ausentes y los
journals propios congelados/eliminados. El único diagnóstico de continuidad de
la regresión se liga a su ventana/proceso/magic/version y se congela/elimina como
leaf exacta owned; no se mantiene ni borra ningún UDF/perfil histórico. Ocho
directorios temporales explícitos se eliminan después de congelar sus salidas.

Baseline de 6888 archivos verificado; sólo cambian las tres fuentes causales
descritas. Históricos y cierres B0–B4 permanecen byte-intactos. HEAD igual;
sin commit/push/tag/release. Native host source y transporte B2 intactos.

## Estado preservado

```ini
ACTIVE_WEB_V1_2_ARCHITECTURE = APPROVED
V12_B0 = PASS
V12_B1 = PASS
V12_B2 = PASS
V12_B3 = PASS
V12_B4 = PASS
controlledFetch.networkEgressControl = ENFORCED
controlledFetch.publicOnly = ENFORCED
controlledFetch.productiveAvailability = NOT_ENABLED
evidenceProfile = CF_B2_GET_HEAD_HTTP11_WINDOWS_V1
POST = NOT_AVAILABLE
auth = NOT_AVAILABLE
binaryDownload = NOT_AVAILABLE

WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
WEBVIEW2_BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
CEF_CHROMIUM_STANDARD_CANDIDATE = REJECTED
SOURCE_CONTROLLED_CHROMIUM = REQUIRES_SOURCE_PROTOTYPE
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

No desviación del diseño terminal aprobado. Extensiones de binding y fence
final de transfer son cambios causales mínimos de B5; B4 mantiene defaults y
su regresión relevante. No B6/B7, network recertification, Chromium/CEF,
historical AW8 E2E ni mantenimiento de recursos históricos. Detenido para
revisión humana.

```ini
V12_B5 = PASS
SAFE_TO_START_V12_B6 = true
```
