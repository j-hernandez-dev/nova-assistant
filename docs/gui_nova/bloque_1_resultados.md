# GUI-B1 — Estructura visual de Nova

Fecha: 2026-10-15. Proyecto: `C:\Users\joseh\Downloads\nova-min\nova-assistant`.

## Resultado

**GUI-B1 = PASS** para la estructura visual, navegación básica, base ES/EN y retirada del menubar previstas en [la propuesta](02_propuesta_gui_nova_y_bloques.md).

Se conserva la sesión existente y su puente con Application. Este bloque no declara completados los bloques B2–B8.

## Cambios entregados

- Shell Nova: fondo azul casi negro, acento ámbar, rail lateral con Inicio/Proyectos/Modelos y Configuración anclada abajo.
- Inicio con órbita decorativa SVG local y compositor inferior redondeado. Sin imágenes remotas, fuentes descargadas, motor 3D ni voz.
- El compositor contiene exclusivamente un combobox de modelos instalados en Ollama, consultados mediante el endpoint `models` existente. No usa el catálogo de modelos descargables como lista de selección. El cerebro abre por separado el catálogo completo. Cambiar la selección pasa por `ChangeModel` y el estado confirmado de Application; no cambia de proveedor automáticamente.
- Acceso manual a la conversación existente y regreso a Inicio, consumiendo el mismo `useSessionView`. No se crea otro agente ni se cambia su selección de herramientas.
- Los controles existentes de proveedor y Knowledge siguen disponibles bajo «Herramientas y fuentes»; adjuntar usa el picker del host existente.
- Estado superior explícito «Backend conectado»/«Conectando con el backend». No se presenta como «Listo»: comprobar Ollama y modelo corresponde a B2.
- Base de traducciones tipadas ES/EN; español predeterminado y selector de idioma. Se localizaron el shell y los controles estáticos de los modales actuales. Contenido del usuario/modelo, metadata de terceros, resultados y configuración CLI conservan su idioma original.
- Preferencia de idioma guardada exclusivamente por Electron en `%APPDATA%\nova-desktop\desktop-preferences.json`, con validación, escritura atómica y error visible si no puede guardarse. No se migra configuración personal existente.
- ModalHost compartido: fondo atenuado e inerte, foco atrapado, Tab/Shift+Tab, Escape/clic exterior y restauración de foco. Se conservaron callbacks y guardas de instalación existentes.
- Menubar retirado mediante Electron; frame nativo, controles de ventana y atajos de edición conservados. Título de ventana y HTML: Nova.
- Los entry points del actualizador Electron heredado a Local CLI quedan deshabilitados antes de red/instalación. Configuración explica «Las actualizaciones de Desktop no están configuradas para Nova», sin afirmar falsamente que está actualizado.
- Tipografía de interfaz separada de código, foco visible, reglas responsive y respeto de `prefers-reduced-motion`.

## Archivos de producto modificados o añadidos

| Área | Archivos |
|---|---|
| Shell | `desktop/src/App.tsx`, `src/styles.css`, `src/main.tsx`, `src/types.ts`, `desktop/index.html` |
| Componentes nuevos | `desktop/src/components/NovaIcon.tsx`, `NovaOrbit.tsx`, `ModalHost.tsx` |
| Idioma | `desktop/src/i18n.tsx` |
| Modales existentes | `desktop/src/components/ModelPicker.tsx`, `SettingsPanel.tsx`, `ClaudeLogin.tsx` |
| Host/IPC | `desktop/electron/main.ts`, `preload.ts` |
| Preferencias/presentación host | `desktop/electron/desktop_preferences.cjs`, `.d.cts`, `desktop_host_policy.cjs`, `.d.cts` |
| Bundle | `desktop/vite.config.ts`: inclusión de los nuevos helpers CommonJS |
| Pruebas | `desktop/tests/desktop_presentation_host.test.cjs` |

Total: 20 archivos fuente/pruebas, además de este informe. Se comprobaron hashes antes de copiar para evitar sobrescribir cambios concurrentes. El servidor/fixture de revisión y sus bundles permanecieron fuera del proyecto; no se incorporó ningún mock al producto.

## Validación realizada

| Comprobación | Resultado y alcance |
|---|---|
| TypeScript en el proyecto final | PASS: `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`. |
| Bundles Vite | PASS: renderer, main y preload mediante `vite build --configLoader runner`, en preparación. Sin electron-builder ni ejecutables. |
| Pruebas focales | **53/53 PASS**, repetidas desde el Desktop final: application_client, approval_host, desktop_presentation_host, knowledge_control y memory_control. |
| Persistencia ES/EN | PASS: cambio, lectura tras reinicio del store, aislamiento de objetos, datos corruptos/oversized y fallo de disco sin cambiar la preferencia efectiva. |
| Contratos host | PASS: sender de IPC, atajos de edición, bloqueo de los tres entry points del updater Electron, aprobaciones existentes preservadas. |
| Revisión visual del renderer | PASS con fixture owned sin efectos: Inicio, órbita, compositor, rail y modales. |
| Idioma en renderer | PASS: cambio ES → EN, etiquetas/placeholder/acciones; regreso a ES. |
| Selector instalado/catálogo | PASS con fixture: combo con dos tags instalados, cambio confirmado de modelo y catálogo independiente que sí incluye un modelo no instalado. El combo no abre el catálogo ni ofrece ese modelo descargable. |
| Modal y teclado | PASS: foco dentro del modal, Tab desde último a primero y Shift+Tab inverso, Escape y foco restaurado al disparador. |
| Responsive | Comprobación del renderer con viewport 1000×700 y 600×400; sin desbordamiento horizontal en el mínimo. |

La revisión de navegador usa datos visuales deterministas; **no es una campaña de modelo real ni prueba de disponibilidad de Ollama**. Los 53 tests incluyen seis nuevos de presentación host. Los temporales de esos tests se dirigieron a una carpeta owned debido a restricciones de escritura del sandbox.

Durante la revisión se corrigió un defecto de integración: los modales usan un portal al body; sus selectores CSS deben partir de `.nova-modal-backdrop`, no de `.nova-app`.

## Límites y continuidad

- B2: preparación real de Ollama/modelo y configuración mínima.
- B3: contador deduplicado de respuestas, receipts del compositor y comportamiento completo de Historial.
- B4: estados de herramientas tipados, stdout incremental y aprobación única. Se mantiene de momento la confirmación nativa existente; no se debilitó su contrato.
- B5–B7: nuevos proyectos/predeterminado, catálogo visual completo y ajustes por secciones. Los componentes actuales siguen operativos; no se presentan como refactorizados por completo.
- La traducción completa de mensajes host/backend, explorador y diagnósticos se termina en sus bloques; esta entrega establece la base de idioma y localiza el shell/modales adaptados.
- El check Python heredado de actualización contra el remoto del checkout no se modificó: no forma parte del updater Electron deshabilitado. CLI y backend compartido no cambiaron.
- No se lanzó una campaña de seguridad, Browser ni HUX. No se modificaron evidencias históricas ni estados anteriores.

## Uso en desarrollo

Desde PowerShell con Node y Python del proyecto en PATH:

```powershell
Set-Location "C:\Users\joseh\Downloads\nova-min\nova-assistant\desktop"
npm.cmd run dev
```

No se hizo staging, commit, push, tag, release, empaquetado ni instalación de modelos. Las aprobaciones y efectos continúan en los mecanismos existentes de Application/ToolRuntime.
