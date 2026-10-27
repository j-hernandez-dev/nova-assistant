# Nova

**0.13.0 · Asistente de IA local para proyectos, archivos, fuentes y recuerdos.**

Nova combina una interfaz de escritorio con modelos de Ollama y herramientas para leer y modificar archivos, ejecutar comandos y consultar la web. El modelo propone las acciones; el host comprueba sus permisos y solicita las autorizaciones correspondientes. La interfaz está disponible en español e inglés.

Esta versión reúne la reconstrucción de Nova Desktop. Desktop y la CLI comparten el backend Python de Application. Los identificadores `local-cli`, `local_cli`, `local-cli-desktop` y el identificador de Electron se conservan por compatibilidad con instalaciones y perfiles existentes.

## Qué incluye

- **Proyectos:** carpetas independientes, historial de conversaciones, panel lateral redimensionable y visor con pestañas de archivos, fuentes y recuerdos.
- **Modelos LLM y EM:** detección por capacidades, selección de modelos instalados, activación individual, contexto automático o manual y estadísticas de uso separadas.
- **Catálogo de Ollama:** Todos, Instalados y Para ti; búsqueda, variantes y descarga explícita. Las recomendaciones consideran la memoria disponible y son estimaciones.
- **Fuentes:** archivos copiados a Nova y URL importadas por proyecto. Puedes seleccionarlas para el siguiente mensaje, verlas, descargarlas, cambiar su vínculo o eliminarlas.
- **Conocimiento:** recuperación léxica y semántica del proyecto, indexación automática y reconstrucción del índice. Las opciones semánticas requieren un modelo EM instalado, habilitado y disponible.
- **Recuerdos:** consulta, creación manual, edición en tabla, eliminación y propuestas de captura automática; importación y exportación con confirmaciones para contenido sensible.
- **Almacenamiento:** medición del espacio de los datos de Nova, acceso a sus carpetas y administración de copias de archivos por proyecto o sin vínculo.
- **Web:** permisos independientes de lectura, búsqueda y navegación; Google, Bing o DuckDuckGo y WebView2, Chrome o Edge, según disponibilidad.
- **Interfaz:** cuatro temas claros y oscuros, fuentes de interfaz y código, mascotas Nova 2D y Nova 3D, transiciones opcionales, zoom del 50 al 150 %, menús y atajos configurables.

Windows es la plataforma de escritorio y navegación validada localmente. Los contratos Python portables tienen cobertura de CI en Windows, Linux y macOS; eso no equivale a validar la GUI ni la navegación nativa en esos sistemas. La entrega 0.13.0 se prepara como **código fuente**: el build de comprobación no genera ni publica un instalador.

## Ejecutar Nova Desktop desde el código

Necesitas Git, Python 3.10 o posterior, Node.js 22.12 o posterior con npm y Ollama en ejecución. CI usa Python 3.14 y Node.js 24. Instala un modelo de conversación compatible con herramientas en Ollama; Nova no lo descarga al arrancar. El modelo predeterminado es `qwen3.5:9b`, pero debes elegir uno adecuado para tu equipo.

Desde PowerShell:

```powershell
git clone https://github.com/j-hernandez-dev/nova-assistant.git
Set-Location nova-assistant
python -m venv .venv
$novaPython = Join-Path $PWD ".venv\Scripts\python.exe"
& $novaPython -m pip install -e ".[browser]"
Set-Location desktop
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

`npm run dev` abre Nova y arranca su backend. Mantén abierta esa terminal. En los siguientes arranques basta con ejecutar ese comando desde `desktop`. Node debe estar en el PATH para los procesos que npm inicia.

Desktop selecciona la `.venv` de este checkout, aunque haya otro entorno Python activado. El registro de inicio indica el intérprete y la carpeta utilizados. Si antes instalaste otra copia, reinstala el paquete editable desde el checkout correcto y comprueba su procedencia:

```powershell
# Desde la raíz del repositorio
& .\.venv\Scripts\python.exe -c "import local_cli; print(local_cli.__file__)"
```

Si un PATH demasiado largo impide encontrar `node`, `tsc` o `vite`, puedes limitarlo en esta terminal, sin cambiar las variables guardadas de Windows:

```powershell
$env:Path = "C:\Program Files\nodejs;$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\WindowsPowerShell\v1.0;C:\Program Files\Git\cmd"
npm.cmd run dev -- --host 127.0.0.1
```

Si tu versión de npm bloquea los scripts de instalación de Electron o esbuild, autoriza esas dependencias según el aviso de npm. Para recuperar un binario de Electron ausente, ejecuta `node .\node_modules\electron\install.js` desde `desktop`.

### Componente de navegación

WebView2 necesita el componente preparado en `dist/browser/windows-x64/`, que incluye el host, su runtime y las dependencias de automatización. Es salida generada y está excluida de Git. **Instalar el extra Python `browser` no crea este componente.** Una copia limpia sin él puede usar archivos, terminal y las demás funciones disponibles, pero no debe anunciar navegación WebView2 lista.

Las versiones y el origen de estas dependencias están en [native/browser-dependencies.json](native/browser-dependencies.json). Consulta también [native](native/) y los [scripts de preparación](scripts/). Chrome y Edge son alternativas explícitas cuando están instalados y sus requisitos están disponibles. Nova no instala ni cambia de navegador silenciosamente.

## Proyectos, fuentes y contexto

Añade una carpeta con Proyectos o **Archivo → Nuevo proyecto…**. El proyecto inicial es `<checkout>/workspace/`. El panel de contenido tiene Archivos, Fuentes y Recuerdos. General permite ocultarlo para dedicar todo el panel a la lista de proyectos.

Hay dos formas complementarias de usar las fuentes:

1. **Selección explícita para un mensaje:** marca sus casillas en el panel lateral. Aparecen encima del campo de escritura y puedes retirarlas con la ×. Un archivo añadido desde el selector o arrastrado al chat se copia a Nova, se vincula al proyecto y queda seleccionado para el mensaje.
2. **Recuperación automática:** Conocimiento configura qué fragmentos del proyecto se recuperan por coincidencia de palabras o similitud semántica. Es independiente de la selección explícita.

Los textos seleccionados que caben en el presupuesto de contexto se incluyen completos; los mayores se preparan por fragmentos. `source_read` permite al modelo leer más de la copia autorizada durante ese turno. Seleccionar una fuente no copia el archivo al directorio de trabajo ni garantiza que todo el documento quepa en un solo contexto.

Las referencias muestran la fuente y su ubicación legible. Validar `[K1]`, `[K2]`, etc. comprueba referencias estructurales del turno, no la veracidad de cada afirmación. Identificadores inventados o rangos como `[K1-K10]` pueden producir un aviso de referencia no verificable. Nova no reescribe la respuesta para ocultarlo.

## Modelos locales

Modelo LLM contiene los modelos de conversación y Modelo EM los de embeddings. La clasificación de modelos instalados utiliza las capacidades que comunica Ollama; el nombre comercial no basta para identificar un embedding.

| Modelo | Valores manuales de contexto | Predeterminado |
| --- | --- | --- |
| LLM | 4K, 8K, 16K, 32K, 64K, 128K, 256K | Automático |
| EM | 512, 1K, 2K, 4K, 8K, 16K, 32K | Automático; todos los EM habilitados |

Estos valores no amplían los límites del modelo ni la memoria del equipo. Nova informa los errores de contexto y ejecución. En un embedding, el contexto limita cada texto de entrada; no representa un historial de conversación ni tokens de respuesta.

El catálogo público se consulta en Ollama y conserva metadatos en caché. Sin conexión puede usar la información guardada e indicar que está desactualizada. Descargar, eliminar y usar modelos son acciones explícitas. Los pesos los administra Ollama y no se suman al almacenamiento de Nova.

## Recuerdos

La **recuperación** consulta recuerdos existentes; la **captura** crea recuerdos o candidatos:

- Recuperación léxica: palabras y términos coincidentes; activada por defecto.
- Recuperación semántica: similitud mediante embeddings; desactivada por defecto y dependiente de un EM disponible.
- Captura automática: activada por defecto en **Guardado de bajo riesgo**. **Sólo proponer** deja candidatos para revisión en Propuestas pendientes.
- Captura manual: permite elegir tipo, ámbito del proyecto actual o perfil personal y clasificación sensible.

Memoria permite autorizar el acceso a recuerdos sensibles por proyecto con confirmación. Mostrar, escribir o exportar contenido sensible conserva sus confirmaciones correspondientes. No hay una opción de Memoria en contexto remoto.

Importar reemplaza los recuerdos actuales después de confirmarlo. Exportar permite incluir contenido sensible sólo con confirmación. Los archivos exportados contienen datos del usuario: guárdalos fuera del repositorio.

## Configuración y atajos

| Grupo | Secciones |
| --- | --- |
| Interfaz | General, Apariencia, Atajos |
| Modelos | Modelo LLM, Modelo EM |
| Contexto y herramientas | Memoria, Conocimiento, Web |
| Proyectos y datos | Proyectos, Chats, Almacenamiento |
| Acerca de | Versión, derechos de autor, backend, proveedor y herramientas |

Los ajustes se guardan al aplicarlos. Restablecer recupera los valores de la sección; Almacenamiento usa **Actualizar** para volver a medir. El idioma puede seguir al sistema o fijarse en español o inglés. No traduce los chats ni cambia las respuestas del modelo.

Atajos iniciales de Windows, configurables en Atajos:

| Acción | Atajo |
| --- | --- |
| Proyectos | Ctrl+B |
| Fuentes | Ctrl+Shift+F |
| Recuerdos | Ctrl+Shift+N |
| Modelos | Ctrl+Shift+M |
| Configuración | Ctrl+, |
| Enfocar el mensaje | Ctrl+L |
| Historial | Ctrl+Shift+H |
| Adjuntar archivo | Ctrl+Shift+A |
| Añadir proyecto | Ctrl+Shift+O |
| Cerrar visor | Ctrl+Shift+W |
| Enviar / nueva línea / detener | Enter / Shift+Enter / Escape |

## Datos y almacenamiento

Ubicaciones predeterminadas; los overrides del backend están en [local_cli/config.py](local_cli/config.py):

| Datos | Ubicación |
| --- | --- |
| Preferencias Desktop, proyectos, apariencia y atajos | `%APPDATA%\nova-desktop\` |
| Configuración Python | `%USERPROFILE%\.config\nova\config` |
| Conversaciones, sesiones, recuerdos, copias de fuentes e índices | `%USERPROFILE%\.local\state\nova\` |
| Auditoría de seguridad | `%LOCALAPPDATA%\Nova\security_audit\v1\` |
| Catálogo de modelos | `%USERPROFILE%\.cache\nova\` |
| Navegación y descargas retenidas | Carpetas administradas de navegación; Almacenamiento muestra las rutas efectivas |
| Planes y Knowledge legado | `.agents/` del proyecto |

Almacenamiento desglosa chats, adjuntos, recuerdos, navegación, configuración, auditoría, catálogo y cachés. Excluye la instalación y los pesos de Ollama. Actualizar recalcula tamaños e inventario.

Adjuntar un archivo crea una **copia persistente**. Mover o renombrar el original no rompe esa copia. Puedes descargarla con Guardar como, desvincularla, cambiarla de proyecto o eliminarla. Quitar un proyecto conserva sus copias en **No vinculado**, salvo que confirmes eliminar sus archivos asociados. Eliminar la copia de Nova no elimina el original.

La limpieza de carpetas explica sus efectos y pide reiniciar cuando el almacén está en uso. Las operaciones pendientes se conservan en `nova-storage-control`, junto al perfil, hasta completarse. No borres manualmente almacenes activos.

## Permisos y recuperación

Nova puede leer, escribir, editar, listar y buscar archivos; ejecutar comandos; consultar páginas y manejar un navegador. Los permisos web son independientes de las aprobaciones de acciones. La búsqueda usa Google por defecto; Bing y DuckDuckGo son alternativas.

La política, las aprobaciones y las concesiones de un solo uso median los efectos. El shell y el navegador operan con los permisos normales de la cuenta. Los perfiles de navegador son propios y temporales; no se usa el perfil personal de Chrome o Edge. Esto no ofrece aislamiento completo de procesos o red. La protección de valores sensibles tiene límites explícitos y no equivale a cifrado ni borrado forense.

Las acciones fallidas o inciertas no se convierten en éxito mediante la respuesta del modelo. Cancelar no deshace lo realizado. Las operaciones y aprobaciones interrumpidas no se reproducen automáticamente al reiniciar el backend. El borrador sin enviar y el historial guardado se conservan.

Desktop admite una instancia por perfil y regenera sus cachés desechables de Chromium antes del arranque. Conserva una copia anterior en `.chromium-cache-backup` sin borrar cookies, localStorage, preferencias, chats o recuerdos. Si una caché está bloqueada, evita su uso persistente en ese arranque. Esto reduce los problemas tras cierres abruptos, pero no sustituye una copia de seguridad.

Detalles: [ejecución de aplicaciones](docs/application_launch.md), [navegación](docs/active_web_reimplementation/) y [límites de seguridad](docs/security_v12/s8_limits.md).

## CLI

```powershell
# Desde la raíz del checkout
& .\.venv\Scripts\python.exe -m local_cli --provider ollama --select-model
```

`--help` describe los argumentos y `/help` los comandos. Entre ellos: `/models`, `/model`, `/browser`, `/search`, `/fetch`, `/attach`, `/source`, `/rag`, `/memory`, `/context` y `/usage`. `/fetch on|off|status` controla lectura HTTP separada de navegación. Los mensajes de sistema de la CLI están en inglés; el modelo puede responder en tu idioma.

## Comprobaciones de desarrollo y versión

Desde la raíz, con el entorno Python preparado:

```powershell
$novaPython = Join-Path $PWD ".venv\Scripts\python.exe"
& $novaPython -m pip install -e ".[browser,memory-semantic]" pytest pytest-subtests
& $novaPython -B ci/release_check.py --tag v0.13.0
& $novaPython -B ci/contract_inventory.py
$run = Join-Path $env:TEMP ("nova-preflight-" + [guid]::NewGuid().ToString("N"))
& $novaPython -B ci/run_contracts.py --job core --output "$run\core"
& $novaPython -B ci/run_contracts.py --job security --output "$run\security"
& $novaPython -B ci/run_contracts.py --job memory --output "$run\memory"
& $novaPython -B ci/run_contracts.py --job knowledge --output "$run\knowledge"
Set-Location desktop
npm.cmd ci
npm.cmd audit --audit-level=low
npm.cmd test
npm.cmd run build:source
```

Los resultados de contratos van a directorios nuevos, propios y fuera del checkout. El inventario distingue pruebas actuales, artefactos históricos y comprobaciones nativas o con modelos reales. No ejecutes todas las campañas históricas como si certificaran el código actual.

`npm test` ejecuta todas las suites ordinarias `.test.cjs` y exige que coincidan con el inventario de CI. `build:source` verifica TypeScript y construye renderer, proceso principal y preloads; **no ejecuta electron-builder**. Los scripts `build` y `build:win|mac|linux` sí empaquetan y requieren una validación de distribución separada.

Para comprobar la versión visible con Electron y el backend sintético, usa un directorio nuevo fuera del checkout:

```powershell
# Desde la raíz, después de build:source
$nativeRun = Join-Path $env:TEMP ("nova-about-" + [guid]::NewGuid().ToString("N"))
node desktop/tests/run_gui.cjs --case about-version --output "$nativeRun" --python "$novaPython"
```

El launcher da a la aplicación de prueba la versión real del paquete y crea un perfil privado. También admite `question-host` y `resume-recovery`; estos casos usan un backend programado, sin inferencia real ni datos de tu perfil.

Las pruebas Electron y las campañas con modelos o navegación reales son comprobaciones explícitas con perfiles propios. Consulta los [resultados y límites de 0.13.0](docs/releases/0.13.0.md). Las evidencias anteriores, incluidas las fallidas o parciales, permanecen en [docs](docs/) con su alcance original.

## Licencia y origen

MIT; consulta [LICENSE](LICENSE). Nova se desarrolla sobre el proyecto original [local-cli de lutelute](https://github.com/lutelute/local-cli); se conserva la atribución de sus contribuciones.
