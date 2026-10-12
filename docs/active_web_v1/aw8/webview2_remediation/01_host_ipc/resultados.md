# Active Web V1.1 — §35.2 bloque 01: browser-host e IPC privado

`WEBVIEW2_REMEDIATION_BLOCK_01 = PASS`

`BROWSER_HOST_CONTRACT = PASS`
`PRIVATE_IPC = PASS`
`HOST_LIFECYCLE = PASS`
`SAFE_TO_ADVANCE_TO_BLOCK_02 = true` (requiere autorización humana; no se ejecutó).

Este resultado certifica exclusivamente el contrato/skeleton IPC Windows. No certifica WebView2, navegación, red ni Active Web. Permanecen `AW8 = BLOCKED`, `ACTIVE_WEB_CORE = NOT_READY`, `available = UNKNOWN` y `publicOnly = UNKNOWN`. Host IPC READY **no** es BrowserSession activa ni capability Active Web.

## 1. Preflight y reutilización

Branch `main`, HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`. Working tree previo no limpio: 18 modificaciones tracked y archivos untracked de Active Web anteriores. Se preserva el listado completo y los SHA de los **2341 archivos heredados** en `baseline_freeze.json`; ningún archivo existente fue editado. El conjunto histórico Active Web/arquitecturas comprende 116 archivos y conserva sus bytes, incluidos V1, V1.1, AW0–AW8, prerequisite remediations, egress closure y architecture review. Tags anteriores y staging permanecen intactos.

La norma es V1.1 §6.3 y §35.2 fila 1: «owner/session correlation, mensajes acotados/versionados, errores, cancel/disconnect sin segundo AgentLoop/authority». Se reutilizan los formatos opacos `bws_`/`bwp_` existentes. BrowserPort, BrowserSession, Application, ToolRuntime, Policy, Approval, Grant, frontends, Memory y Knowledge **no se modifican**. No existía el proceso/contrato privado .NET necesario; el adapter Playwright histórico no se reutiliza como motor certificado.

Baseline pertinente antes de cambios: Active Web ordinary contracts, **672 PASS**, exit 0. La deuda Core HOME/USERPROFILE ya está demostrada antes de este bloque en AW0 closure/AW7/revision 02 y permanece FAIL.

## 2. Implementación exclusiva

- Python Infrastructure: codec cerrado, transporte Win32 Named Pipe y `BrowserHostClient` con lifecycle, errores tipados y presupuestos. No implementa BrowserPort funcional, no registra tools y no se importa desde Core/Application.
- Proyecto separado `native/nova-browser-host`: C#/.NET 10, sin PackageReference, SDK WebView2, navegador ni contenido web. Arranca, recibe handshake, devuelve health, cancellation receipt y shutdown ordenado.
- Protocolo propio versión 1: uint32 little-endian + JSON UTF-8 estricto; 16 KiB frame, 4 KiB payload, profundidad 8, máximo 4096 requests/host, deadlines de hasta 30 s. Rechaza mensajes/campos/comandos/resultados desconocidos, duplicados JSON, versiones incompatibles y correlación inválida.
- Envelope cerrado con schemaVersion, messageType, requestId, browserSessionRef, pageRef, operationId, deadline, payload, result y error. Request/response/event/cancel/protocol_error; handshake y shutdown son operaciones tipadas. `reserved_browser` siempre responde UNSUPPORTED_COMMAND, sin payload de navegación ni efecto.
- Launch explícito del ejecutable/assembly absolutos; shell=false, sin handles heredados, stdio DEVNULL, entorno mínimo sin credenciales del provider. Los paths son composición host confiable, nunca input del modelo.
- Pipe local de una instancia, FIRST_PIPE_INSTANCE y REJECT_REMOTE_CLIENTS. DACL protegida: NETWORK denied y sólo TokenUser actual allowed. Python comprueba server PID del child creado; C# comprueba client PID del owner original. Handshake liga host identity/instance/session y procesos reales; el host mantiene handle al owner original y termina cuando éste sale.
- Respuestas nunca contienen autoridad/grants/Approval tokens/passwords/cookies/secrets. El receipt sólo declara las features IPC ping/cancel/shutdown y `activeWebAvailable=false`; ese dato **no alimenta** capability discovery productiva. UNKNOWN de producto permanece UNKNOWN.

Los PID de extremos se comprueban con APIs Windows reales ([client PID](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid), [server PID](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeserverprocessid)); la evidencia nativa verifica además DACL/ACEs efectivos y rechazo de un proceso no-owner, no sólo strings o mocks.

## 3. Lifecycle, cancelación y límites del claim

Flujo normal: NOT_STARTED → STARTING → READY → STOPPING → STOPPED. Errores → FAILED; cleanup no confirmado → CLEANUP_UNCONFIRMED. Se distinguen nunca iniciado, start fallido, mismatch/handshake, transport disconnect, process exit/crash, timeout y cancelación local. Shutdown sólo es exitoso con response/event correlacionados **y exit 0 observado**; cerrar un canal fallido no lo recalifica como éxito.

Un presupuesto monotónico cubre lock wait, conexión y todos los fragmentos IO; no se acepta una respuesta tardía. La IO overlapped pendiente se cancela y drena antes de liberar buffers. Cleanup tiene esperas separadas de terminate/kill de 2 s cada una; no se presenta el presupuesto IPC como deadline wall-clock total de efectos browser futuros. No hay reconexión/reenvío automático de una request transmitida.

Health es síncrono: un cancel wire de una operación ya completada devuelve ALREADY_COMPLETED, **no rollback**. La cancelación Event durante startup/IO invalida el canal y recoge el proceso. Cancelación/STARTED/outcomes de futuras operaciones browser no están implementados ni certificados.

ACL/PID/ownership son controles locales bajo **HOST_UNISOLATED**, no sandbox. No se promete protección frente a administrador/debugger/inyección de proceso o sustitución de runtime/assemblies confiables. No se aloja contenido web ni se expone IPC a páginas.

## 4. Criterios de cierre y trazabilidad

| Requisito del bloque 01 | Componente y evidencia | Estado |
|---|---|---|
| Contrato versionado, cerrado y acotado; request/result/error/events | protocol.json; codecs Python/C#; malformed/oversize/unknown/extra-field/version tests | PASS |
| Handshake host/process/session/protocol | BrowserHostClient + Program/NativePipe; success, identity mismatch, wrong session/PID/instance | PASS |
| Ownership único y private pipe | DACL binaria, PID nativo, second client y unauthorized first client, owner death | PASS |
| Python/C# serialization compatible | handshake/health/shutdown reales y casos negativos nativos | PASS |
| Deadline, timeout, cancel; ningún late result/retry | monotonic transport/client, native pending IO y late-reply contract | PASS |
| Duplicate requestId/correlation rechazados | seen IDs/operations + correlación completa; tests nativos y contrato | PASS |
| Lifecycle y cleanup reales | start/never-started/disconnect/crash/clean shutdown/owner exit; 0 hosts restantes | PASS |
| Sin autoridad en host / sin nuevo AgentLoop | campos cerrados, host puro Infrastructure; core/application/roots byte-intactos | PASS |
| Sin capability browser derivada de IPC | handshake sólo IPC; test existing application capability closed; roots intactos | PASS |
| Sin bloque 02 ni fases posteriores | sin WebView2 SDK/content/DOM/tools/adapter/probe/E2E | PASS |
| Regresión sin cambios nuevos materiales | jobs ordinarios existentes + hash total, deuda Core separada | PASS con deuda heredada explícita |

Invariantes aplicables preservados: AW-INV-001/002 (autoridad/ToolRuntime intactos), 003/004 (no segunda capability ni datos→autoridad), 007/008/027/029 (disponibilidad no habilitada ni fallback), 013/014/017/035 (sin credenciales/JS/selectores), 031/032/033 (sin retry ni éxito/rollback ficticio), 047/048 (cleanup observado y no sandbox), 049/050 (frontends/históricos intactos). AW-INV-051/052 y recertificación de red/guard siguen **pendientes de bloques posteriores**, no se declaran probados por IPC.

## 5. Tests y regresión

Host: Windows 11 Pro 10.0.26200 x64, volumen C: NTFS; .NET SDK 10.0.203 / runtime Microsoft.NETCore.App 10.0.7; Python 3.14.6, pytest 9.1.1. El host se compiló offline con feed vacío, obj/bin/perfiles/TEMP externos y 0 warnings/errors. No instalación de paquetes/modelos/SDK/workloads ni configuración global.

| Ejecución válida final | Resultado | Exit |
|---|---|---|
| IPC_CONTRACT_TEST | 55 PASS / 0 FAIL / 0 ERROR / 0 SKIP | 0 |
| HOST_PROCESS_TEST (.NET y pipes nativos reales) | 51 PASS / 0 FAIL / 0 ERROR / 0 SKIP | 0 |
| Active Web ordinary regression | 672 PASS | 0 |
| Security ordinary regression | 615 PASS | 0 |
| Memory ordinary regression | 791 PASS | 0 |
| Knowledge ordinary regression | 1015 PASS | 0 |
| Core ordinary regression | 3411 PASS / 1 FAIL / 0 ERROR / 7 SKIP; 53 subtests PASS | 1 |

Focused combinado: **106/106**, 24.487 s. XML raw:
`C:/Users/joseh/AppData/Local/Temp/nova-host-ipc-01-focused-attempt05-20261010.xml`.
Copia aditiva en `evidence/focused.xml`, con newline final archivístico; se conservan SHA raw y archivado diferenciados. `test_results.json` preserva los 106 IDs/clasificación/tiempos, todas las corridas intermedias, commands/receipts, hashes XML/logs/selección y artifacts .NET externos.

Los jobs heredados usan **la selección positiva vigente y su collection guard sin editar CI**: no equivalen a todos los tests posibles de HEAD ni a campañas native browser/LLM. Los 7 skips Core son exactamente los históricos de la misma selección (3 symlinks, 2 POSIX mode, 2 legacy monitor). No nuevos skips/xfail/exclusiones. Los 53 subtests hacen que el atributo JUnit tests=3472 sea mayor que los 3419 casos base; denominadores no se suman entre jobs solapados. Desktop no se reejecutó: fuentes/CI/tests/evidencia heredada intactos, sin claim de nueva certificación Desktop.

Los tests nuevos viven explícitamente en el proyecto native, fuera del inventario CI histórico; **no** se anuncia su ejecución automática en Actions. Outputs, runtime y build state quedan fuera del working tree Git.

## 6. Fallos preservados y clasificación

- Dos primeras corridas host: 46 ERROR de setup cada una, ENVIRONMENT (TEMP/TMP ausentes; luego perfiles NuGet ausentes). Se corrigió sólo el fixture nuevo, con carpetas privadas externas; ningún test body host había ejecutado.
- Corrida focused anterior: 105 PASS / 1 FAIL, HARNESS_BUG del oracle nuevo SDDL GA vs acceso efectivo FILE_ALL_ACCESS. Se reemplazó por validación binaria **más fuerte** de protected DACL, exactamente dos ACEs, SID y máscaras; producto .NET/ACL sin cambio. XML previo permanece externo e inmutable; no se publica su SID local en el repo.
- Primeras regresiones con Python base sin dependencias completas: Knowledge 21 ERROR de collection, Memory 786 PASS/5 FAIL por numpy ausente, Security 614 PASS/1 FAIL de subprocess sin pytest, Core 3410 PASS/2 FAIL (Knowledge event por pypdf ausente + deuda HOME). ENVIRONMENT. Se reutilizó el venv histórico ya instalado, sin cambiar producto, runner, assertion, selección ni paquetes. Corridas inválidas quedan preservadas, no se cuentan como PASS.
- Único FAIL válido final: `tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`. **PREEXISTING_CORE_HARNESS_DEBT / NON_BLOCKING_FOR_BLOCK_01**, no PRODUCT_BUG nuevo. HOME privado ≠ USERPROFILE y PowerShell $HOME usa USERPROFILE. Históricos AW0 closure/AW7/revision 02 y hashes de test/BashTool/shell/runner demuestran ausencia de cambio causal. No se repara, oculta, filtra ni llama PASS.

La conclusión del bloque es ausencia de regresiones **introducidas por este skeleton**, no un claim de Core globalmente verde.

## 7. Integridad y trabajo posterior

`integrity.json` compara los 2341 archivos anteriores y los 116 históricos: drift=0. Incluye pins del delta autorizado, hashes raw/external, tags y staging sin cambios. V1 y V1.1 conservan SHA respectivos `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e` y `46ec3201460ba37a6fe47f6cf94e80f0024ec442c9323115a0cf19d64de95e1d`.

Pendiente, no implementado: adapter WebView2/UDF/runtime (bloque 2), ExternalProtocolGuard, observations/refs/actions, transfers/takeover, red y broker, discovery v2, composición browser/tools, prerrequisitos y AW8 E2E. No decisión normativa abierta necesaria para cerrar el IPC health de este bloque. Packaging/SDK/versiones de WebView2 y semántica wire de efectos futuros deben resolverse en sus bloques, no anticiparse.

No commit, push, tag ni release. Se detiene para revisión humana.
