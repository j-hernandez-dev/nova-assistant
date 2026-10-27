# Distribución Windows de Nova 0.13.0

Revisión local: 26 de octubre de 2026, America/Mexico_City.

El instalador NSIS x64 incluye Electron, el backend `nova-backend.exe` con Python y sus dependencias, y el componente de navegación WebView2 Fixed Version con su host .NET autocontenido y el driver Playwright. **Ollama y los modelos siguen siendo requisitos externos.** No se descargan ni se instalan modelos al abrir Nova.

## Compilación

Se necesita Windows x64, Python 3.14 x64, Node.js 22.12 o posterior y el SDK .NET 10. Desde `desktop`, ejecutar `npm ci` y `npm run build:win`. El script también acepta los argumentos anteriores `--publish never --config.directories.output=release`; nunca publica.

El entorno de compilación Python queda en `build/windows/python`, con versiones fijadas en `packaging/windows/requirements-build.txt`. El backend se compila con PyInstaller en modo carpeta: mantiene stdin/stdout para el protocolo JSONL y no extrae el intérprete en cada arranque. El componente nativo se prepara con el manifiesto de dependencias existente y verifica el archivo WebView2 por tamaño y SHA256 antes de usarlo.

Salidas generadas, excluidas de Git:

- `dist/windows-backend/nova-backend/`: ejecutable y bibliotecas del backend.
- `dist/windows-browser/windows-x64/`: host nativo, WebView2 y Playwright.
- `desktop/release/Nova-0.13.0-windows-x64-setup.exe`: instalador de distribución.
- `desktop/release/windows-build.json`: versión, tamaño, SHA256 y requisitos externos.

## Comportamiento instalado

En Windows, Electron inicia exclusivamente `resources/backend/nova-backend.exe --server`. No descubre Python del sistema ni una virtualenv; si falta el ejecutable informa la desconexión. El entorno heredado de Python/PyInstaller se limpia y se conserva la clave de aprobación creada por el host.

El navegador se encuentra mediante la ubicación del ejecutable instalado, independientemente del directorio actual. Una instalación nueva crea su proyecto predeterminado en `Documentos/Nova/workspace`, fuera de la carpeta de instalación. Se respetan los proyectos existentes del perfil. Desinstalar conserva documentos y datos del usuario.

El backend congelado rechaza las actualizaciones por Git/pip: se actualiza mediante el instalador. La ruta de desarrollo conserva la virtualenv del checkout y su flujo anterior.

## Verificación explícita del runtime

`nova-backend.exe --runtime-info` prueba NumPy, una escritura/lectura de PDF en memoria y SQLite, y comunica la versión y presencia de los componentes. No consulta datos del usuario ni un modelo.

`nova-backend.exe --check-browser` abre únicamente una página HTTP propia en loopback, verifica navegación y un campo de formulario, y comprueba el cierre del host, su job y su perfil temporal. No visita sitios externos ni ejecuta acciones propuestas por un LLM. Son comprobaciones explícitas de empaquetado, separadas del protocolo normal `--server`.

## Alcance de las pruebas

La prueba funcional NSIS usa una identidad de QA, nombre de proceso y directorio de instalación separados, sin accesos directos ni ejecución al terminar la instalación. El wrapper de QA usa compresión `store` para la prueba; el instalador de producción mantiene su compresión normal. Así no reemplaza ni cierra la instalación habitual de Nova. Los hashes del renderer, backend, host WebView2, runtime y driver se comparan con los del paquete de producción. La aplicación sigue en modo `app.isPackaged`; el harness redirige sus carpetas conocidas antes de cargar el código de producción y retira los intérpretes del PATH.

Se comprueban instalación, carga del backend real por JSONL, versión a través del preload/IPC, guardado de preferencias, ubicación escribible del proyecto, navegación local, cierre, desinstalación y conservación de perfil/documentos. Los datos son sintéticos y las comprobaciones no realizan inferencia real. El informe de resultados registra los hashes exactos del candidato.

## Firma y Control de aplicaciones

**El instalador no está firmado.** Dos intentos del instalador real en Windows Sandbox sin red fueron bloqueados por Control de aplicaciones, tanto desde la carpeta compartida como desde una copia local con el mismo SHA256. Esos intentos permanecen registrados como fallidos; no se cuentan como instalaciones satisfactorias en un Windows limpio.

El usuario indicó que no dispone de certificado y autorizó continuar con las pruebas funcionales aisladas. No se desactivaron políticas del host, no se añadieron exclusiones ni se importaron certificados de confianza. Las pruebas funcionales se realizan en el Windows del host con identidad y datos de QA independientes. No sustituyen la aceptación de una firma por Smart App Control ni una certificación de todos los entornos Windows.

Microsoft describe la necesidad de firmar código para su aceptación por Smart App Control en su [documentación de desarrollo](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview). Una distribución firmada requiere un certificado o servicio de firma apropiado; este candidato conserva explícitamente la limitación de no estar firmado.

## Integridad de Git y publicación

La extracción del commit reveló conversiones CRLF/LF en ocho archivos históricos de Memoria fijados por hash. Se conservaron los bytes originales verificados del worktree y se añadieron reglas `-text` explícitas, sin cambiar fixtures, hashes esperados ni guardas. Una prueba con un índice Git desechable y `core.autocrlf=true` verifica que se almacenan los mismos bytes. Para preparar el siguiente commit conviene ejecutar `git add --renormalize -- tests/memory_v1` después de añadir `.gitattributes`.

El instalador, su checksum y los recibos van como archivos de la Release, no en el historial Git. Esta preparación no crea commits, pushes, etiquetas ni Releases. Los cambios de empaquetado deben confirmarse antes de etiquetar; se debe construir y probar el candidato correspondiente a ese commit.

## Resultado del candidato

- Instalación, ejecución y desinstalación aisladas: **PASS**, con los mismos bytes de aplicación, backend y navegador del paquete final.
- Regresión: **6,084 aprobados**, 7 omitidos por condiciones existentes y 0 fallos; Core añade 69 subpruebas aprobadas. Auditoría npm: 0 avisos.
- Tamaño del instalador: **457,393,466 bytes** (436.2 MiB).
- SHA256: `20a8aa68fcba17cabc1f4b29cf60f1b82834627a505dd0ee7c01e1a97805b94d`.
- Windows Sandbox: **BLOCKED_UNSIGNED**, sin instalación limpia satisfactoria ni cambios de políticas.

Recibo público sin rutas de perfiles: [windows-installer-0.13.0.json](windows-installer-0.13.0.json). El candidato incluye cambios de empaquetado posteriores a la base `f986688`; hay que confirmar los cambios y volver a construir desde ese commit antes de etiquetar o publicar.
