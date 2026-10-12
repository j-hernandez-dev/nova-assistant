# Campaña diagnóstica no reparadora — C04

Sólo WV2-B05-C03-TAKEOVER-CONTINUITY-004. Los 75 pins del candidato continuation_03 se preservan, igual que sus resultados 30/3 y la política TRANSIENT/COMMITTED.
Primera ejecución: los tres node IDs fallidos, una vez cada uno, en orden autorizado. No retries.
Sólo tras localizar suficientemente la causa se permiten controles PASS cercanos: same-origin directo y cross-origin directo, una vez cada uno. No suite completa, policy campaign, bloque06 ni AW8.

## Método
Un pytest plugin nuevo envuelve únicamente los build fixtures. Delega al build original, luego compila copias temporales de los mismos fuentes con taps de metadata y sustituye el executable **del harness**. No cambia ninguno de los fuentes productivos, fixtures, HTML, drivers, secuencias, assertions o mensajes Named Pipe.
Los dos tipos de caso conservan sus mains respectivos (normal y outer diagnostic wrapper), LifecycleServer, private IPC/ownership, WebView2/runtime/guard reales.
Estas builds son DIAGNOSTIC_TEST_HOST_NOT_PRODUCT: NO evidencia de certificación positiva del candidato.

En la copia temporal de SensitiveTracking:
- una binding CDP adicional, sólo en el world privado, transmite event kind/control id/length, NO valores;
- se anota inmediatamente antes de la llamada a la binding productiva; payload/schema productivo sigue igual;
- se registran world creation/destruction/clear, live/protected identity, checkpoint selection/invoke/ack;
- no WebMessage, host objects, selector/model JS, autoridad ni puente de página.
En la copia del registry:
- taps registran longitud/clase/exact-known/current/previous-current length, commit reason y primer failure enum;
- Add/Input/Commit/Require/Retire/Checkpoint/Dispose siguen la misma lógica, bounds y error externo;
- no hashes/prefixes/valores ni contenido del registry se persisten.
Takeover sólo recibe marcas begin/completed; Main sólo inicializa el sink local host-owned.

## Metadata y límites
Sink local del harness: suffix .continuity-metadata.jsonl junto al UDF de test, owner/process scoped.
Refs de control/page/frame/world se traducen a IDs opacos locales, no IDs DOM ni secretos.
Sequence estrictamente creciente, monotonic ticks, host/owner PID, session/host alias; no timestamps basados en páginas.
Límite 8192 registros por proceso; overflow/delivery gap invalida evidencia diagnóstica, nunca relaja producto.
No exception message/stack con URL/DOM/secret, no public IPC/debug fields.
Copias generadas y assemblies guardan source hashes y transformación exacta para integridad (hashes de código, NO de secretos).

Los taps realizan I/O local y añaden un evento CDP de metadata: pueden perturbar timing.
Se documentará esa limitación; una no-reproducción no se convertirá en PASS histórico ni se usará como calidad.
Preflight de anchors y compilación pasó sin iniciar host/tests; no fue reejecución de caso.

## Análisis
Distinguir COMMITTED_SHORT_VALUE, CHECKPOINT_CONTINUITY_FAILURE, CAPTURE_CHANNEL_FAILURE, REGISTRY_BOUND_EXPIRY, EVENT_ORDERING_OR_LATE_CAPTURE, OTHER.
Identificar la promoción del current pending real vs historical buffers y cualquier regresión de current por late event; no heuristic rebind.
Si las cuatro condiciones requeridas no son PASS, DIAGNOSIS=INCONCLUSIVE. Incluso DIAGNOSED sólo permite propuesta de fix para revisión, nunca reparación automática.

networkEgressControl/publicOnly/available=UNKNOWN; AW8=BLOCKED; ACTIVE_WEB_CORE=NOT_READY.
36 UDF históricos sin mantenimiento; sin commit/push/tag/release.

