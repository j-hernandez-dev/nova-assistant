# AW8 prerequisite remediation — resultado aditivo

`AW8_PREREQUISITES = PARTIAL`
`SAFE_TO_RESUME_AW8 = false`

El AW8 original permanece **BLOCKED**. Esta revisión no modifica sus artefactos ni los manifests/certificaciones AW0–AW7. No es una fase nueva, no es la campaña final AW8 y no declara ACTIVE_WEB_CORE READY.

## Prerrequisitos

| Requisito | Estado | Evidencia y límite |
|---|---|---|
| PRODUCTIVE_BROWSER_TOOL_PATH | BLOCKED | CLI/JSONL siguen sin fábrica Active Web productiva ni las nueve tools V1. No se implementó la conexión completa AgentLoop/ToolRegistry/ToolRuntime/Policy/Approval/Grant/servicio browser. |
| EXCLUSIVE_PUBLIC_ONLY_EGRESS | BLOCKED | Hardening y prueba nativa negativa acotada, no prueba completa de exclusividad del engine. |
| TRUTHFUL_ACTIVE_WEB_CAPABILITY | BLOCKED | El componente conserva UNKNOWN honestamente, pero aún no alimenta discovery del composition root ni mide una composición productiva completa. |

Siguen abiertos **AW8-PREFLIGHT-001 / PRODUCT_INTEGRATION_GAP** y **AW8-PREFLIGHT-002 / CERTIFICATION_PREREQUISITE_UNKNOWN**. No se encontró contradicción normativa ni se resolvió una nueva decisión de arquitectura. El bloqueo no es el fallo heredado HOME/USERPROFILE.

§18.3 exige no anunciar Active Web si no se demuestra ausencia de bypass relevante. §25 y AW-INV-007/008/027/029 impiden interpretar instalación, flags, broker existente o UNKNOWN como disponibilidad. No se fuerza ningún booleano.

## Cambios acotados

- `playwright_adapter.py`: argumento fijo por proceso `--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1`; inspector interno fijo sobre la misma instancia/contexto/page, sin JS/selector/URL del caller. Capabilities siguen UNKNOWN.
- `browser_network.py`: reducción opcional de hosts aplicada antes de DNS; `None` conserva PUBLIC_ONLY normal y tuple vacía deniega todo. Nunca permite un destino privado. Evita tráfico de fondo ajeno al probe.
- Nuevo `productive_probe.py`: diagnóstico explícito con clases shipping PlaywrightBrowserAdapter, BrowserNetworkPolicy, HttpFetchBroker y BrowserEgressBroker. Sin endpoint/resolver ficticio, instalador, profile personal, firewall global ni override de disponibilidad.
- Nuevo `test_aw8_prerequisite_probe.py`: diez funciones / dieciséis instancias: quince portables y una nativa explícita con engine ya instalado. Doubles no son certificación nativa.
- `ci/pytest_contracts.json`: inventario positivo de esos contratos; probe nativo sólo evidencia local explícita. Sin cambios de workflows/runner. Retirar únicamente diez filas y dos reglas nuevas reconstruye byte-a-byte el SHA anterior: `921d7fa8f06833c114b7db1189fe3ef2b2565475bb39258a36a1230c845deef2`. Los dos selectors del job nativo AW7 siguen intactos.

No se registraron tools browser incondicionales, browser_eval_js, ContractOnlyBrowserTool ni planes privados de tests como producto. **Conserva el fail-closed actual, pero no termina la rama positiva de registro productivo.** Core, Security Policy/schema/grants, MEMORY, Knowledge, Desktop, roots, ToolRuntime y arquitectura no cambiaron respecto del freeze inicial de esta tarea.

## Prueba nativa: alcance limitado

Host: Windows 11 build 26200, C: NTFS local, HOST_UNISOLATED. Python 3.14.6; Playwright 1.63.0; Chromium 153.0.8010.12 revision 1243, ya instalado.

Probe headful acotado: 2026-10-09T22:15:29.640907Z–22:15:31.901436Z.

- 8/8 destinos HTTP/HTTPS privados, loopback, link-local y metadata rechazados por broker; 0 upstream; 0 registros perdidos.
- Broker real detenido deliberadamente: dos intentos HTTP/HTTPS al canario TCP loopback fallaron. Control positivo del listener desde el host confirmado; conexiones browser = 0, también durante cleanup.
- Cleanup engine/broker/canario confirmado.
- RTC/prefixed RTC no expuestos en la ventana inspeccionada. Es about:blank sin secure context: **no** demuestra disable de service workers/WebTransport en contextos seguros ni todos los workers.
- engine KNOWN/PLAYWRIGHT_CHROMIUM; networkBroker KNOWN/true; controlClass KNOWN/HOST_UNISOLATED; publicOnly UNKNOWN; available UNKNOWN.

El snapshot describe el momento **anterior** al fault injection/cleanup; no es un contexto vivo disponible después. Los argumentos son configuración fija del adapter, no lectura certificada de toda la command line. Se usan clases productivas con composición diagnóstica de alcance reducido, **no el composition root de Nova**.

Faltan pruebas positivas de HTTP/HTTPS público controlado, redirects/subresources/nuevos origins; DNS engine-wide; WS/WSS y service workers en secure context; QUIC/direct UDP/WebRTC fuera de esa ventana; fallback no-loopback TCP/UDP; schemes internos/file/data/javascript/custom; y vínculo con roots/discovery/registro/servicio browser productivos. Véase `egress_enforcement.json`. Flags y componentes no se convierten en PASS de exclusividad.

Referencias de diseño, no certificación del engine instalado: [proxy de Chromium](https://chromium.googlesource.com/chromium/src/+/HEAD/net/docs/proxy.md), [resolución Chromium](https://new.chromium.org/developers/design-documents/network-stack/socks-proxy/), [routing/service workers Playwright](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-route).

### Corrida diagnóstica anterior: corrección explícita

Se conserva íntegro el raw externo `productive-probe-final/result.json`. Su `noThirdPartySites=true` es **incorrecto**: Chromium hizo un CONNECT de fondo a `https://www.google.com` con upstreamConnected=true **por el broker**. No demuestra bypass directo ni ampliación de autoridad; tampoco sirve como corrida sin terceros o promesa universal de ausencia de payload TLS.

Se registra **PROBE_SCOPE_BUG**. El probe posterior reduce a canarios numéricos antes de DNS y tiene 0 upstream, sin relajar PUBLIC_ONLY. No se usa la corrida contaminada para certificar exclusividad ni se depende de la respuesta de Google.

## Regresiones

| Gate | Resultado exacto |
|---|---|
| Nuevos contratos, código congelado | 16 PASS / 0 FAIL / 0 ERROR / 0 SKIP |
| Active Web completa, código congelado | 616 PASS / 0 FAIL / 0 ERROR / 0 SKIP |
| Core positivo completo aplicable | 3326 PASS / 1 FAIL histórico / 0 ERROR / 7 SKIP históricos; 53 subtests PASS; exit 1 |
| Security | 615 PASS / 0 FAIL / 0 ERROR / 0 SKIP |
| MEMORY | 791 PASS / 0 FAIL / 0 ERROR / 0 SKIP |
| Knowledge | 1015 PASS / 0 FAIL / 0 ERROR / 0 SKIP |
| Desktop | 71 PASS / 0 FAIL / 0 SKIP; TypeScript exit 0 |

Core: 3334 parameter instances; JUnit informa además 53 subtests (3387). Único FAIL final:
`tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`.
Permanece **PREEXISTING_CORE_HARNESS_DEBT**, no se marca PASS ni se filtra. HOME privado y USERPROFILE privado distintos explican PowerShell. Test/runner/producto/assertion asociados están intactos. Los siete skips coinciden por identidad con AW7; no hay nuevos xfails/exclusiones.

Se preservan XML/log/hash y clasificación de corridas intermedias: double con metadata inválida, nuevo selector CI mal clasificado, dos fixtures sin CancellationToken y comandos Desktop incorrectos. Se corrigieron sólo fixtures/metadatos/comandos nuevos, no assertions antiguas. Corridas con cambios en curso no fundamentan el resultado final congelado. Security/MEMORY/Knowledge/Desktop se reutilizan: los últimos cambios sólo afectaron probe/fixtures Active Web, sources/selecciones heredados siguen intactos y la regresión final Active Web/Core cubre los cambios posteriores.

No hay quality retries ni E2E AW8: inferencias = 0. Basetemp/profiles/outputs fuera de Git.

XML final Active Web: `ead8b38acd4958778e347136db474efd6f96961743847bae9aa202cad7b03334`.

XML final Core: `f5b368a844daf99a3b024a999fe1838fae5e7d1018b834f4c6a0d5cf2df5835b`.

Comandos, denominadores, timestamps, XML y hashes: `test_results.json`. Freeze de cinco componentes: `component_freeze.json`; baseline completo: 2298 pins. Integridad: `integrity.json`.

## Cierre

`AW8_PREREQUISITES = PARTIAL`
`SAFE_TO_RESUME_AW8 = false`

Se detiene con los dos blockers indicados: no hay evidencia suficiente para activar Active Web ni reanudar su campaña. No se recalifica AW8 ni certificaciones anteriores. Sin campaña final, inferencia, READY, commit, push, tag o release. Revisión humana requerida.
