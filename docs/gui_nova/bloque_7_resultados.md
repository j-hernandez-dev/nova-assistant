# GUI-B7 — Ajustes por dominio y mensajes Desktop

Fecha: 2026-10-16. Proyecto: `C:\Users\joseh\Downloads\nova-min\nova-assistant`.

## Resultado

El botón de configuración abre un modal Nova con navegación por secciones a la izquierda y opciones a la derecha. Navegación y contenido tienen desplazamiento independiente, incluido el mínimo de ventana de 600×400. Escape, clic exterior y el botón de cierre conservan el contrato de ModalHost.

| Sección | Implementación |
|---|---|
| General | Idioma de interfaz ES/EN con borrador, Guardar y Cancelar; explicación del alcance y atajos existentes. |
| Conexión y modelo | Proveedor/modelo y preparación observados; acceso al gestor único de modelos; proveedores adicionales existentes bajo opciones avanzadas. |
| Proyectos y permisos | Proyecto efectivo y predeterminado; acceso al panel existente para añadir, cambiar, quitar y abrir carpetas. No hay nuevos permisos ni acceso completo. |
| Web | Formularios independientes para Fetch, buscador y navegador. Guardan mediante los comandos existentes de Application; muestran por separado borrador, valor efectivo y disponibilidad. |
| Memoria | Capacidades observadas de sólo lectura y controles existentes de consulta, búsqueda, paginación, detalle, recuerdo, corrección, olvido, propuestas y exportación JSON visible. |
| Conocimiento y documentos | Fuentes/adjuntos y todas las operaciones previas de Knowledge. RAG se aplica explícitamente a la sesión actual. |
| Acerca de y diagnóstico | Versión, conexión, proveedor, número de herramientas, limpieza del chat y códigos técnicos. Actualizador heredado deshabilitado, sin botón hacia upstream. |

El selector rápido de idioma del encabezado se concentra en General para mantener un único formulario de preferencias. El selector del compositor continúa mostrando exclusivamente modelos instalados en Ollama.

## Persistencia y fuentes de verdad

- El idioma continúa guardándose por Electron en `%APPDATA%\nova-desktop\desktop-preferences.json`, separado de proyectos, selección de modelo, conversaciones y servicios. El store existente valida ES/EN y escribe de forma atómica; un fallo conserva la preferencia anterior.
- Los formularios conservan su borrador al cambiar de sección. Cancelar restaura el valor efectivo; cerrar descarta cambios no guardados. Una operación ya enviada al host continúa independientemente de cerrar el modal.
- Fetch usa `SetFetchEnabled` y el almacén existente `fetch-preference.json`; buscador usa `SetSearchEngine` y `browser-search.json`; navegador usa `SetBrowser` y `browser-preference.json`, en el state directory administrado por Nova. No se migraron preferencias personales.
- Los cambios usan sesión y revisión actuales. Un receipt aceptado no cambia optimistamente el estado: el valor efectivo llega del snapshot del host. No hay una copia efectiva en localStorage.
- Cambiar de navegador puede cerrar su sesión anterior antes de guardar la preferencia. La interfaz lo advierte; no promete restaurar páginas o inicios de sesión si guardar falla.
- `SetRAGEnabled` aplica a la sesión actual y puede iniciar indexación. No se presenta como preferencia persistida ni como indexación terminada al aceptar el comando.
- Semántica de Memory, captura automática e inyección remota son configuración existente observada; no se inventaron setters para ellas.

## Idioma y consentimiento

Los textos propios, estados, errores normales, controles de proveedor y autenticación, y los diálogos nativos de selección de archivos/carpetas, memoria sensible y envío de documentos usan ES/EN. La preferencia se consulta al abrir cada diálogo. Se preservan las decisiones, sus índices y la validación del host.

Las conversaciones, las respuestas del modelo, los documentos, los recuerdos, la salida de herramientas y los códigos técnicos conservan su contenido original. El idioma de presentación no se envía al modelo ni cambia la CLI. Los detalles técnicos permanecen en desplegables, y el renderer no muestra excepciones arbitrarias de autenticación como mensajes normales.

Una nueva aprobación del host cierra los paneles de ajustes/modelos para no quedar oculta. No se modificaron Policy, Approval, Grant, las primitives Browser ni los mecanismos privados de credenciales.

## Correcciones causales

- Un resultado tardío no se adhiere a otro proyecto/sesión.
- La incertidumbre de una operación, incluido `MemoryControlResult.error.outcomeUnknown`, no se convierte en éxito ni produce reintento automático.
- Los formularios Web vinculan la espera al valor enviado, de modo que un guardado anterior no bloquea un nuevo borrador.
- Aplicar RAG queda pendiente hasta observar el estado aceptado; no vuelve a encolar la misma indexación durante la espera del snapshot.
- Quitar un adjunto de la selección por borrado ocurre después de la aceptación del host.
- Los errores de preferencias y servicios se presentan con mensajes propios traducidos y códigos técnicos separados.

## Comprobaciones

| Verificación | Resultado |
|---|---|
| TypeScript completo, sin emitir | PASS |
| Desktop: suites ordinarias y nuevas de Ajustes | 263/263 PASS en el proyecto entregado; incluye cliente, consentimiento, proyección, persistencia y formularios |
| Backend proporcional: Fetch, búsqueda con navegador, readiness y proyectos | 64/64 PASS; fixtures y preferencias de prueba |
| Nuevos contratos de Desktop en inventario y workflow CI | Registrados; sin GUI, Ollama ni Internet requeridos |
| Electron 1280×820 | Modal, General, Web, borrador y traducción verificados con fixture owned |
| Electron 600×400 | Navegación y contenido desplazables; controles accesibles sin solapamiento |
| Persistencia de idioma | Elegir EN no guarda; cambiar de sección conserva el borrador; Escape y reapertura recuperan ES; Guardar aplica EN; una nueva ventana inicia en EN |
| Almacenes y autoridad | Stores/receipts existentes, pruebas negativas de sesión/revisión y consentimiento conservadas |
| Documentos históricos | 1628 archivos anteriores byte-intactos; no se reetiquetaron estados históricos |

Incidencia de ejecución registrada: una corrida conjunta obtuvo un fallo intermitente en la escritura del registro de proyectos, en una suite/fuente anterior sin cambios B7. La repetición focal de esa suite aprobó sus 16 casos. Los resultados de cada intento permanecen en el staging externo; no se alteró el contrato de proyectos para aprobarlo.

La prueba visual usa el renderer real, DesktopApplicationClient y el store real de preferencias de presentación sobre un directorio owned. Los servicios están simulados en ese fixture; sus contratos efectivos se prueban también en las suites de host/backend. No se iniciaron búsquedas públicas, autenticaciones, descargas, mutaciones Browser ni operaciones sobre memoria/documentos personales.

## Archivos y límites

Cambios principales: `SettingsPanel.tsx`, `WebSettings.tsx`, `MemorySettings.tsx`, `KnowledgeSettings.tsx`, `settings_actions.tsx`, los módulos de textos ES/EN, `settings.css`, integración `App.tsx`, los DTO/cliente de sesión y localización de diálogos en `main.ts`. Se añaden siete suites ordinarias y se actualizan los sentinels de Knowledge para comprobar los helpers de diálogo y la nueva ubicación de los controles.

No se añadieron temas, voz, MCP, nuevos proveedores, nuevos navegadores ni formatos. No se reescribió el agente ni el networking. No hubo staging Git, commit, push, tag, release, empaquetado ni compilación de ejecutables. El cierre integrado del producto corresponde al bloque 8.

GUI_B7_AJUSTES = PASS
