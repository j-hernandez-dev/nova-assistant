# Bloque 4 — Chrome y Edge opcionales

Fecha: 2026-10-14. Implementación en `C:/Users/joseh/Downloads/nova-min/nova-assistant`.

**BLOQUE_4_CHROME_EDGE = IMPLEMENTADO**

## Uso

WebView2 incluido continúa como predeterminado. No se pregunta por el navegador al
iniciar y una tarea normal no necesita comandos administrativos. Para cambiarlo:

```text
/browser list
/browser use edge
/browser use chrome
/browser use webview2
/browser status
```

Los comandos figuran en `/help`. Los argumentos inválidos reciben un mensaje en
inglés, sin traceback. CLI, JSONL y el backend de Desktop usan `SetBrowser` y el
mismo estado de Application. No se añadió un selector ni lógica de seguridad en
React/Electron.

La elección explícita se conserva en `browser-preference.json` dentro del directorio
de estado configurado de Nova. No se modificaron preferencias personales, no se
importó configuración histórica y no se migró la elección de buscador. Leer la
preferencia no escribe ningún archivo.

Elegir un navegador diferente cierra la sesión anterior antes del cambio. La próxima
operación crea una sesión y refs nuevas. No se permite cambiar durante un turno o
subagente activo. Si el cierre no puede confirmarse, la elección se rechaza y no
se presenta una segunda tentativa de cierre como confirmada.

Si el navegador falta, se informa `BROWSER_NOT_INSTALLED`; no se instala ni se
descarga Chromium, no se cambia la preferencia silenciosamente y no se toca el
navegador personal. Una elección guardada cuyo navegador fue desinstalado permanece
visible como unavailable hasta que el humano cambie de opción.

`/search engine ...` sigue eligiendo el buscador, no el navegador. `/fetch off`
continúa desactivando únicamente el fetch HTTP. Búsqueda y navegación Browser
funcionan independientemente.

## Implementación

- Una `BrowserSelection` host-owned se comparte entre las herramientas de Browser
  y `web_search`. El modelo no recibe parámetros para elegir ejecutable, perfil
  personal, canal ni autoridad.
- La detección Windows consulta App Paths y ubicaciones habituales de instalación.
  No utiliza un ejecutable arbitrario encontrado en PATH.
- WebView2 conserva su host y Fixed Version incluidos. Chrome/Edge se lanzan con
  Playwright mediante sus canales `chrome`/`msedge` y el ejecutable instalado
  detectado explícitamente. No hay fallback a Chromium descargado.
- Los canales instalados ejecutan el modo headless del navegador real, con un
  perfil temporal nuevo de Nova. No usan cookies/login/extensiones de un perfil
  personal. La intervención humana visible pertenece al bloque posterior.
- Observación, ElementRefs, click/type/key, historial, navegación y búsqueda usan
  las mismas operaciones Playwright. Se extrajo el IO de página común y se separó
  del arranque específico de Windows. No se creó otro pipeline de Policy.
- El driver Node incluido se asigna al Job de procesos propio antes de lanzar el
  navegador. Se verifica por handle del SO su ruta incluida; luego se comprueban
  PID/ruta reales del navegador, pertenencia al Job y el `user-data-dir` exacto.
  Esto prueba el ejecutable utilizado y permite cerrar sólo los procesos propios;
  no constituye aislamiento de red ni de efectos del sistema.
- La consulta del PID del driver usa un seam interno pequeño de Playwright 1.64,
  versión ya fijada en el paquete. Si deja de existir, el arranque falla de forma
  tipada antes de lanzar Chrome/Edge. No se usa esa interfaz como tool del modelo.
- Se mantiene Policy → Approval cuando corresponde → Grant de un uso → binding
  fresco → acción. El cambio de backend invalida la sesión anterior: un Grant/ref
  de WebView2 no se adapta para actuar en Edge.
- Una acción incierta sigue UNKNOWN y no se repite automáticamente. Se conserva
  la distinción entre interacción local observada y éxito remoto.

Los tres backends conservan `networkIsolation=NOT_PROVIDED` y
`controlClass=HOST_UNISOLATED`. No se atribuye PUBLIC_ONLY al navegador. El guard
nativo de WebView2 no se presenta como una certificación heredada de Chrome/Edge.
Las herramientas comunes rechazan destinos explícitos de elementos que pretendan
lanzar protocolos externos o URLs locales.

Playwright documenta el uso de Chrome/Edge instalados por canal y las limitaciones
de políticas empresariales. También requiere un directorio separado para
automatización; no se utiliza el perfil habitual. Referencias:
[navegadores](https://playwright.dev/python/docs/browsers),
[launch_persistent_context](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context).

## Resultados

| Comprobación | Resultado |
|---|---|
| WebView2 predeterminado, sin prompt inicial nuevo | PASS |
| Selección persistente y cambio explícito | PASS |
| CLI / JSONL / Desktop backend, una Application | PASS |
| Argumentos inválidos y navegador ausente, sin traceback | PASS |
| Sesión anterior cerrada, refs/Grant anteriores rechazados | PASS |
| Policy / Approval / Grant y UNKNOWN preservados | PASS |
| Regresión focal Python | 590 casos PASS, 0 fallos, 0 skips |
| Comprobación posterior de errores tipados | 41 casos PASS, solapados; no sumados al denominador |
| Job nativo Windows `browser-block4` | 1 caso PASS, 0 skips |
| Inventario CI | 3866 funciones clasificadas, 0 sin clasificar |
| WebView2 real 155.0.4283.45 | PASS nativo |
| Edge instalado 155.0.4283.45 | PASS nativo |
| Chrome instalado | NO DISPONIBLE en este equipo; negativo PASS, positivo pendiente |
| Modelo local con Edge y catálogo mixto | PASS, smoke focal de una petición |

No se afirma una prueba positiva de Chrome: no está instalado y no se descargó.
Su launcher, selección y canal están implementados; comparte las operaciones
verificadas con Edge. Debe ejecutarse el mismo smoke en una instalación con Chrome
antes de afirmar compatibilidad nativa positiva para esa versión.

### Prueba nativa

Páginas HTTP owned, sin dependencia de Internet público. En WebView2 y Edge se
comprobó JS renderizado, refs opacas, input + Enter, ref obsoleta sin efecto en
canario, un click aprobado con exactamente un efecto, historial, recarga,
redirect con query/fragment, popup gestionado y búsqueda → artículo.

La identidad Edge confirmada fue:

```text
channel = msedge
executable = C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe
version = 155.0.4283.45
profile = nuevo nova-edge-<uuid>, temporal y eliminado al cerrar
```

Los popups quedan dentro de la sesión propia y mantienen una sola página actual;
no se ofrece una API multitab en este bloque. No se utilizaron perfiles personales.

### Prueba con modelo real

`qwen3.5:9b`, Q4_K_M, digest
`c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`.
Perfil productivo: contexto 8192, temperature 0.6, top_p 0.95, top_k 20,
think=false, sin aumentar reservas de contexto/salida.

Se seleccionó Edge mediante el comando real de Application. Con fetch desactivado
y herramientas locales/Browser juntas, el modelo decidió:

```text
web_search → browser_navigate → read → respuesta
```

La respuesta incluyó `AMBAR-73` del artículo realmente abierto, su URL con
query/fragment y `PIEDRA-AZUL` del README leído. No usó terminal. Es un smoke de
funcionamiento, no un benchmark cuantitativo de calidad del modelo.

### Incidencias de desarrollo

Edge inicialmente rechazó `Browser.getBrowserCommandLine` porque no estaba activo
`--enable-automation`. Se añadió ese flag de automatización para comprobar el perfil
exacto, sin alterar Policy o ampliar herramientas. El intento fallido cerró sus
procesos y eliminó su perfil. Los tests iniciales de configuración necesitaron
crear Turns registrados en su fixture para emitir eventos válidos; no se debilitó
la comprobación de Application.

Finalmente se preservaron los errores tipados de arranque en las operaciones
comunes. Un fallo antes de STARTED devuelve su motivo útil; uno después de STARTED
mantiene el outcome incierto. Esta corrección se comprobó focalmente y con el job
nativo posterior.

## Cambios principales

- Nuevos: `browser_config.py`, `application/browser_selection.py`,
  `infrastructure/browser/discovery.py`, `windows_installed.py`, `page_io.py`.
- Compartidos: `tools/browser_tools.py`, `browser_search_tool.py`,
  `bootstrap_passive_web.py`, `infrastructure/browser/pages.py`, `search.py`,
  `windows_webview2.py`, `process_job.py`.
- Integración: `application/commands.py`, `session.py`, `tool_runtime.py`,
  `browser_navigation.py`, `cli.py`.
- Verificación: `tests/test_browser_selection.py`, `tests/browser_block4/`,
  `scripts/smoke_browser_block4.py`, inventario y runner CI.

Windows continúa siendo la plataforma implementada y probada. Las operaciones de
página/búsqueda están separadas de detección y procesos Windows; no se declararon
soporte ni pruebas Linux/macOS, ni se añadieron adaptadores vacíos.

## Limpieza y preservación

Los recibos finales confirman cierre de procesos propios, Jobs vacíos, perfiles
eliminados y listener detenido. No se borraron datos del usuario ni el perfil
preliminar retenido de los bloques anteriores.

No hubo rebuild ni modificación del host nativo o runtime WebView2 incluidos:

- host DLL SHA256: `add85e2da7908b21d03e3bba2808a65ff22377ff597b024816e9388d61ff71ca`;
- runtime EXE SHA256: `46b3c6ac9169416cc2ee76b23ee3d9db0eb8daefb914b1d9cc0f5d2387b033ac`.

No se modificaron evidencias anteriores ni el repositorio antiguo. Sin staging,
commit, push, tag o release. Los bloques de takeover/transferencias y distribución
final no se adelantaron.
