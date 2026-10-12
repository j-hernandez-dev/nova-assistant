# AW8 — cierre focal de EXCLUSIVE_PUBLIC_ONLY_EGRESS

`EXCLUSIVE_PUBLIC_ONLY_EGRESS = BLOCKED`

`BLOCKER_TYPE = ARCHITECTURAL_ENFORCEMENT_LIMIT`

`PRODUCTIVE_BROWSER_TOOL_PATH = PASS`

`TRUTHFUL_ACTIVE_WEB_CAPABILITY = PASS`

`AW8_PREREQUISITES = BLOCKED`

`SAFE_TO_RESUME_AW8 = false`

Resolución aditiva. Permanecen literales el AW8 original `BLOCKED` y las revisiones 01/02 `PARTIAL`. No se ejecutó AW8 final, no hubo inferencia LLM, nueva fase, READY ni operaciones Git de publicación.

## Baseline y reconciliación

Base `main` / `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`, working tree heredado conservado y staging vacío. Windows 11 build26200, C: NTFS local, `HOST_UNISOLATED`. Python 3.14.6 mediante ejecutable absoluto del venv de validación; Playwright 1.63.0, Chromium 153.0.8010.12 revision1243.

[scope_reconciliation.md](scope_reconciliation.md) mapea individualmente obligaciones, cláusulas y evidencia. No se exige impedir JavaScript interno normal ni demostrar ausencia universal de cualquier socket en cualquier Chromium. AW-INV-030 limita **targets agentic**; el escape externo al host sí permanece obligatorio. No se reclaman sandbox, firewall total ni namespace de red.

La arquitectura conserva SHA-256 `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`. Se verificaron 2.315 pins aplicables de revision02: 2.313 sin cambios, dos deltas autorizados y reversibles exactamente a sus SHA anteriores; cero drift inesperado/missing. Los 12 artefactos históricos referenciados y los 69 outputs externos de revision02 mantienen sus hashes. Los cinco tags y el HEAD siguen iguales. No se alteran certificaciones anteriores.

## Vía concreta pendiente

`AW8-EGRESS-EXTERNAL-PROTOCOL-001`:

`renderer/button → location.href(custom scheme) → Chromium ExternalProtocolHandler → lookup de handler Windows`

Con el **adapter productivo sin modificar sus args, contexto ni broker**, una página controlada solicitó `nova-aw8-unregistered-canary:opaque`. Chromium emitió:

> Failed to launch 'nova-aw8-unregistered-canary:opaque' because the scheme does not have a registered handler.

El evento `Page.frameRequestedNavigation` confirma la URL y `scriptInitiated`. La página permanece abierta. Eso **no** es una denegación del engine: llegó al lookup del handler externo. `context.route`/canonicalización HTTP no impidieron esa ruta. Se capturaron PID/tree, command lines nativas y ventana temporal en [egress_evidence.json](egress_evidence.json).

No se lanzó una aplicación registrada, no se registró un protocolo canario y no se escribió HKCU/CA/configuración global. Por seguridad se utilizó un protocolo inexistente. No se presenta como exploit consumado ni bypass de Policy/Grant; tampoco se transforma la ausencia de handler en PASS de prevención de escape.

La comprobación CDP `Browser.setPermission` para `protocol-handler` fue rechazada como descriptor inválido. El puerto V1 congelado carece de un mediador pre-efecto soportado para este canal host; cerrar la página después de navegación o agregar otro recognizer JS no demuestra enforcement nativo. El código upstream [ExternalProtocolHandler](https://chromium.googlesource.com/chromium/src/+/main/chrome/browser/external_protocol/external_protocol_handler.cc) distingue el lookup externo de la ruta HTTP. La extrapolación a un handler registrado es una **inferencia del flujo de código**, no un lanzamiento probado aquí. La limitación declarada corresponde a este adapter/build/configuración, no a todo Chromium posible.

Se detiene aquí el hardening. No se introduce una cuarta ronda, transformación arbitraria de documentos, nuevo engine, política global de protocolos ni modificación arquitectónica para conseguir PASS.

## Comprobaciones cerradas y límites de evidencia

- Targets agentic `file:`, `javascript:`, custom, `data:`, `chrome:` y `about:`: **6/6 rechazados** por la API, antes de efecto/broker.
- `https-metadata`: **denegación nativa fresca explícita**, `BROWSER_EGRESS_DESTINATION_DENIED`, cero upstream y cleanup confirmado. El probe histórico/secuencial que dejó ese intento UNKNOWN permanece intacto; no se reinterpreta. La nueva prueba comienza en otro contexto limpio, sin el cache de CONNECT fallidos previos.
- Metadata V1: manualTakeover/upload/download conocidos true en adapter headful; persistentSession/screenshot conocidos false; platform `win32`; maxPages `3`. Son soporte estático del adapter, no disponibilidad o certificación de red/visión.
- Discovery productivo vuelve a producir `publicOnly = UNKNOWN`, `available = UNKNOWN`; no puede anunciar browser tools ni fallback BEST_EFFORT. Las dos áreas de wiring/truthfulness cerradas en revision02 se conservan, sin nuevo claim E2E.
- Cierre browser/context/broker/upstream confirmado; los PID nativos capturados ya no están vivos. No se introdujo confianza TLS de test que deba limpiarse.

HTTPS admitido con renderer/TLS confiable **no quedó demostrado** en esta revisión. Tampoco se completó una traza exhaustiva de canales TCP/UDP/DNS/background ni se amplió el canario TCP de fallo broker. Son pruebas pendientes para un cierre positivo, **no** el fundamento de un supuesto blocker universal del SO. Redirects, subresources, nuevos origins, WS/WSS y service workers conservan su evidencia contractual/nativa controlada de revision02, ahora reejecutada como regresión; no se promueve a certificación de exclusividad.

## Tests e integridad

Todos los outputs y `--basetemp` permanecen fuera del working tree. Autoload de plugins y configuración privada deshabilitados, `no:cacheprovider`, sin nuevos skips/xfails/filtros. Comandos y hashes en [test_results.json](test_results.json).

| Verificación | Resultado final |
|---|---|
| Metadata/gate focal | 11 PASS / 0 FAIL / 0 ERROR / 0 SKIP |
| Active Web completa | 702 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 0 XFAIL |
| Inventario estático CI | PASS; 4.048 contratos; 0 sin clasificar |
| Integridad de estado previo | PASS; 0 drift inesperado; 69/69 outputs externos intactos |

Los 11 contratos focales están incluidos en los 702; no se suman como casos únicos distintos. Se añadieron cinco funciones base portables al inventario, sin cambiar workflows, reglas anteriores, assertions ni runners. La reversión exclusiva de esas cinco entradas recupera exactamente el SHA de revision02.

Se conservan las ejecuciones iniciales fallidas: import incorrecto del nuevo helper (**HARNESS_BUG**, 1 collection ERROR), clasificación faltante de los nuevos tests (**HARNESS_BUG**, 701 PASS/1 FAIL), diagnóstico CDP que suponía enable-automation y comparación inicial string/objeto del verificador de hashes. Se corrigió sólo instrumentación/inventario; no se relajaron assertions. Los XML/raw originales no se sobrescribieron.

Core/Security/Memory/Knowledge/Desktop se reutilizan desde revision02, con módulos y evidencia preservados; no se anuncian como campañas nuevas. El único fallo Core HOME/USERPROFILE continúa `PREEXISTING_CORE_HARNESS_DEBT`, no blocking para esta tarea, y no se recalifica como PASS ni modifica.

## Archivos de esta tarea

Producto: `local_cli/infrastructure/active_web/playwright_adapter.py`, únicamente metadata V1 conocida. Inventario: `ci/pytest_contracts.json`, únicamente cinco entradas nuevas. Nuevos harness/tests: `tests/active_web_v1/egress_closure_probe.py` y `test_aw8_egress_metadata.py`. Evidencia aditiva: este directorio y raw externos referenciados. Los cambios de producto/inventario son byte-reversibles a los pins revision02.

Detención para revisión humana. No se ejecutará AW8 final mientras el canal externo host carezca de control pre-efecto demostrable en la composición V1.
