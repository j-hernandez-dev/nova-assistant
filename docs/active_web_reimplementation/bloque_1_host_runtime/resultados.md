# Resultados del Bloque 1

Fecha: 2026-10-14. Estado: **BLOQUE_1_HOST_RUNTIME = PASS** en Windows x64.
El servicio y el paquete pasan tanto el smoke directo como la entrada manual de CI.
El [receipt final directo `native-smoke-02.json`](runs/native-smoke-02.json) contiene
27 comprobaciones aprobadas y limpieza confirmada antes de escribirlo.

## Ejecución nativa directa

Comando, desde la raíz de nova-min, con el Python compatible existente:

```powershell
& $novaPython scripts/smoke_browser_block1.py --package-dir dist/browser/windows-x64 --output docs/active_web_reimplementation/bloque_1_host_runtime/runs/native-smoke-02.json
```

Código de salida `0`. El receipt registra inicio a `2026-10-14T18:50:36.196416Z` y
fin a `2026-10-14T18:50:41.413861Z`: aproximadamente 5.22 segundos. Esta ejecución
ocurrió después de terminar la publicación del candidato que incluye la cancelación
de descargas y la comprobación del assembly administrado.

| Validación | Resultado y evidencia |
|---|---|
| Host autocontenido | Arranca con PATH limitado a System32 y DOTNET_ROOT apuntando a una ruta propia inexistente; no resuelve dotnet.exe externo. |
| Runtime incluido | WebView2 `155.0.4283.45`; ruta del proceso obtenida por Windows dentro de `runtime/msedgewebview2.exe`. |
| Playwright incluido | Playwright `1.64.0` y driver reales desde `python/` del paquete; conexión CDP al árbol del host. |
| Canal CDP | Listener en loopback, puerto efímero, PID perteneciente al árbol administrado. |
| Navegación y lectura | Servidor HTTP propio en `127.0.0.1`; la página ejecuta un temporizador JS y el servicio lee el DOM actualizado. |
| Interacción | Un click Playwright sobre el botón owned cambia el texto leído a `Clicks: 1`. |
| Procesos | Nueve procesos observados; todos los handles retenidos confirmaron salida, incluido el driver Playwright. |
| Limpieza | Host cerrado, job vacío, perfil eliminado y listeners CDP/HTTP cerrados; thread HTTP y directorio temporal eliminados. Cierre graceful, sin errores de servicio. |

Identidad observada del candidato:

| Componente | SHA-256 |
|---|---|
| `host/nova-webview-host.exe` | `3e9d35979acf28a7bbab2eaa0bc58563257a17710568d486e60b94fe7022b4a0` |
| `host/nova-webview-host.dll` | `af0a5621e20b47c35a90b6a871a6097d934bbada51fefe219b63e4e6eb8a2e0d` |
| `runtime/msedgewebview2.exe` | `46b3c6ac9169416cc2ee76b23ee3d9db0eb8daefb914b1d9cc0f5d2387b033ac` |

El smoke compara ambos archivos del host con `package.json`. Estos hashes
identifican el paquete probado; no son un gate de hashes de todas las fuentes
para habilitar Browser.

El [arranque directo desde el paquete](runs/bootstrap-from-package.json) también
registró PASS con el Python existente `3.14.6`: Playwright no era descubrible ni
estaba preimportado antes de iniciar el servicio. El servicio cargó por sí mismo
su módulo y driver incluidos, navegó y leyó una página owned, y confirmó cierre
graceful, job vacío y perfil eliminado. El `.dll` coincide con el candidato anterior.

## Regresión y selección CI

El [receipt de regresión](regression_results.json) registra 222 casos distintos
aprobados en estos seis archivos:

- `tests/test_browser_block1.py`: 27 casos de 13 contratos portátiles del adaptador,
  con dobles; cubren componentes/dependencias ausentes, identidad y endpoint inválidos,
  fallo CDP, cancelación Ctrl+C, asignación de job, cierre forzado, perfiles propios y límites.
- `tests/test_fetch_preferences.py`, `tests/test_fetch_preferences_shell.py` y
  `tests/test_cli_preferences.py`: junto con los 27 anteriores, 82 casos aprobados.
- `tests/test_agent.py` y `tests/test_main.py`: 140 casos aprobados.

El inventario positivo contiene 3834 contratos y cero sin clasificación. Los
13 contratos portátiles nuevos están en Core. El contrato del paquete real es
`SPECIAL_INFRASTRUCTURE_ONLY`, job manual Windows `browser-block1`, seleccionado
con `--special`. Su colección explícita aprobó; esa colección no ejecuta motores.

La [entrada manual final](runs/ci-wrapper-03.json) ejecutó ese contrato real y
terminó con código `0`, sin skips. Su [receipt nativo](runs/ci-native-03.json)
identifica el mismo host/runtime y confirma las 27 comprobaciones, el cierre
graceful y la limpieza completa; observó diez procesos y todos terminaron.
Este caso nativo se cuenta por separado de los 222 casos de regresión; las
repeticiones diagnósticas no aumentan el denominador.

El [receipt del paquete](package_receipt.json) conserva sus dependencias y
los hashes de los ejecutables probados. Los binarios generados permanecen en
`dist/browser/windows-x64/`; `build/`, `dist/` y `native/**/bin|obj` son salidas
de compilación ignoradas. El código, fixture y receipts del bloque se conservan.

## Intentos anteriores y alcance

El [primer smoke `native-smoke-01.json`](runs/native-smoke-01.json) registró PASS
en 26 comprobaciones y limpieza completa. Una publicación del host se solapó con
esa ejecución y el receipt todavía no identificaba el `.dll`; se conserva como
evidencia preliminar, no como aceptación del candidato final. El segundo receipt
es el resultado nativo que identifica el assembly final.

El [primer intento de entrada CI](runs/ci-wrapper-01.json) falló con
`OUTPUT_OUTSIDE_BLOCK1_OR_TEMP` antes
de iniciar el host. El runner cambia TEMP y sitúa el temporal de pytest en una
carpeta hermana; el wrapper pasaba esa ruta al smoke, cuyo output está limitado a
temporales propios y el directorio del bloque. El wrapper ahora deja al smoke
crear su output temporal y conserva únicamente una copia del receipt saneado en
el directorio propio de pytest. El [segundo intento CI](runs/ci-wrapper-02.json)
pasó ese punto pero su [receipt nativo](runs/ci-native-02.json) registró FAIL con
`HOST_EXITED` bajo el entorno saneado de CI. Confirmó host cerrado, job vacío,
perfil eliminado y recursos HTTP propios cerrados; también conservó el código
`CONTROL_PIPE_CLOSE_FAILED`. Ese intento permanece FAIL.

El [diagnóstico causal](ci_environment_diagnosis.json) aisló el fallo a la
estructura artificial del perfil Windows del runner: asignaba carpetas hermanas
sin relación a USERPROFILE, APPDATA y LOCALAPPDATA. WebView2 recibía sus flags
CDP, pero no abría el listener ni escribía DevToolsActivePort. Variar la longitud
del perfil Browser no corrigió el fallo. Restaurar sólo USERPROFILE permitió
arrancar; después se demostró que una estructura coherente enteramente temporal
también funciona, sin heredar el perfil personal.

La corrección se limita al job `browser-block1`: APPDATA y LOCALAPPDATA quedan
bajo el USERPROFILE temporal, con TEMP/TMP bajo AppData/Local/Temp. El tercer
intento pasó mediante la entrada oficial de CI. Este ajuste no cambia el host,
el runtime, las preferencias del usuario ni los demás jobs.

Se validó el componente con CPython `3.14.6` x64, SDK WebView2 `1.0.4258.31`, runtime
Fixed Version `155.0.4283.45` y Playwright `1.64.0`. El paquete sin comprimir ocupa
`943197830` bytes en 921 archivos; el campo `bytes` del receipt registra
`943196682` bytes de payload sin contar el propio `package.json`. Su CAB de
runtime tiene `310544938` bytes. No es todavía un
instalador completo de Nova.

El host incorpora .NET `10.0.7`, publicado con SDK .NET `10.0.203`. Se comprobó
su arranque sin `dotnet.exe` resoluble. Fixed Version no se actualiza mediante
Evergreen: distribuir futuras versiones del motor y sus correcciones corresponde
a las nuevas builds de la aplicación.

Los recursos activos de las pruebas finales quedaron cerrados: perfiles Browser,
procesos, listener CDP y servidor HTTP propio. Se retienen el paquete/build y los
diagnósticos temporales como archivos de trabajo. Una comprobación final de
procesos Windows no encontró host, WebView2 ni driver Node ejecutándose desde
este paquete. No se hicieron staging, commit, push, tag ni release.

## Archivos e integración

La implementación está en `C:/Users/joseh/Downloads/nova-min/nova-assistant`.

- `native/nova-webview-host/`: host Windows y protocolo privado de ciclo de vida.
- `native/browser-dependencies.json`: dependencias y distribución Fixed Version.
- `local_cli/application/browser.py`: servicio y puerto Browser internos.
- `local_cli/infrastructure/browser/`: conexión CDP, carga del driver incluido y
  ciclo de vida de procesos/perfil.
- `scripts/package_browser_windows.py`: construcción del componente distribuible.
- `scripts/smoke_browser_block1.py` y `tests/browser_block1/`: fixture y prueba real.
- `tests/test_browser_block1.py`: regresión portable del servicio.
- `ci/pytest_contracts.json`, `ci/run_contracts.py`: selección portable/manual y
  entorno temporal del job Windows.
- `pyproject.toml`, `.gitignore`: dependencia opcional y salidas de compilación.
- `docs/active_web_reimplementation/bloque_1_host_runtime/`: instrucciones,
  resultados y receipts de este bloque.

El repositorio antiguo se utilizó como referencia de lectura. La implementación
no importa su composición, manifests de disponibilidad ni router léxico.

El Bloque 1 no registra herramientas productivas en el modelo; esa integración
corresponde al Bloque 2. La ventana inicial es oculta. Los permisos de sitio y
las aperturas de aplicaciones externas se deniegan y las descargas se cancelan
hasta las transferencias propias del Bloque 5.

No se acreditan búsqueda pública, Chrome/Edge, takeover, uploads/downloads
productivos, instalador completo ni Linux/macOS. El navegador mantiene red normal;
no se afirma aislamiento universal. No se ejecutaron campañas HUX ni se heredaron
denominadores o resultados históricos.
