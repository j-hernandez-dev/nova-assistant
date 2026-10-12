# V12-B3 — Baseline Interactive Browser

Fecha: 2026-10-11. Baseline de entrada aceptado: B0/B1/B2 PASS.
Se cierra exclusivamente B3 y se detiene el trabajo para revisión humana.

```ini
V12_B3 = PASS
SAFE_TO_START_V12_B4 = true
interactiveBrowser.networkIsolation = NOT_PROVIDED
interactiveBrowser.controlClass = HOST_UNISOLATED
interactiveBrowser.productiveAvailability = NOT_ENABLED
```

## Candidato evaluado

Perfil: `IB_B3_WEBVIEW2_HOST_V5_WINDOWS_X64_BASELINE_V1`.

| Componente | Identidad |
| --- | --- |
| Capability | `INTERACTIVE_BROWSER_V1_2` |
| Adapter | WebView2 existente; observación/guard/host de IPC v5 |
| SDK WebView2 | `1.0.4258.31`, paquete local; sin descarga/actualización |
| Runtime WebView2 | `154.0.4258.62`, X64 instalado |
| .NET SDK | `10.0.203` |
| .NET Runtime | `10.0.7`; `coreclr.dll` observado dentro del host candidato |
| Host DLL SHA-256 | `73bd432a41a49c94e653c4741c54295f600156c70a1a9972d1c872716244053a` |
| Productive availability | `NOT_ENABLED` |

Los digests de fuentes, SDK, runtime, DLLs, configuración y del conjunto
candidato están en [adapter_identity.json](adapter_identity.json). Se conservan
los binarios exactos evaluados. El runner de canarios cargó la misma DLL del
host. La sonda de identidad reutilizó esos bytes y confirmó el árbol del Job
Object, el runtime efectivo y el cierre de su UDF propio.

SDK/runtime/arquitectura coinciden con el cierre histórico de Block05. Las
fuentes existentes del host y del adapter permanecen byte-intactas. La DLL se
compiló desde esas fuentes en un directorio temporal propio, con feed local.
El único delta de arquitectura es un descriptor V1.2 aditivo y no productivo.
Las opciones defensivas preexistentes del engine permanecen configuración; no
se certifica un claim de red a partir de ellas.

## Gates

| Gate | Resultado |
| --- | --- |
| `INTERACTIVE_BROWSER_WEBVIEW2_ADAPTER` | PASS |
| `INTERACTIVE_BROWSER_PRIVATE_IPC` | PASS |
| `INTERACTIVE_BROWSER_LIFECYCLE` | PASS |
| `INTERACTIVE_BROWSER_STRUCTURED_OBSERVATION` | PASS |
| `INTERACTIVE_BROWSER_OPAQUE_REFS` | PASS |
| `INTERACTIVE_BROWSER_EXTERNAL_PROTOCOL_GUARD` | PASS |
| `INTERACTIVE_BROWSER_POPUP_CHILD_BOUNDARY` | PASS |
| `INTERACTIVE_BROWSER_CAPABILITY_SEPARATION` | PASS |
| `INTERACTIVE_BROWSER_NETWORK_ISOLATION_CLAIM` | NOT_PROVIDED |

También se registran los aliases solicitados: `WEBVIEW2_ADAPTER_BASELINE`,
`BROWSER_HOST_PRIVATE_BOUNDARY`, `BROWSER_LIFECYCLE_BASELINE`,
`STRUCTURED_OBSERVATION_BASELINE`, `EXTERNAL_PROTOCOL_GUARD_V12` = PASS;
`INTERACTIVE_BROWSER_NETWORK_CLAIM` = NOT_PROVIDED.

## Cambios

Se añadieron dos módulos internos:

- `local_cli/core/interactive_browser_v12.py`: descriptor cerrado y fijo de
  capability, adapter, trust, política externa y disponibilidad. Rechaza campos
  extra y cualquier intento de cambiar `NOT_PROVIDED` o `HOST_UNISOLATED`.
- `local_cli/infrastructure/active_web/interactive_browser_v12.py`: proyección
  opt-in desde el host privado existente; verifica sesión, instancia y guard
  instalado. No emite Grant, Approval, authority, tools ni snapshot productivo.

Se añadió `native/nova-browser-host/tests/v12_b3/test_baseline.py` y un runner
nativo separado bajo este directorio de evidencia. El host, IPC, adapter,
Application, Policy, Approval y producto existentes no se editaron.

## Evidencia nativa nueva

WebView2 real carga una página HTTPS virtual local y devuelve una observación
acotada a través del host separado y Named Pipe privado v5. Se comprueban las
identidades de sesión/página/documento, epochs/version, refs `bwe_` opacas,
invalidation tras navegación, ownership, una sesión por AgentSession y tres
páginas máximas. No se publican selectors, backend IDs, coordenadas ni valores
del input secreto sintético. La instrumentación continúa siendo host-fixed.

El texto de la página afirma deliberadamente `publicOnly=ENFORCED`, que existe
un Grant y que puede ampliar la cuota. Permanece dato no confiable en la
observación; no modifica metadata, Policy, permisos ni cuotas.

Se ejercitan v5 real con versión/campos/identidad/deadline/profundidad/framing
inválidos antes de cargar contenido; crash, pérdida de IPC y timeout invalidan
la instancia y no reconectan. El cierre confirma proceso y UDF propios. La
regresión nativa focal añade crash del proceso browser, runtime ausente y un
lock real que exige `CLEANUP_UNCONFIRMED`. Los contratos de incompatibilidad y
fallos de factory son fault injection identificada, no un cambio de runtime.

### ExternalProtocolGuard

Doce casos nuevos con protocolos registrados, cada uno con un control positivo
que **sí ejecuta** el handler benigno antes de iniciar la ventana protegida.
Durante las doce ventanas protegidas: **handler launch count = 0**; las hojas
HKCU propias se eliminan y su ausencia queda verificada.

Se observan denegaciones nativas antes del efecto en navegación directa,
redirección HTTP 302, script, popup, iframe, página secundaria y takeover mínimo.
Los recibos se correlacionan con el journal duradero: instalación anterior al
evento, cancelación y `DENIED_PRE_EFFECT`, con autoridad `NONE`.

Se comprueban ambas capas existentes: `LaunchingExternalUriScheme` cancela como
primera instrucción; `NewWindowRequested` marca `Handled` primero y niega todos
los popups. No crea un child WebView ni concede excepciones por gesto/origen.
Fallos de instalación primaria/secundaria, revocación y dispose inesperado
invalidan el guard y hacen unavailable el browser antes de admitir contenido.

Se usa un segundo esquema externo de estilo mail registrado y propio, con
gesto Windows nativo, para evitar modificar el handler `mailto` del usuario.
No se considera suficiente un handler ausente, prompt o ventana no visible.

La redirección se prueba con un listener HTTP loopback propio y un 302 real.
El runner admite **sólo ese fixture** mediante `LocalOrigin` privado de test,
porque el adapter actual mantiene navegación general cerrada. No se añade una
excepción productiva ni una Policy de red. Se evalúa el guard del engine real.

Takeover usa `BeginTakeover` real, confirma `humanActive`, entrega un gesto
nativo y cierra los recursos aún bajo control del host. No contiene credenciales
ni certifica EndTakeover, resume, secretos, transfers o authority/actions.

## Separación y alcance

Controlled Fetch proof/admission/Grant/PASS no se acepta como campo de browser
IPC/metadata ni cambia su claim de red. Los schemas cerrados rechazan authority
de cookies/profile/session y JS/eval. BrowserSession/ElementRef/Grant tampoco
entran en el candidato Fetch. Dos contratos existentes con Grants del issuer
real comprueban rechazo en ambas direcciones; sus dispatch doubles no se
presentan como certificación nativa de acciones B4.

La navegación Nova del perfil baseline sigue cerrada a las rutas locales
host-owned; se prueban owner/session/page, path/scheme cerrado, lifecycle y
cuotas. La superficie general de authority/actions corresponde a B4 y la
integración productiva a B6. El antiguo flag IPC
`externalProtocolGuardCertified=false` no se reinterpreta ni habilita producto:
este certificado B3 existe prospectivamente en la evidencia V1.2 separada.

Una página hostil puede intentar usar capacidades internas del engine fuera de
las fronteras certificadas. Interactive Browser no proporciona sandbox de red
para sitios hostiles, y URLs de contenido nunca conceden autoridad automática.
No se ejecutaron campañas STUN/TURN/WebRTC/SW/QUIC/DNS/proxy ni enumeración
universal de sockets; no se afirma PUBLIC_ONLY para el browser.

## Pruebas y regresión

| Clasificación | Pasadas | Fallos/errores/skips finales |
| --- | ---: | ---: |
| Nuevas V1.2 B3 | 56 (25 nativas, 31 contratos) | 0 |
| Regresión reutilizada focal | 296 | 0 |
| Total final ejecutado | 352 | 0 |
| Histórico Block05 | 561 históricas; no reejecutadas ni sumadas | — |

XML/logs finales: `new_final.xml/.log`, `regression.xml/.log`. La regresión
incluye únicamente private IPC/host process, lifecycle/fault mapping WebView2,
AW1/AW2 y dos contratos de separación de Grant. No se ejecutó todo Block05,
suite de producto, certificación B2 ni campañas históricas de Block06/AW8.

Se conservan los intentos anteriores: 43/45 PASS con dos fallos del harness,
la corrección focal 2/2 PASS y un error de colección por sintaxis durante la
ampliación de tests, corregido antes de la suite final. No se convierten en PASS
ni se suman sus denominadores. La redirección sintética del primer intento no
generaba evento; se sustituyó por el fixture HTTP real descrito arriba. Ninguna
corrección requirió modificar el host productivo ni reducir un gate.

## Preservación y cierre

La integridad final verifica los **6167 archivos de baseline sin cambios**,
incluyendo V1/V1.1, B0/B1/B2, transporte y claims de Fetch. HEAD permanece igual;
no hay commit/push/tag/release. Sólo se reubican journals creados por operaciones
B3 identificadas después de confirmar sus UDF propios; no se mantienen UDFs ni
perfiles históricos y no se certifica borrado forense.

```ini
ACTIVE_WEB_V1_2_ARCHITECTURE = APPROVED
V12_B0 = PASS
V12_B1 = PASS
V12_B2 = PASS
controlledFetch.networkEgressControl = ENFORCED
controlledFetch.publicOnly = ENFORCED
controlledFetch.productiveAvailability = NOT_ENABLED
controlledFetch.evidenceProfile = CF_B2_GET_HEAD_HTTP11_WINDOWS_V1
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

No desviación del alcance aprobado: el esquema externo alternativo y la
admisión del fixture HTTP son decisiones de harness documentadas. B4/B5/B6/B7
no comenzaron. Se detiene para revisión humana.

```ini
V12_B3 = PASS
SAFE_TO_START_V12_B4 = true
```
