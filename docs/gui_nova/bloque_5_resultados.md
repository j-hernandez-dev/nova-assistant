# GUI-B5 — Proyectos y explorador de Nova

Fecha: 2026-10-16. Proyecto: `nova-min/nova-assistant`.

## Resultado

El panel de Proyectos administra un único workspace efectivo y recuerda las carpetas añadidas. El host resuelve el proyecto predeterminado como `<NovaRoot>/workspace/`, independiente de la carpeta desde la que se lance Electron. No concede acceso predeterminado a todo el código fuente de Nova.

| Acción | Resultado |
|---|---|
| Añadir | Selector nativo, validación y cambio confirmado por Application. La carpeta queda recordada. |
| Cambiar | El menú de tres puntos permite sustituir la carpeta seleccionada. Cancelar mantiene el proyecto anterior. |
| Seleccionar | Activa una carpeta recordada, con un solo árbol de proyecto activo. |
| Quitar | Retira la entrada, sin borrar archivos. Si estaba activa, primero confirma el cambio al predeterminado. |
| Abrir en el Explorador | El host abre la carpeta confirmada mediante la API del sistema, sin construir comandos shell. |
| Árbol y vista previa | Navegación local, lectura acotada y errores ES/EN. No se ejecuta el contenido de los archivos. |

Inicio, Historial, conversación compartida, mensajes sin leer y permisos de GUI-B4 conservan su sesión. Cambiar proyecto no inicia un segundo agente ni borra la conversación.

## Autoridad y persistencia

La ruta activa procede del snapshot de Application. El registro Desktop recuerda carpetas, pero no es una autorización multi-root. El selector y las operaciones de proyecto pertenecen al host; React proyecta su resultado confirmado.

Se corrige el relevo del contexto al cambiar de proyecto: el runtime no puede conservar la autoridad filesystem ligada a la raíz anterior. Las operaciones nuevas deben nacer con el contexto del nuevo workspace. Policy, Approval y Grant mantienen su evaluación ordinaria; no se convierten permisos anteriores en permisos del nuevo proyecto.

Los cambios incompatibles con ejecución o interacción pendiente se rechazan antes de alterar la carpeta activa. Una ruta inaccesible, un cambio rechazado, una desconexión o un fallo de persistencia deben explicarse; no se presentan como un cambio exitoso.

Las lecturas del explorador verifican el sender/main frame de Desktop y la pertenencia a la raíz canónica activa. Un enlace que escape de la raíz, una respuesta de un proyecto anterior o una petición de otra ventana no habilita una vista previa. El contenido se representa como texto.

La carpeta `workspace/` contiene datos del usuario y se excluye del versionamiento, al igual que los artefactos de la fixture de GUI-B5. Quitar una carpeta no elimina sus datos ni sus conversaciones guardadas. No se migra configuración personal ni se cambia el idioma de CLI.

La carpeta predeterminada administrada se conserva como destino de retorno y no se puede quitar del registro. Las demás pueden retirarse. El registro se guarda en `%APPDATA%/nova-desktop/project-preferences.json`; sus entradas no autorizan lecturas simultáneas de todas esas raíces.

El arranque confirma el workspace antes de publicar disponibilidad de chat. Si el predeterminado es inaccesible, el panel permite elegir otra carpeta explícitamente. Una carpeta anterior desaparecida produce un aviso. El inicio y los cambios de carpeta ofrecen restaurar las conversaciones guardadas; no las restauran automáticamente. El reinicio explícito del backend conserva su recuperación anterior de transcript, sin reanudar efectos.

Las páginas del explorador contienen hasta 500 entradas; el offset está acotado a 100000 y se informa al alcanzar el límite. La vista previa admite texto UTF-8 de hasta 1000000 bytes, rechaza contenido binario y no renderiza HTML. Las respuestas tardías de otra raíz se descartan. Al terminar una acción, incluso si se cancela el picker, se refrescan una vez las lecturas de presentación invalidadas; no se repite la acción.

## Verificación

- **183/183 pruebas Node PASS** en las 18 suites ordinarias de Desktop. B5 añade 20 contratos de host/cliente y 7 de presentación: confirmación de ruta, cancelación, cambio rechazado, retiro sin borrado, fallback, persistencia, errores, paginación, raíz sustituida por enlace y previews fuera de scope.
- **253 pruebas Python PASS, 2 SKIP** en la regresión focal de Proyectos, GUI-B2–B4, sesión, eventos, ToolRuntime, interacciones, providers, Desktop, procesos, Policy/Approval/Grant y redacción. B5 aporta 15 ejecuciones de 10 funciones estáticas, incluyendo un `JsonLineServer` real con archivos owned y un turno posterior en el nuevo proyecto. Las dos omisiones son perfiles manuales Electron/Ollama existentes.
- Regresión adicional del backend: **98 PASS, 1 SKIP**. Se acotó PATH sólo dentro del proceso pytest para evitar que la búsqueda del ejecutable `bash` sintético de un test recorriera un PATH lento; no se modificaron Policy ni su timeout.
- Las pruebas Node que crean junctions requirieron ejecución fuera del sandbox de herramientas; el intento inicial fue rechazado con EPERM. La regresión Python del destino también se repitió con ese permiso: el sandbox había impedido restaurar el cwd del proyecto tras una fixture (`WinError 5`). La ejecución final del destino obtuvo **253 PASS, 2 SKIP**. No se añadió excepción de acceso al producto.
- **TypeScript y bundles Vite PASS**, sin electron-builder ni empaquetado. Tras los dos ajustes finales de mensajes y el refresco de previews se repitieron las 7 pruebas de presentación, TypeScript y el build.
- Inventario CI: **3945 contratos estáticos**, incluyendo GUI_PROJECTS y sus 10 funciones; 18 suites Node ordinarias. No se añaden GUI/Ollama a CI ordinario.
- Comprobación visual en Electron real a **1280×820** y **600×400**, con perfil propio y carpetas owned: abrir drawer, añadir, ver árbol y README real, desplegar menú y mantener compositor y cierre accesibles. Se corrigió una superposición del árbol con el compositor al ancho mínimo. El selector y la apertura del Explorador se verificaron mediante puertos deterministas del host; la fixture visual no cambió preferencias personales ni abrió carpetas ajenas.
- Copia al proyecto destino con preflight de hashes de todos los archivos y verificación posterior. Los **1626 documentos anteriores** permanecen byte-intactos.

## Archivos afectados

- Presentación: `desktop/src/App.tsx`, `components/FileExplorer.tsx`, `components/FileViewer.tsx`, `project_presentation.ts`, `types.ts`, `i18n.tsx`, `styles.css`.
- Host: `desktop/electron/projects_host.cjs`, su declaración, `main.ts`, `preload.ts`, `application_client.ts` y `desktop/vite.config.ts`.
- Application/composición: `local_cli/application/session.py`, `local_cli/bootstrap_server.py`, `local_cli/server.py`.
- Tests nuevos: `desktop/tests/projects_host.test.cjs`, `projects_client.test.cjs`, `project_presentation.test.cjs`, `tests/test_gui_projects.py`.
- Inventario/CI existentes, `.gitignore` y este informe nuevo.

## Alcance

Sin nuevas capacidades del agente, voz, MCP, nuevas reglas de routing ni cambios de primitivas Browser/network. No se empaquetan ejecutables ni se ejecuta electron-builder. Las pruebas de presentación usan datos owned; no son una campaña de calidad del modelo.

La evidencia y documentación anteriores se verifican por SHA-256. No se reescriben resultados históricos. No se realiza staging Git, commit, push, tag ni release.
