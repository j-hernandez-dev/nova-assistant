# Block06 — factibilidad nativa del candidato CEF/Chromium

```ini
CEF_CHROMIUM_CANDIDATE = REJECTED
CEF_WEBRTC_SUPPRESSION = FAIL
```

**Alcance exacto:** se rechaza el artefacto/perfil probado: CEF `154.0.34+g14c5a08+chromium-154.0.8037.98`, Windows X64, distribución estándar mínima con host C++ propio y proxy fijo. No se construyó ni probó un fork CEF/Chromium con los gates de source propuestos. Este resultado no demuestra una imposibilidad universal de CEF; tampoco permite certificar ese futuro build.

## Primer gate causal

Una única ejecución válida del probe crítico produjo:

- `isSecureContext=true`, `RTCPeerConnection` construido, data channel creado y oferta aceptada; ICE completó con tres candidatos.
- Un datagrama STUN Binding Request de **20 bytes**, source UDP port `58929`, owner PID `32612`.
- Ese PID figura en el Job Object owned y el callback nativo lo identifica como utility / `network.mojom.NetworkService`. Host PID `36572`.
- El canario UDP había sido calibrado antes con un emisor Python distinto (`33596`, source port `64837`), cuyo OWNER_PID coincidió. La recepción nativa se conserva separada de la calibración.
- La fixture llegó por el proxy HTTP owned. El datagrama alcanzó el canario UDP separado, fuera de ese broker TCP.

Ventana nativa: `2026-10-11T16:35:00Z`–`16:35:03Z`; ventana monotónica del harness `112269.4079121`–`112271.5731316`. Receipt UDP: `112271.2579806`. Eventos/procesos/medición están en [native_probe_evidence.json](native_probe_evidence.json). No se llama QUIC a este STUN ni se afirma un data-channel conectado de extremo a extremo: la salida UDP ya basta para incumplir el gate.

La página usa un origen loopback HTTP potencialmente confiable, verificado como secure context por el engine real. Es un fixture offline, no PUBLIC_ONLY, no HTTPS remoto y no excepción productiva a la política. No se importó ninguna authority de Nova.

## Resultado de gates

| Gate | Resultado | Evidencia / límite |
|---|---|---|
| CEF_WEBRTC_SUPPRESSION | FAIL | PeerConnection/ICE y STUN owned directo |
| CEF_DIRECT_UDP_SUPPRESSION | FAIL | UDP relevante STUN; QUIC/HTTP3 específico no probado |
| CEF_PROXY_EXCLUSIVITY | FAIL | Ruta RTC no mediada; no atribución a fallback HTTP |
| CEF_SERVICE_WORKER_SUPPRESSION | INCONCLUSIVE | No ejecutado tras el fail-stop obligatorio |
| CEF_BROKER_OWNED_DESTINATION_RESOLUTION | INCONCLUSIVE | DNS/rebinding/prefetch no ejecutados |
| HTTPS estándar | INCONCLUSIVE | Success/hostname/chain/private-denial no ejecutados |
| Logical origin admission | INCONCLUSIVE | Redirect/iframe/fetch/coalescing/download coverage no ejecutada |
| CEF_EXTERNAL_PROTOCOL_GUARD | INCONCLUSIVE | Canary registrado/popups/takeover no ejecutados; ningún PASS WebView2 transferido |

Se detuvo al primer gate obligatorio FAIL. No hubo una segunda combinación de flags, prueba de otro engine ni continuación de los gates. Cero hits del target HTTP directo sólo describen esta fixture; no demuestran exclusividad general.

## Qué se construyó y qué no

El ejecutable separado consume directamente CEF C API, sin Electron, Playwright, renderer Desktop, BrowserTool, ToolRuntime ni IPC Nova. Se compilaron **fuentes del harness**, no fuentes CEF/Chromium. Perfil solicitado único: proxy numérico HTTP, bypass implícito loopback eliminado, disable-quic/background/component-update. Son runtime options, no gates certificados. En particular, el binario no contiene RTC-off nativo.

El gate de identidad observó ABI `15400` y hash `726dc73763db22edb289e41af2421a232617f7f4` antes de initialize. Distribución y DLL se fijaron por hash; la identidad completa está en [candidate_identity.json](candidate_identity.json). No se hizo una atestación independiente de todos los módulos cargados. No se afirma certificado de perfil a partir del string solicitado.

En [control_matrix.json](control_matrix.json) se separan supported CEF API, runtime options, compile-time/API configuration y source gates. El candidato propuesto en la revisión previa necesitaba justamente estas últimas fronteras; consumir el binario estándar no las instala.

### Source/build: lo que faltaría, sin implementarlo

Para un candidato fuente-controlado, el punto conceptual RTC es negar construcción/uso de PeerConnection y su backend P2P en todos los contextos, o retirarlos mediante una configuración de build realmente soportada por el pin elegido. **No** se da por válido el antiguo `enable_webrtc=false` de otros releases: no se verificó una receta actual de CEF154.

SW exige gate native de register/access/start, no un wrapper JS, interceptar algunos scripts, cookies-off ni unregister posterior. El punto de embedder a revisar es `ContentBrowserClient::AllowServiceWorker` y todas las particiones; el hook no está implementado en este harness. Las fronteras resolver/socket/NetworkService deben rechazar todo destino distinto del broker y reinstalarse antes de tráfico tras restart. Native `DisableQuic` no sustituye UDP/P2P gating. Todo sigue sin construir ni certificar.

CEF expone callbacks de URL/request y `OnProtocolExecution`; Chrome-style también puede delegar el protocolo al handler default. DENY_ALL exige cerrar **todas** esas rutas pre-effect, no sólo dejar un boolean false para unknown schemes. Son puntos de source/API, no resultados nativos. ([CEF browser client fijado](https://raw.githubusercontent.com/chromiumembedded/cef/14c5a089e8452874cb1a556dc3fde26ed2d87723/libcef/browser/chrome/chrome_content_browser_client_cef.cc), [Resource handler fijado](https://raw.githubusercontent.com/chromiumembedded/cef/14c5a089e8452874cb1a556dc3fde26ed2d87723/include/cef_resource_request_handler.h)).

Harían falta build propio de CEF/Chromium, pin de dependencias/GN/Ninja/Clang/toolchain, gates/patches por versión, evidencia de reproducibilidad y recertificación por cada cambio. El uso de un tar publicado no demuestra reproducible build. Coste de mantenimiento alto, especialmente para updates de seguridad: runtime fijo no significa congelarlo sin parches. No se ejecutó checkout/build completo ni se implementó fork. Ver [source_control_feasibility.json](source_control_feasibility.json).

Coste observado: archive `172,752,666` bytes; libcef.dll `289,818,624`; árbol de distribución retenido `452,967,884`. Despliegue app-local, sin installer/admin/driver/service/política global/CA. Se preservan notices/licencias del paquete. La publicación final exigiría su revisión de distribución; no hay release aquí.

## Compatibilidad futura Block05

La API permite controles/pages, callbacks lifecycle, frame/DevTools fixed primitives, file dialogs/download handlers y UI owned. Una Page se creó y cerró realmente. Opacidad de refs, freshness, cuotas, approvals exactas, secret capture, takeover epochs y staging honesto no vienen certificados por esa disponibilidad.

[compatibility_block05.json](compatibility_block05.json) clasifica cada función `SUPPORTED` por primitive/API, `PLAUSIBLE` por integración pendiente o gap que apareciera. `SUPPORTED` no es un PASS de BrowserPort ni hereda la corrida 561 de WebView2. Application/Policy/Grant/DTOs no se modificaron. Un future adapter no puede exponer eval genérico ni selectors/handles a modelo.

## Preparaciones conservadas

Antes de la ejecución válida hubo fallos exclusivamente de preparación:

1. Compilación: entorno VS no incluyó el SDK instalado; C1083 Windows.h. Se añadieron include/lib paths explícitos al SDK10.0.26100.0, sin instalarlo.
2. Job assignment: el harness pidió SET_INFORMATION en lugar de SET_QUOTA; proceso terminado antes de permitir initialize.
3. Initialize: salida `0x80000003`, sin engine/control/fixture; INCONCLUSIVE, no PASS por cero UDP. Se observó ICU ausente junto al exe; se corrigió el deployment conforme al README, fijó stack x64 y habilitó log privado. No se aisló causalmente cuál de esas correcciones explica el initialize anterior.

Se conservan [preparation_evidence.json](preparation_evidence.json) y [setup_initialization_attempt.json](setup_initialization_attempt.json). `oneEngineRun` en ese receipt inicial expresa intención del driver, no initialize exitoso: sus eventos no incluyen ENGINE_INITIALIZED. No se convierten los intentos de preparación en fallos de seguridad ni éxitos retrospectivos. El último candidato ejecutó el único probe RTC completo; no retries de calidad.

## Lifecycle y archivos nuevos

El probe válido recibió BROWSER_CLOSED/ENGINE_SHUTDOWN_CONFIRMED, exit0, sin forced kill. El Job quedó vacío y la inspección posterior no encontró procesos del harness. Los listeners cerraron.

La eliminación validada de tres perfiles **nuevos** fue rechazada por la política de herramientas antes de ejecutar el comando. No se sorteó esa restricción ni se reintentó con otro mecanismo. Los perfiles quedan **CLEANUP_UNCONFIRMED**, bajo root privado protected-ACL/no-reparse, para cleanup humano separado. Binarios/archive se retienen como artefactos privados del harness, no instalados en Nova. No se declara UDF deleted ni CLOSED. Esto no cambia los 36 UDF históricos ni el PASS histórico Block05.

El primer driver no persistió los números efímeros de los endpoints destino/proxy. El código, protocolo, PID, calibration y receipt prueban el bypass STUN; esa limitación impide presentarlo como certificado exhaustivo de red. Ver [cleanup_evidence.json](cleanup_evidence.json).

## Preservación y decisión

```ini
CEF_CHROMIUM_CANDIDATE = REJECTED
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
WEBVIEW2_BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

No se recomienda redactar V1.2: no se cumplió el gate NATIVE_FEASIBILITY_PASS. Ningún producto/arquitectura/CI/test histórico fue editado; la integridad del árbol previo está en [integrity.json](integrity.json). Sin Block07, AW8 E2E, commit/push/tag/release. Detención para revisión humana.
