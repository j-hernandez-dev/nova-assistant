# Bloque 1: host y runtime WebView2 incluidos

Validado en Windows x64 el 2026-10-14. El [smoke nativo final](runs/native-smoke-02.json)
registra PASS en sus 27 comprobaciones y confirma la limpieza de los recursos
propios. El alcance y los resultados de regresión se detallan en [resultados.md](resultados.md).

Este bloque prepara el servicio Browser interno en Windows x64: host WinForms
autocontenido, WebView2 Fixed Version seleccionado por ruta explícita, perfil
temporal propio y Playwright conectado mediante CDP local. No registra herramientas
del modelo ni modifica el loop normal, Policy, preferencias o proveedores de búsqueda.

## Paquete y dependencias

El lock de construcción es `native/browser-dependencies.json`. Para esta revisión
selecciona WebView2 Fixed Version `155.0.4283.45` x64, SDK WebView2 `1.0.4258.31` y
Playwright Python `1.64.0` con su driver y dependencias. El lock registra el origen
y SHA-256 del CAB oficial. No contiene hashes de fuentes para habilitar Browser.

El paquete generado tiene esta estructura:

```text
dist/browser/windows-x64/
  host/nova-webview-host.exe    # publicación .NET autocontenida, con dependencias
  host/nova-webview-host.dll    # assembly administrado identificado en el receipt
  runtime/msedgewebview2.exe    # Fixed Version, con el resto de su distribución
  python/                     # Playwright, driver Node y dependencias Python
  package.json                # versiones, layout y receipt de construcción
  build-dependencies.json
  README.txt
```

Se conserva el contenido completo de esas carpetas. Éste es el componente Browser;
todavía no es un instalador completo de Nova. Las dependencias incluidas en este
paquete se construyeron para CPython `3.14.6` x64; se usa un intérprete compatible
de Nova o del usuario. El paquete completo ocupa `943197830` bytes (aproximadamente 0.94 GB)
sin comprimir y el CAB de origen `310544938` bytes (aproximadamente 310 MB). El host publicado
puede ejecutarse sin instalar .NET ni WebView2 compartidos. La construcción sí
necesita el SDK de .NET y acceso a las fuentes de paquetes declaradas.

## Construir

Desde la raíz de esta copia de nova-min, en PowerShell:

```powershell
& build/browser/venv/Scripts/python.exe scripts/package_browser_windows.py --download
```

El comando usa el entorno Python de construcción preparado para este trabajo.
También puede usarse un Python compatible del desarrollador. `--download` autoriza
la descarga del CAB declarado si falta; para usar uno ya descargado:

```powershell
python scripts/package_browser_windows.py --runtime-archive C:/ruta/Microsoft.WebView2.FixedVersionRuntime.155.0.4283.45.x64.cab
```

El builder rechaza un destino existente. Para otra compilación se elige un nuevo
`--output` dentro de `dist/`. La ejecución normal del servicio no descarga motores,
drivers o dependencias.

## Smoke nativo explícito

Desde la raíz de nova-min, seleccionar el Python compatible existente y ejecutar:

```powershell
$novaPython = (Get-Command python -ErrorAction Stop).Source
& $novaPython scripts/smoke_browser_block1.py --package-dir dist/browser/windows-x64
```

También puede asignarse a `$novaPython` la ruta explícita del intérprete de Nova.
Para este smoke no es necesario instalar Playwright en ese intérprete: se carga
la copia incluida en el paquete.

El resultado se escribe por defecto en un directorio temporal nuevo con prefijo
`nova-browser-block1-result-`. Para conservar evidencia de una ejecución concreta:

```powershell
& $novaPython scripts/smoke_browser_block1.py --package-dir dist/browser/windows-x64 --output docs/active_web_reimplementation/bloque_1_host_runtime/runs/native-smoke-03.json
```

`--output` acepta únicamente un archivo nuevo bajo el temporal del sistema o este
directorio del bloque. No sobrescribe receipts. El código de salida es `0` para
PASS y `1` para FAIL. Un paquete, runtime, driver o plataforma ausentes producen
FAIL en esta ejecución explícita; nunca un skip que parezca un smoke aprobado.

El contrato equivalente de pytest es
`tests/browser_block1/test_native_smoke.py::test_windows_packaged_host_render_click_and_cleanup`.
Requiere infraestructura Windows y paquete completo; su clasificación es manual,
separada del CI portátil. `NOVA_BROWSER_BLOCK1_PACKAGE` permite indicar otro paquete.
Ejemplo directo, con pytest instalado en el entorno de pruebas:

```powershell
& $novaPython -m pytest -q tests/browser_block1/test_native_smoke.py
```

La entrada positiva del CI existente es `ci/run_contracts.py --job browser-block1
--special --output <directorio-nuevo-fuera-del-checkout>`. Requiere pytest en el
intérprete de validación. `--collect-only` comprueba la selección sin arrancar el
host; no es evidencia de ejecución nativa.

La entrada manual también pasó con un perfil Windows temporal coherente, sin
usar los directorios personales del usuario. Los detalles y el intento previo
fallido por la estructura de ese entorno están en `resultados.md`.

## Qué comprueba

1. Carga el servicio de esta copia y Playwright/driver desde `python/` del paquete;
   comprueba versiones y los hashes del apphost `.exe` y assembly `.dll` contra
   su receipt de construcción.
2. Lanza el `.exe` del host con `PATH` limitado a System32 y `DOTNET_ROOT` apuntando
   a una ruta propia inexistente. No hay un `dotnet.exe` resoluble en ese entorno.
3. Confirma mediante Windows la ruta real del host, su parentesco con el proceso
   Python y la ruta real del proceso WebView2 dentro del runtime incluido.
4. Confirma un listener CDP sólo en loopback y perteneciente al árbol del host.
5. Sirve exclusivamente `tests/browser_block1/owned_page.html` desde un servidor
   propio en `127.0.0.1` y puerto efímero. Navega con Playwright, espera una mutación
   DOM por temporizador, lee el texto renderizado, pulsa un botón y lee `Clicks: 1`.
6. Cierra la sesión en `finally`, verifica el job vacío y perfil eliminado, espera
   la salida de handles de los procesos observados (incluido el driver Playwright),
   comprueba que CDP dejó de escuchar y cierra el servidor HTTP propio.

La limpieza precede a la escritura del receipt. Una limpieza de emergencia no
convierte en PASS una ejecución que dejó procesos. El receipt conserva versiones,
hashes, comprobaciones y códigos acotados; no guarda tokens del canal, perfiles,
entorno, transcripciones del host, mensajes de excepción o contenido de páginas.

La página usa navegación HTTP y JavaScript normales. El navegador conserva su red
normal; este smoke no afirma aislamiento universal, funcionamiento con sitios
públicos, ausencia de CAPTCHA, integración con el modelo ni aceptación de bloques
posteriores. No reutiliza resultados ni escribe sobre campañas históricas.

## API interna disponible

`local_cli.application.browser` define el puerto, resultados de navegación/lectura,
errores `BrowserUnavailable` y receipt de cierre. La implementación Windows es
`local_cli.infrastructure.browser.windows_webview2.WebView2BrowserSession`:

```python
from pathlib import Path
from local_cli.infrastructure.browser.windows_webview2 import WebView2BrowserSession

with WebView2BrowserSession(Path("dist/browser/windows-x64")) as browser:
    browser.navigate("http://127.0.0.1:PUERTO/owned.html")
    reading = browser.read(max_chars=16000)
```

`page` y `ready` están disponibles para infraestructura de confianza del bloque.
No son un catálogo de herramientas del modelo. Los fallos portátiles de paquete,
runtime y dependencia se prueban sin iniciar motores reales; sus resultados no
sustituyen el smoke nativo.

En este bloque la ventana inicial permanece oculta, los permisos de sitio y
las aperturas de aplicaciones externas se deniegan, y las descargas se cancelan
para evitar escrituras en Downloads antes de implementar transferencias propias
en el Bloque 5. Las herramientas productivas del modelo pertenecen al Bloque 2.

Los resultados y limitaciones observados pertenecen a `resultados.md` y a los
receipts nuevos que allí se enlacen.
