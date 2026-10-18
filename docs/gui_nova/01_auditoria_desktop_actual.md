# Auditoría del Desktop actual y base para la GUI de Nova

Fecha: 2026-10-15. Proyecto auditado: `C:\Users\joseh\Downloads\nova-min\nova-assistant`.

## 1. Alcance y resultado

Esta es una auditoría de código para preparar la refactorización visual solicitada. Se revisaron React, Electron, su puente con Python y las operaciones que ya ofrece Application. Se contrastaron con las siete referencias visuales aportadas por el usuario.

**Conclusión:** conviene sustituir la presentación actual y conservar el backend, el ciclo del agente, las herramientas y los servicios de modelos, archivos, Memory y Knowledge. El cambio necesita algunas proyecciones y operaciones de host pequeñas; no puede resolverse íntegramente con CSS.

Los puntos que requieren atención antes de presentar la GUI como terminada son:

1. El `ready` actual confirma la recepción de un snapshot, no la disponibilidad de Ollama y del modelo.
2. El resultado visual de una herramienta pierde información y puede aparecer como «Done» aunque haya fallado o su efecto sea incierto.
3. La aprobación inline provoca una segunda confirmación nativa. Eliminarla directamente suprimiría una comprobación de consentimiento existente.
4. No existen todavía la vista compacta, el contador de respuestas sin leer, el proyecto administrado predeterminado ni preferencias ES/EN de Desktop.
5. El actualizador y parte de la identidad siguen apuntando a Local CLI upstream.

La propuesta y sus bloques están en [02_propuesta_gui_nova_y_bloques.md](02_propuesta_gui_nova_y_bloques.md).

## 2. Método y límites de esta revisión

- Inspección de fuentes y pruebas existentes; contraste de frontend, puente y Application.
- Referencia de código obtenida mediante `git log`: `b4a1706 — feat: integrate browser navigation and stabilize CLI`. Los hallazgos corresponden a los archivos presentes, no únicamente a ese commit.
- La comprobación de `git status` de esta revisión devolvió «this operation must be run in a work tree»; no se afirma que el checkout esté limpio ni se propone reparar Git dentro de esta tarea.
- No se inició Electron, Ollama ni una campaña de modelo real. No se ejecutaron suites de pruebas ni instalaciones. Los tests citados son infraestructura reutilizable, no resultados nuevos de aceptación.
- No se modificó producto, configuración personal ni evidencia histórica. La entrega consiste exclusivamente en estos dos documentos.

El proyecto `C:\Users\joseh\Downloads\nova-assistant` es otra ubicación y no es el Desktop objeto de esta propuesta.

## 3. Arquitectura que existe

| Capa | Implementación observada | Decisión recomendada |
|---|---|---|
| Renderer | React 19 y TypeScript; `App.tsx` compone conversación, explorador, visor, selector de modelos y ajustes. | Reorganizar en shell, vistas y modales de Nova. |
| Presentación | CSS con variables, tipografía monoespaciada, fondo oscuro y acento azul. | Sustituir tokens y composición por fondo azul casi negro, ámbar y superficies de las referencias. |
| Host Desktop | Electron 33; `contextIsolation: true`, `nodeIntegration: false`; inicia Python en modo servidor. | Conservar aislamiento y puente; retirar menubar desde Electron. |
| Cliente de Application | Proyección de snapshots/eventos con cursor, identidad de sesión y manejo de desconexión. | Reutilizar como fuente única de estado de conversación. |
| Backend | Application compartida y servicios existentes de sesión, proveedores y herramientas. | Conservar decisiones y ejecución en backend. |
| Servicios auxiliares | Catálogo de modelos, recomendaciones, descarga; Memory; documentos/Knowledge; RAG; controles web actuales. | Reorganizar acceso visual sin volver a implementarlos. |

Fuentes: [package.json](../../desktop/package.json), [App.tsx](../../desktop/src/App.tsx#L467), [styles.css](../../desktop/src/styles.css), [main.ts](../../desktop/electron/main.ts#L311), [application_client.ts](../../desktop/electron/application_client.ts#L37), [bootstrap_server.py](../../local_cli/bootstrap_server.py#L211).

`useSessionView` suscribe la vista al cliente del host. Cambiar entre Inicio e Historial o cerrar un modal puede ser una operación visual sin reconstruir la sesión ni detener la generación. Fuente: [use_session_view.ts](../../desktop/src/use_session_view.ts).

## 4. Hallazgos por flujo

### 4.1 Preparación del sistema

En [application_client.ts](../../desktop/electron/application_client.ts#L220), un snapshot aceptado establece `ready: true` y `connected: true`. En este contexto describen la conexión del cliente a la sesión. No prueban que Ollama responda o que el modelo seleccionado esté instalado y sea utilizable.

Application ya dispone de observación de proveedores: [providers.py](../../local_cli/application/providers.py#L368) contiene `refresh_status()` y `list_models()`. [jsonl_application.py](../../local_cli/interfaces/jsonl_application.py#L254) proyecta la salud del runtime, pero consultar ese estado no equivale por sí solo a hacer un probe nuevo.

**Cambio necesario:** proyección de preparación observada por el host, con razones concretas y separada de «ocupado», «generando» o «esperando permiso». No reinterpretar indiscriminadamente `status.ready`, porque el selector actual también depende de él: [App.tsx](../../desktop/src/App.tsx#L378). Los ajustes deben seguir accesibles cuando falta la configuración.

### 4.2 Conversación, Inicio e Historial

La aplicación actual abre directamente una conversación con estética de terminal. No hay una vista inicial orbital ni una distinción visual entre interfaz compacta e historial.

El transcript ya procede de Application y el cliente maneja eventos repetidos y reconexión. Sin embargo, [types.ts](../../desktop/src/types.ts) no conserva toda la identidad y el ciclo de vida necesarios para contar respuestas públicas finalizadas de forma fiable: faltan, entre otros, correlación estable de herramientas y marcas de tiempo/read watermark de presentación.

Se necesita una proyección aditiva para mensajes y lectura, sin convertir el renderer en dueño de los turnos. Enviar desde Inicio no debe abrir Historial. Una respuesta pública nueva debe incrementar el contador una sola vez, aunque se repitan eventos o snapshots.

En [App.tsx](../../desktop/src/App.tsx#L280), el manejo de Enter ya considera Shift+Enter e IME. El borrador se limpia antes de conocer el receipt del envío. Debe conservarse cuando Application rechaza el mensaje o se pierde la conexión. También hay que hacer explícito el comportamiento del botón Detener durante una generación.

### 4.3 Mensajes, herramientas y estado incierto

[MessageBlock.tsx](../../desktop/src/components/MessageBlock.tsx) ya proporciona Markdown, detalles plegables, copiar y actividad. El Markdown se representa como contenido de React en [Markdown.tsx](../../desktop/src/components/Markdown.tsx), una base reutilizable.

La limitación está en la proyección de herramientas:

- `ToolResult` contiene solamente nombre y texto; el emparejamiento visual es posicional.
- La tarjeta presenta el resultado recibido con check/«Done», sin distinguir éxito, fallo, denegación o efecto `UNKNOWN`.
- Los eventos de ToolRuntime sí contienen resultado y `effectState`; parte se pierde en `_observe_display`.
- Etiquetas técnicas de harness aparecen en modo normal.

Fuentes: [types.ts](../../desktop/src/types.ts#L3), [MessageBlock.tsx](../../desktop/src/components/MessageBlock.tsx#L180), [session.py](../../local_cli/application/session.py#L1676), [session.py: eventos del runtime](../../local_cli/application/session.py#L1733).

**Cambio necesario:** conservar IDs y outcomes tipados hasta el componente. «Completado» no puede deducirse de que exista texto de salida. Un comando ejecutado tampoco demuestra por sí solo un efecto externo como que una ventana quedó abierta.

El cliente actual trata `ThinkingDelta` como actividad visual; no agrega su texto privado al mensaje público. Esa separación debe conservarse. «Pensando» será una etiqueta de producto, no una transcripción del razonamiento.

### 4.4 Qué significa tiempo real en la implementación actual

Ya hay eventos de inicio y final de herramienta. Para procesos, la infraestructura captura stdout/stderr y devuelve un reporte al finalizar: [host_process.py](../../local_cli/infrastructure/host_process.py#L79), [process.py](../../local_cli/core/process.py#L92).

No se encontró un canal público de fragmentos incrementales de stdout hasta Desktop. Por tanto, un nuevo componente puede mostrar inmediatamente «Ejecutando» y luego el resultado real, pero no una consola que crece durante la ejecución sin una extensión acotada del canal de progreso. La propuesta identifica expresamente ese trabajo; no simulará resultados en React.

### 4.5 Aprobaciones y preguntas

[App.tsx](../../desktop/src/App.tsx#L528) muestra una aprobación inline. Al pulsarla, [main.ts](../../desktop/electron/main.ts#L503) llama a `confirmApproval`, que abre un diálogo nativo adicional.

[approval_host.cjs](../../desktop/electron/approval_host.cjs#L23) comprueba solicitud pendiente, sesión, digest, herramienta, directorio, revisión de Policy, plazo y frescura después de la decisión. La firma privada se genera en main. La respuesta afirmativa del renderer no se considera consentimiento suficiente.

**Implicación:** una única tarjeta flotante como la solicitada requiere una superficie de consentimiento controlada por el host y pruebas equivalentes. No basta con quitar `showMessageBox` y firmar el «sí» de React. Las preguntas normales pueden reutilizar su mecanismo existente sin confundirse con Approval.

### 4.6 Proyectos y explorador

[FileExplorer.tsx](../../desktop/src/components/FileExplorer.tsx) ya permite selección nativa de carpeta, expansión diferida, orden de carpetas, recarga y paginación. Cancelar el picker conserva la raíz anterior. El visor limita la vista previa a 1 MB. Son piezas que conviene conservar.

Falta la presentación de la referencia: drawer lateral, registro de carpetas recordadas, proyecto administrado predeterminado y menú Cambiar/Quitar/Abrir en el Explorador. Actualmente hay **un workspace activo**, no varios roots efectivos simultáneos.

Application ya valida y serializa `change_workspace`, bloquea cambios durante trabajo activo y reancla servicios: [session.py](../../local_cli/application/session.py#L882). La nueva UI debe esperar su receipt antes de cambiar la selección.

Dos correcciones pequeñas vinculadas al refactor:

- `split('/')` para el nombre de raíz/archivo no cubre correctamente rutas Windows con `\`: [FileExplorer.tsx](../../desktop/src/components/FileExplorer.tsx#L187), [FileViewer.tsx](../../desktop/src/components/FileViewer.tsx#L23).
- Los handlers de vista previa/listado aceptan rutas desde el renderer y leen directamente con `fs`, sin asociarlas explícitamente al root elegido ni aplicar el mismo control de sender de otros handlers: [main.ts](../../desktop/electron/main.ts#L534). Es un hueco observado del contrato IPC; no se ha intentado ni demostrado una explotación. Al construir el nuevo panel se debe usar una operación acotada al proyecto host-owned.

`openExternalUrl` no sustituye una operación específica de abrir la carpeta elegida en el Explorador. Se propone un handler pequeño que obtenga el path del proyecto confirmado y llame a `shell.openPath`.

### 4.7 Modelos

[ModelPicker.tsx](../../desktop/src/components/ModelPicker.tsx) ya ofrece Para ti/recomendaciones, Catálogo, Descubrir, búsqueda, categorías, información de hardware, instalar, eliminar, sincronizar y progreso. Tiene cierre con Escape y clic fuera. No hace falta un catálogo nuevo.

Puntos a corregir o formalizar:

- [App.tsx](../../desktop/src/App.tsx#L201) cambia al modelo recién descargado y cierra el panel automáticamente. Descargar y seleccionar deben ser acciones distintas salvo petición explícita «descargar y usar».
- La selección visual se cierra antes de conocer el resultado del cambio. Debe reflejar el modelo confirmado por Application.
- [session.py](../../local_cli/application/session.py#L370) valida el cambio de modelo, pero no persiste por sí mismo la selección como preferencia para próximos arranques.
- No existe todavía foco modal accesible completo ni localización ES/EN. Hay textos puntuales en otros idiomas y progreso interpretado desde texto.

Los modelos, fechas, estrellas y tamaños de la referencia son ejemplos visuales; no deben convertirse en datos hardcodeados de Nova.

### 4.8 Ajustes, idiomas y controles existentes

[SettingsPanel.tsx](../../desktop/src/components/SettingsPanel.tsx) agrupa versión, actualizaciones, RAG y atajos. No hay navegación por secciones, esquema de preferencias GUI ni infraestructura i18n. Otros controles Memory/Knowledge están repartidos entre App y el puente.

Los textos actuales mezclan idiomas: renderer mayoritariamente inglés, algunos diálogos españoles y otros ingleses en main. La nueva GUI necesita localización de componentes y mensajes del host Desktop, conservando códigos técnicos en diagnóstico. No debe traducir mensajes del usuario/modelo ni cambiar el idioma de CLI.

Hay controles web existentes en [commands.py](../../local_cli/application/commands.py#L30), pero no forman parte del conjunto admitido por el cliente Desktop actual en [application_client.ts](../../desktop/electron/application_client.ts#L6). Exponer sus configuraciones requiere un puente explícito a esas operaciones, no modificar preferencias solamente en React.

### 4.9 Menubar, identidad y actualizador

[main.ts](../../desktop/electron/main.ts#L417) usa ventana Windows con frame nativo. No se encontró retirada explícita del menú de aplicación. Se puede eliminar el menubar y conservar minimizar/maximizar/cerrar nativos, sin añadir una ventana frameless en esta etapa.

[package.json](../../desktop/package.json) conserva identidad Local CLI y URLs upstream; [main.ts](../../desktop/electron/main.ts#L24) consulta releases de `lutelute/local-cli`. Antes de presentar actualización de Nova, hay que aislar/desactivar esa ruta heredada hasta definir un destino aprobado. No se necesita construir ni publicar un instalador para hacerlo.

## 5. Reutilizar, adaptar y dejar fuera

| Reutilizar directamente | Adaptar de forma focal | Fuera de esta etapa |
|---|---|---|
| Application, AgentLoop, ToolRuntime, Policy/Approval/Grant. | DTO de preparación, actividad y mensajes de Desktop. | Cambios del comportamiento del agente por estilo de GUI. |
| Cliente de sesión, snapshots, cursor y reconexión. | Home/Historial, contador y persistencia de preferencias visuales. | Voz, animación 3D, MCP y nuevas capabilities. |
| Picker y servicios de modelos. | Presentación de catálogo y selección persistida. | Nuevo proveedor de modelos o catálogo inventado. |
| Workspace, picker, árbol y visor. | Proyecto predeterminado, menú y IPC de vista humana. | Autoridad multi-root simultánea no implementada. |
| Memory, Knowledge, attachments y RAG actuales. | Ubicación y localización de sus controles. | Rediseñar sus motores o admitir formatos nuevos. |
| Controles Browser/fetch existentes. | Proyectar configuración y disponibilidad reales. | Reabrir Active Web/HUX o campañas de certificación. |

## 6. Pruebas existentes aprovechables

| Infraestructura | Qué ayuda a preservar | Qué no demuestra todavía |
|---|---|---|
| [application_client.test.cjs](../../desktop/tests/application_client.test.cjs) | Snapshot/eventos, desconexión, replay, correlación. | Home, badge, configuración inicial y aceptación visual. |
| [approval_host.test.cjs](../../desktop/tests/approval_host.test.cjs) | Validación exacta, firma privada, plazo y confirmación del host. | Una nueva superficie flotante equivalente. |
| [test_nova_core_phase13_desktop.py](../../tests/test_nova_core_phase13_desktop.py) | Puente con Application y gates de Desktop. | La nueva navegación y localización. |
| [test_nova_core_phase8_providers.py](../../tests/test_nova_core_phase8_providers.py) | Proveedores, modelo ausente y cambios validados. | Indicador visual de preparación real. |
| [test_nova_core_phase4_session.py](../../tests/test_nova_core_phase4_session.py) | Continuidad y semántica de sesión. | Contador de respuestas leídas. |
| [memory_control.test.cjs](../../desktop/tests/memory_control.test.cjs), [knowledge_control.test.cjs](../../desktop/tests/knowledge_control.test.cjs) | Puentes y operaciones existentes. | Organización e idioma del nuevo panel. |

Se recomienda añadir pruebas de los flujos nuevos durante cada bloque y una comprobación integrada Windows al final. No hace falta una campaña general de seguridad ni un benchmark masivo de modelos para validar una refactorización de Desktop.

## 7. Decisiones de diseño que sustentan la propuesta

- La referencia 4 define Inicio; la 5, Historial; la 6, Proyectos; la 7, Modelos. Las referencias 1–3 definen organización de Ajustes, no nuevas funciones.
- Siguiendo la imagen de Historial: usuario a la derecha y Nova a la izquierda. Se resuelve así la frase de la solicitud que menciona dos veces «derecha».
- El proyecto predeterminado será una carpeta dedicada dentro de la raíz de Nova, propuesta `workspace/`; no se concede implícitamente acceso a todo el source tree.
- La GUI podrá operar en ES/EN. El idioma del modelo seguirá dependiendo de la conversación y su configuración actual.
- «Listo» es disponibilidad observada para el chat local; «Pensando» y «esperando permiso» son actividad, no fallos de instalación.
- No se alteran estados ni resultados históricos de Active Web/HUX. Esta auditoría no certifica disponibilidad nueva de Browser ni cambia el alcance de sus contratos.

**Estado de esta entrega:** auditoría y propuesta documental; implementación pendiente de los bloques descritos en el segundo archivo.
