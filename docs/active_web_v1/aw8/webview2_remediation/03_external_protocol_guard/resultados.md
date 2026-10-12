# Active Web V1.1 — §35.2 bloque 03: ExternalProtocolGuard

`WEBVIEW2_REMEDIATION_BLOCK_03 = PASS`

`EXTERNAL_PROTOCOL_GUARD = PASS`

`HOST_PRE_EFFECT_DENY = PASS`

`SAFE_TO_ADVANCE_TO_BLOCK_04 = true`

Estos resultados son **evidencia engine-specific de este bloque**, no disponibilidad productiva de Active Web, certificación de red ni AW8 E2E. Se detiene aquí para revisión humana.

## 1. Baseline y preflight

Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`, sin cambio. Working tree previamente dirty: 18 modificaciones tracked y trabajo Active Web/native untracked heredado; conservado. Staging vacío; cinco tags anteriores intactos. No commit/push/tag/release.

Se comprobaron los pins completos aplicables del bloque 02 antes de modificar: drift 0. El freeze de este bloque registra 2380 archivos previos y 144 archivos históricos/arquitectónicos. La comprobación final conserva las dos arquitecturas, AW0–AW8 y las evidencias de remediaciones/bloques01–02 byte-intactas. No se reescriben ni recalifican sus manifests.

Normativa aplicada: V1.1 **§18.6**, **§26.3**, **§35.2 bloque3**, **§36.6–7**, **AW-INV-051–053**. §18.6 permite denegar popups: se elige **DENY_ALL**, no creación de nuevos controles autónomos. §35.2 reserva observations/actions al bloque4, takeover completo al bloque5 y red al bloque6. No se anticipan esas capabilities.

## 2. Implementación y reutilización

Ruta mínima existente conservada: Python BrowserPort → adapter Infrastructure → Named Pipe privado/PID-bound → mismo `nova-browser-host` .NET → WebView2 real. Se reutilizan ACL/ownership del pipe, framing, deadlines, Job Object de lifecycle, STA/UI thread, sesiones/páginas opacas, cuotas, UDF y cleanup del bloque02. No se importa SDK/COM desde Core/Application ni se cambia Policy/Approval/Grant.

SDK oficial fijado **Microsoft.Web.WebView2 1.0.4258.31**, .NET SDK **10.0.203**, `net10.0-windows`, x64. Runtime observado **154.0.4258.62**. Build final: 0 warnings/0 errors; mensaje informativo del SDK sobre comprobación de workloads preservado, sin actualización de workloads. Restore sólo desde el paquete oficial ya instalado en el feed local del bloque02; no descarga/instalación de Runtime ni configuración global nueva.

### Guard y orden

Cada controller creado sigue en `about:blank` cuando se suscriben `LaunchingExternalUriScheme` y `NewWindowRequested`. Sólo después de instalarlos se registra la Page como utilizable. El único contenido de prueba se carga desde el executable de certificación, después de verificar el registro y correlación. No existe comando de contenido/script en el IPC productivo.

`LaunchingExternalUriScheme` ejecuta **`e.Cancel = true` como primera instrucción**, sin deferral, espera Python, decisión por gesture/origin, Policy ni Approval. Posteriormente sanea metadata y escribe audit. No ShellExecute/Process.Start/relaunch/allow exception en producto. `NewWindowRequested` ejecuta `e.Handled = true` primero: ningún popup autónomo, browser predeterminado ni nuevo control.

Una retirada inesperada del guard invalida y cierra controles antes de desuscribirlo. La retirada normal sólo sucede después de `controller.Close()`. Fault de instalación: no Page utilizable, controller cerrado y recursos engine observados para poder confirmar cleanup. Las nuevas pruebas inyectan fallos únicamente mediante factories/sinks internos del executable de tests; producto/IPC no aceptan flags para perder, desactivar o permitir el guard.

Microsoft documenta la cancelación del evento antes de lanzar el protocolo y su efecto sobre el diálogo default; el probe nativo, no la mera existencia de la API, aporta la evidencia de este bloque. [LaunchingExternalUriScheme](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.launchingexternalurischeme?view=webview2-dotnet-1.0.4258.31), [event args / Cancel](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2launchingexternalurischemeeventargs?view=webview2-1.0.4191.47).

### Audit/receipt

Se escribe un registro durable **SecurityAuditRecord v1 válido** sin modificar DATA_KEYS: `kind=policy`, `origin=application`, `tool=ExternalProtocolGuard`, `outcome=DENIED_PRE_EFFECT`, `effectState=none`. `observationScope` contiene sesión, página, host instance, incarnation=1, secuencias de instalación/evento, scheme saneado, initiating origin saneado si existe y gesture observado. Los IDs de operación son explícitamente observaciones host-owned; ToolCallId/TurnId/AgentId son null y no se inventan Grant/Approval/intención del usuario.

No se persiste la URI completa: sólo scheme; el origin HTTP(S) se limita a scheme y digest de hostname/port; otras representaciones se omiten. FileStream CreateNew + WriteThrough + Flush(true) antes de publicar receipt durable. El archivo administrado por Infrastructure se conserva fuera del UDF efímero, no es transcript ni evento de sesión presentado como Security Audit. Es evidencia durable del guard, no auditoría inventada de una tool invocation.

Audit failure tras Cancel: receipt `durable=false`, `recordId=null`, audit gap y cierre/inutilización de sesión; el intento sigue DENIED_PRE_EFFECT. Ningún fallo de audit se transforma en allow. Se valida la serialización C# leyendo los registros reales con `SecurityAuditRecord.from_dict` Python.

### IPC aditivo

Se agrega una extensión cerrada **v3**, con sólo `guard_metadata` de lectura además del lifecycle ya existente. v1/v2 codecs conservan sus contratos. v3 transporta errores tipados GUARD_UNAVAILABLE/GUARD_AUDIT_FAILED y metadata/receipts acotados; no URI, scripts, selectors, authority, grants ni relaunch. No comando público de navegación, acciones, pérdida del handler o takeover. El adapter sólo aporta evidencia Infrastructure; no es capability snapshot v2 ni composition root de tools nuevas.

## 3. Prueba nativa y canary reversible

Matriz prospectiva congelada antes de la primera medición: `certification_plan.json`. Regresión adicional de disposición inesperada congelada antes de medirla: `supplemental_contract_plan.json`; no se modifica el plan anterior ni sus resultados.

12 canaries finales únicos bajo **HKCU/Software/Classes/nova-aw8-guard-<uuid>**, exclusivamente harness. Nombre sin colisión, registro por usuario y helper benigno cuyo primer efecto funcional es escribir PID en sentinel. Se registra explícitamente default/URL Protocol/shell/open/command; las rutas/commands machine-local quedan en raw externo privado, no se envían al modelo ni se registran como producto.

Cada asociación tiene un **control positivo de Windows antes de la ventana medida**: helper ejecutado y PID/sentinel preservados separadamente. Así se demuestra un handler registrado funcional, no un protocolo inexistente. Durante las ventanas del guard: **0 ejecuciones del helper, sentinel ausente en 12/12**. Cleanup de registro: **12/12**, claves finales ausentes. No se tocan handlers del usuario, CA, políticas globales ni admin. La autorización específica de este usuario habilita este registro de certificación; no deriva de la arquitectura sola.

Casos observados:

| Caso | Resultado nativo / clasificación |
|---|---|
| Script → custom registrado | Evento observado, Cancel=true, denial durable, helper=0 |
| Click nativo → custom registrado | Evento observado, userGesture=true, Cancel=true, helper=0 |
| mailto | Evento LaunchingExternalUriScheme observado y Cancel=true; no modificación del handler mail del usuario |
| iframe/child frame con click | Evento observado y userGesture=true; guard del control owner cancela |
| Popup/new window | NewWindowRequested observado, Handled=true, POPUP_DENIED_PRE_EFFECT; no control nuevo ni default browser |
| Segundo control/página | Ambos PageRefs guardados previamente; dos receipts de fuentes distintas, helper=0 |
| Interacción visible equivalente a takeover | Controller real visible, gesto WM nativo, evento userGesture=true y Cancel=true; guard incondicional intacto |
| Sink de audit fallido | Intento real cancelado antes del fallo inyectado; auditGap/UNKNOWN/no receipt durable |
| Registro fallido / segundo control fallido | Fault factory explícito: no página utilizable; UNKNOWN; cleanup confirmado |
| Pérdida/revoke / Dispose inesperado | Session/control invalidados antes de unsubscribe; UNKNOWN; cleanup confirmado |
| Host crash / IPC disconnect | Sin retry/fallback, handles inutilizables y cleanup real, misma ruta privada |

Los casos de fault injection son contratos, no claims de que un bug arbitrario del SDK fue inducido naturalmente. La interacción visible/native gesture demuestra que el guard no se suspende por interacción humana; **no certifica la integración Application de takeover**, reservada al bloque5. No se presenta JavaScript `.click()` como user gesture ni se implementa automation/action de producción para estos tests.

Hay **9 receipts nativos**: 8 durables (incluyendo popup) y 1 gap deliberado tras cancelación. Popup denial se distingue del evento de external protocol. No se cuenta error NavigationCompleted, diálogo o engine-internal denial como guard PASS. Este corpus no usa solicitudes suprimidas internamente para cubrir el requisito; child-frame seleccionado emite efectivamente el evento. `ENGINE_INTERNAL_DENIAL` queda categoría distinta, no evidencia del handler.

La estrategia no crea popups, por lo que no existe una ruta de popup-controller creation que deba permitirse/recuperarse; se demuestra rechazo antes de creación/default handling. La creación fallida de un controller secundario cubre el caso donde no puede instalarse el guard.

## 4. Tests y regresión

Comandos exactos, runtime, tiempos, denominadores, XML/hashes, listas de skips, casos y outputs externos: **`test_results.json`**. Plugin autoload deshabilitado, basetemp/build/feed/output fuera del checkout, sin nuevas exclusiones/skips/xfails ni quality retries. No AW8 E2E/model inference/public Internet.

| Suite | Resultado |
|---|---|
| Host completo final | **185 PASS**, 0 FAIL/ERROR/SKIP, exit0, 61.543 s JUnit |
| Active Web heredada | **672 PASS**, exit0 |
| Security | **615 PASS**, exit0 |
| MEMORY | **791 PASS**, exit0 |
| Knowledge | **1015 PASS**, exit0 |
| Desktop | **71 PASS**, 0 FAIL/SKIP, exit0 |
| TypeScript | `tsc --noEmit`, exit0 |
| Core amplio | **3410 PASS, 2 FAIL, 7 skips históricos, 53 subtests PASS adicionales**, exit1 |
| Diagnóstico aislado JSONL sin modificar test | **1 PASS**, exit0; no reemplaza corrida Core |

185 se descompone en 156 contratos heredados del host/bloques01–02 y 29 nuevos: **18 EXTERNAL_PROTOCOL_GUARD_CONTRACT_TEST**, **11 EXTERNAL_PROTOCOL_GUARD_NATIVE_TEST** (8 caminos de lanzamiento/fault de audit real, 1 IPC/metadata del host real y 2 pérdidas host/IPC). La matriz canary incluye también los fault contracts con engine real y fallo sintético expresamente identificado.

XML final: `C:/Users/joseh/AppData/Local/Temp/nova-wv2-03-final.xml`.

SHA-256: `f14a0eea2d956bd98ee6513bd64c60c3f58a45b427269061423ce0528c34d050`.

### Fallos preservados, no ocultados

1. Primera corrida focused: **27 PASS / 1 FAIL**, PRODUCT_BUG: captura de procesos demasiado tarde ante instalación fallida → cleanup intentado antes de exit. Se corrigió exclusivamente observando procesos inmediatamente tras crear controller; XML/raw conservados. Corrida siguiente **184 PASS**. Revisión estática posterior añadió invalidación previa en Dispose inesperado y su regresión; corrida final **185 PASS**. No se alteraron assertions para aceptar el defecto. El UDF de esa corrida fallida permanece fuera del repositorio como estado histórico aislado de CLEANUP_UNCONFIRMED, sin engine vivo ni canary registrado; **no se reporta su cleanup fallido como PASS**. Todos los cleanups de la configuración final sí quedaron confirmados.
2. Core HOME/USERPROFILE: `TestBashToolEnvSanitization::test_non_sensitive_env_vars_available` permanece **PREEXISTING_CORE_HARNESS_DEBT / NON_BLOCKING_FOR_BLOCK_03**, test/BashTool/runner byte-intactos; exit1 conservado.
3. Core JSONL: `test_jsonl_slow_subscription_disconnects_then_reconnects_with_gap` observado por primera vez en esta corrida como **HARNESS_BUG / PREEXISTING_ASYNC_ASSERTION_RACE**. `_wait_for(event)` retorna con el primer EventGap; el test lee `sent` sin esperar el segundo SessionSnapshot, mientras el pump hace dos sends secuenciales. Archivos del test, coordinator, event stream, JSONL y providers sin cambio; fixture tool_factory vacío. Diagnóstico aislado pasó con mismo entorno privado y 0 módulos WebView2/guard cargados. No se modifica el test ni se reemplaza su FAIL de la suite completa por el diagnóstico. Clasificación causal sustentada en código/identidad/ruta, no en que un rerun simplemente estuviera verde.

Los siete skips de Core coinciden con bloque02; no se agregan skips/xfails/filtros. No se suman suites solapadas como un denominador HEAD único ni se afirma que Core quedó verde. La regresión demuestra ausencia de cambios causales materiales del guard en las rutas heredadas, no eliminación de deuda ajena.

## 5. Criterio por criterio

| Gate | Estado | Evidencia |
|---|---|---|
| GUARD_INSTALLATION_ORDER | PASS | Suscripción antes de Page READY; installed sequence antes de evento y Load; factories fallidas nunca publican Page usable |
| REGISTERED_PROTOCOL_PRE_EFFECT_DENIAL | PASS | Protocolos canary registrados funcionales, callback nativo, Cancel=true, 0 helper/sentinel durante medición; mailto observado |
| SECONDARY_CONTROL_AND_POPUP_GUARD | PASS | Dos controles propios guardados; popup Handled=true antes de metadata, no control/default browser; fallo secundario fail-closed |
| TAKEOVER_GUARD | PASS | Gesto nativo en controller visible: guard instalado/incondicional, sin allow/dialog/relaunch; no se certifica takeover completo futuro |
| GUARD_AUDIT_AND_FAULT_PATHS | PASS | Registros C# durables validados contra SecurityAuditRecord Python; pérdida/registro/audit/host/IPC y cleanup; sin IDs de autoridad inventados |

No se observó una vía concreta browser/page→host application que produzca efecto antes del guard en esta composición congelada. La evidencia se limita a SDK/runtime/configuración/canales probados, no afirma aislamiento host ni una propiedad universal de todas las versiones WebView2.

## 6. Integridad, alcance y próximos bloques

Sólo tres archivos existentes cambiaron: `WebView2Runtime.cs` (instalación/lifecycle), `LifecycleServer.cs` (wire3 observabilidad), `webview2_adapter.py` (hook Infrastructure de client type). Nuevos: `ExternalProtocolGuard.cs`, `GuardProtocol.cs`, `guard_ipc.py`, `guard_adapter.py`, runner/tests específicos y evidencia aditiva. Lista completa y pins finales en manifest/integrity/product_freeze_final.

Architectures V1/V1.1 y 144 artefactos históricos sin drift. Core/Security/Memory/Knowledge/Desktop/CI/Playwright no modificados. No capacidades nuevas al modelo, fallback Playwright, política de excepción o relaunch. No bridge WebMessage/host objects, prompts ni datos no confiables públicos.

Estado final:

```text
externalProtocolGuard = KNOWN / HOST_PRE_EFFECT_DENY (sólo evidencia de este bloque)
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

No se implementa snapshot v2 productivo (bloque7), nueva integración de tools (bloque8), observations/actions (bloque4), transfers/takeover completo (bloque5), recertificación de red (bloque6) ni AW8 final. AW-INV-052/053 conservan las fronteras y sus pruebas independientes. `SAFE_TO_ADVANCE_TO_BLOCK_04=true` es sólo resultado para autorización humana posterior; **no se avanza automáticamente**.

OPEN DECISION normativa: ninguna nueva requerida para este bloque. Deuda heredada/Core y limitaciones anteriores quedan explícitas; no se recertifica ni reinterpreta el pasado.
