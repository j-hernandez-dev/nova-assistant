# Reconciliación compartida — continuation_02

Decisión humana: resolver `WV2-B05-REV02-ASSERTION-SCOPE-002`.
Alcance: únicamente proof de fixture en `check(d)` y helpers de test asociados.
Producto, redactor, registry, driver, HTML, valores, secuencias, no-exposure
assertions, Policy y schemas permanecen intactos.

## Registro antes de editar

SHA anterior de `test_sensitive_continuity.py`:
`cb64741c19fb85334de03d22bf13a903141f8fc50b9136ef8d0746408e6a8136`.

Assertion anterior:
`assert 'Safe result' in r.visible_text_summary,'The controlled reflection path must run'`.

Propósito: confirmar ejecución del actor/reflection fixture; no era una regla de
privacidad. La proyección pública puede legítimamente ocultar un leaf entero al
coincidir con un buffer sensible corto conocido. Conservar el literal en esa
projection ya no es una prueba válida de transición.

Callers directos e indirectos y los 33 IDs FAIL exactos constan en
[baseline_freeze.json](baseline_freeze.json), registrado antes de editar.
nvr21 permanece histórico: 396 total, 363 PASS, 33 FAIL, 0 ERROR, 0 SKIP,
SHA XML `0979fa3a10d1ccb64fd65e724e18d896d174cd0981c881d224c052926b73131d`.
No se reinterpreta como PASS.

## Proof actual (prospectivo, pendiente del focal)

La comprobación de privacidad en BrowserObservation permanece sin cambios.
El proof de ejecución se separa mediante:

1. snapshot previo de Session/Page, ObservationRef/version, engine epoch/version
   y browserContextEpoch por los contratos ya existentes;
2. receipt del driver humano existente, sin cambiar generación ni WM_CHAR;
3. observador **de test**, nativo .NET/UI Automation y de sólo lectura, ligado
   al HWND/PID del host ya owned. Antes del actor exige documento real y ausencia
   de señal de ejecución. Después exige que el fixture efectivamente haya
   reflejado su señal en el estado UI privado, antes de ocultar takeover;
4. evento host-owned de humanCompleted/humanActive/no-abort, seguido de
   finalización real del takeover;
5. nueva ObservationRef, versiones mayores, Session/Page correctos, context
   N+1 y relación de navigation epoch específica del escenario.

El observador privado conserva el proof semántico anterior sobre la ejecución
del fixture, **sin requerir ese contenido en la projection saneada**. Sólo emite
booleans/PID; jamás nombres, page text, raw secret ni DOM. No actúa, navega,
introduce scripts, modifica HTML o usa la pipe del producto. La lectura UI
privada no concede autoridad ni desactiva redacción. Su adquisición acotada de
estado no es retry de casos/calidad.

Same-document exige epoch igual; history-state/new-document exige epoch mayor;
frame destruction mantiene la identidad top-level y admite el avance de epoch
de frame. BACK/FORWARD exige receipts tipados de movement completado. El proof
privado debe fallar si el actor no ejecutó la reflexión; no basta crear otra
capture o incrementar artificialmente versiones.

Las assertions posteriores de origin/href/bridge/element binding y todas las
de privacidad **no se modifican**. Si aparece otro fallo tras resolver el helper,
se conserva y detiene antes de la suite completa; no se amplía autorización.

## Hashes actuales / candidato

- `native/nova-browser-host/tests/test_sensitive_disconnect_diagnostic.py`: anterior `909e9803bc7b93ab8dadbe2742abf8dafea5ecadf2a405244cd9aa7d195b9fc0`, posterior `134b0a347bf325876b98e5682061549b530fab9a5dbf0732b2f112bc9d43bd09`.
- `native/nova-browser-host/tests/test_sensitive_continuity.py`: anterior `cb64741c19fb85334de03d22bf13a903141f8fc50b9136ef8d0746408e6a8136`, posterior `8d4ff72fa703e3cecaf104714a758fcb79aea60973bdb1e80196634dde8f60ae`.

Dos archivos nuevos son exclusivamente el observador de test, enumerados en
[candidate_freeze.json](candidate_freeze.json). 72 pins de código; cero cambio de
producto. La fixture diagnóstica añade sólo el mismo observador, manteniendo
LifecycleServer/IPC real y teardown previo.

No se añade ningún test/parametrización: el inventario completo continúa en 396.
Focal obligatorio: exactamente los 33 IDs de nvr21, una vez, sin skips/xfails/
filtros/retry. Sólo un 33/33 permite la regresión completa.

## Resultado focal y parada obligatoria

El candidato congelado se ejecutó exactamente una vez contra los 33 IDs:
**28 PASS / 5 FAIL / 0 ERROR / 0 SKIP**. Cero fallos en el nuevo proof compartido;
los 33 alcanzaron assertions/operaciones posteriores y emitieron su receipt de
no-exposición. Esto **no** permite declarar el gate completo PASS: exige 33/33.

Los nuevos primeros puntos de fallo son href/origin públicos retenidos,
texto público de bridge retenido y selección de un target no publicado.
Estas assertions y acciones siguen intactas. Se detuvo antes de los 396 casos;
no hay modificación posterior ni quality retry. Los checks posteriores no
ejecutados no se heredan como PASS. [Detalle de los cinco FAIL](test_results.json).

Se conserva nvr21=363/33 como historia y nvr23=28/5 como nueva evidencia.
`SHARED_TRANSITION_HELPER_RECONCILIATION = PARTIAL`;
`SAFE_TO_ADVANCE_TO_BLOCK_06 = false`.
