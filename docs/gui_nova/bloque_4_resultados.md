# GUI-B4 — Actividad, salida y permisos

Fecha: 2026-10-16. Proyecto: `nova-min/nova-assistant`.

## Resultado

- Herramientas desplegables bajo el mensaje público correspondiente, correlacionadas por `operationId`, `toolCallId` y el ID host del mensaje; nunca por texto o posición de resultados.
- Inicio conserva la vista compacta y muestra la actividad del turno actual. Historial conserva la conversación compartida, los contadores y la lectura de GUI-B3.
- «Pensando» indica generación activa sin exponer razonamiento privado. Los verbos «Leyendo…» o «Ejecutando…» requieren un estado de ejecución observado; las operaciones pendientes, terminadas o denegadas tienen títulos neutros.
- Salida stdout/stderr real en crecimiento cuando la herramienta la ofrece. Si sólo existe un resultado final, se muestra ese resultado; no hay transcripción animada ficticia.
- Estados derivados de receipts: ejecución confirmada, denegación, fallo, cancelación, timeout, no disponible e incertidumbre. `UNKNOWN`, efectos parciales y pérdida de observación no muestran un check de éxito ni generan reintentos.
- Errores normales ES/EN y diagnóstico plegable separado. Una causa terminal correlacionada no se repite como aviso genérico del turno además de su tarjeta. Las respuestas públicas del modelo se conservan: no se hace deduplicación léxica de su prosa.
- Los resultados legacy sin receipt tipado se muestran como detalles sin confirmación de ejecución; su texto no concede un estado exitoso.

## Una aprobación controlada por el host

La doble confirmación anterior se sustituye, en la ruta productiva de herramientas, por una sola ventana hija local creada por Electron encima del compositor, con «Permitir» y «No permitir» (ES) / «Allow» y «Deny» (EN).

La ventana principal únicamente muestra la solicitud pendiente y «Revisar permiso». Ese botón abre la superficie del host; no decide ni firma consentimiento. Tanto `application-command/ResolveApproval` desde el renderer principal como la ruta raw heredada se rechazan. El helper nativo anterior se conserva para compatibilidad y sus tests, sin seleccionarlo en esta ruta productiva.

La superficie usa documento fijo local, CSP sin scripts de página, conexiones o frames, `sandbox=true`, `contextIsolation=true` y `nodeIntegration=false`. Su preload aislado coloca argumentos mediante `textContent`, no publica API al documento y sólo atiende sus dos canales privados. Se deniegan navegación, ventanas nuevas, webviews y permisos de contenido. No se carga contenido remoto.

Main acepta una decisión sólo desde el webContents y main frame de esa ventana exacta, con nonce fresco y solicitud vigente. Vuelve a comprobar sesión, approval/toolCall/turn/operation IDs, argumentos completos, digest, cwd, revisión de Policy y plazo antes del envío. Invalida el binding antes del dispatch para impedir doble clic; el cliente construye el comando y la autenticación privada existentes. No hay autoaprobación, consentimiento persistente ni firma expuesta al renderer.

Cerrar o recargar esa ventana no aprueba ni ejecuta. La solicitud puede revisarse de nuevo explícitamente, con binding nuevo si todavía es válida. Una recarga del renderer principal conserva la superficie independiente; una desconexión, pérdida de continuidad o cambio de solicitud la invalida. La recuperación del stream debe completar un snapshot fresco antes de volver a ofrecer una decisión.

Abrir/revisar sólo informa éxito tras READY real del preload. Carga fallida, ausencia de READY durante un máximo de cinco segundos, cierre o fallo nativo de creación/posición muestran un error recuperable de presentación; nunca despachan consentimiento ni abren un bucle de ventanas. El compositor y Detener quedan accesibles. Las preguntas de Nova conservan su respuesta propia y se distinguen de permisos.

## Transporte y límites

Application mantiene un sidecar `toolActivities` en los snapshots del turno. Los eventos `ToolRequested/Started/Completed/Failed` públicos conservan sus payloads mínimos existentes. Las proyecciones completas y los fragmentos de salida se envían como `OperationProgress` **SENSITIVE**, sólo a la interfaz dueña de sesión.

- Progreso combinado retenido: hasta **32 KiB por operación**.
- Resultado final de presentación: hasta **32 KiB por campo** `output/stdout/stderr`.
- Argumentos de presentación: preview JSON de hasta **8 KiB**; error técnico de hasta **256 bytes**. No se recortan los argumentos reales que recibe el ejecutor o la aprobación.
- Batches de progreso de **100 ms**, hasta un fragmento por canal por flush (hasta 20 eventos de fragmentos/s, más primer/último flush). Secuencia monotónica propia de la operación.
- Decodificación UTF-8 incremental y redacción de secretos entre fragmentos antes de publicar. Un prefijo de secreto retenido no aparece a medias al terminar.
- Los límites de proceso, captura, timeout, concurrencia, árbol y cleanup existentes no cambian. El callback es opcional y los puertos antiguos que no lo soportan conservan su firma anterior.

El cliente descarta duplicados, correlaciones ajenas y progreso posterior a un receipt terminal; un salto de fragmentos recupera un snapshot. El receipt final reemplaza el preview incremental. Perder conexión marca pérdida de observación en presentación, conserva el último outcome host y no vuelve a ejecutar una acción. Los IDs y estados tipados se preservan al redactar; argumentos, rutas y texto siguen redactados. El sidecar no se incorpora a inferencia, memoria o transcript persistido.

`ToolStarted` conserva su semántica previa de entrada al runtime. No se mueve la revalidación final anterior al efecto físico: una negativa en ese límite sigue denegando la ejecución. Un exit code 0 tampoco prueba cualquier efecto semántico ni la aparición de una ventana.

## Archivos

- Backend: `local_cli/application/{session,tool_runtime,process,secrets,events}.py`, `local_cli/core/process.py`, `local_cli/infrastructure/host_process.py`.
- DTO/proyección: `desktop/src/types.ts`, `desktop/shared/application.ts`, `desktop/electron/{application_client,activity_projection,preload}.ts`.
- Host: `desktop/electron/main.ts`, `approval_surface.cjs`, `approval_surface.d.cts`, `approval_preload.ts`, `desktop/vite.config.ts`.
- Renderer: `App.tsx`, `components/MessageBlock.tsx`, `components/ToolActivity.tsx`, `activity_presentation.ts`, `i18n.tsx`, `styles.css`.
- Tests: `tests/test_gui_activity.py`; `desktop/tests/{activity_client,activity_presentation,approval_surface}.test.cjs`; fixture manual `approval_surface.electron-smoke.cjs`.
- Inventario y CI existentes, exclusión específica `/.runtime/gui-b4-native/` en `.gitignore` y este informe nuevo.

## Verificación

- **156/156 tests Node PASS**, en las 15 suites ordinarias de Desktop. Incluyen 47 contratos nuevos/heredados de aprobación, correlación y secuencia de actividad, salida acotada, errores y recuperación de conexión.
- **238 tests Python PASS, 2 SKIP** en la regresión focal de GUI-B2/B3/B4, sesión, eventos, ToolRuntime, interacciones, providers, Desktop, procesos, Policy/Approval/Grant y redacción. Las omisiones corresponden a perfiles manuales existentes; los tests nuevos de actividad se ejecutaron.
- **TypeScript sin errores** (`tsc --noEmit`) y **build Vite PASS** de renderer, main y ambos preloads. No se invocó electron-builder.
- Inventario CI actualizado: **3935 contratos estáticos**, sin contratos sin clasificar; las tres suites Node nuevas pertenecen al job ordinario Desktop. El smoke Electron queda en un perfil manual explícito.
- La copia al proyecto objetivo usa hashes previos y posteriores por archivo. Se verifica que los **1625 documentos históricos** anteriores conservan su SHA-256.

### Comprobación visual y nativa

Se utilizó el renderer real con `DesktopApplicationClient` real y receipts de una fixture owned, sin conversaciones personales ni efectos externos. Se observó inicio activo antes del resultado final, desplegables, stdout preservado, denegación e incertidumbre con diagnóstico separado. El error de turno `OUTCOME_UNKNOWN` no añadió un segundo aviso de la misma condición. La fixture no representa una evaluación de calidad del modelo.

Se ejecutó además Electron instalado con controlador, documento, preload, sandbox e IPC reales. En fixtures independientes se registraron `approved:true` y `approved:false`, cada uno con **dispatchCount=1** y **executed=false**: el receptor era un sink de prueba y no ejecutó el comando mostrado. La entrada Allow se observó como entrada nativa real sin atribuir su actor; la entrada Deny se verificó con computer-use. No se simuló consentimiento mediante JavaScript/IPC ni se repitieron los casos para cambiar sus resultados. El perfil final `--ready-only` confirmó READY real con **dispatchCount=0**, sin decisión.

El smoke manual queda fuera del job ordinario CI. Requiere Electron instalado y generar antes `approval_preload.js` con el build Vite (sin electron-builder); se ejecuta explícitamente desde `desktop` con `node_modules/electron/dist/electron.exe tests/approval_surface.electron-smoke.cjs --case=allow`, `--case=deny` o `--case=final-ready --ready-only`. Sus perfiles, recibos y logs van a la carpeta ignorada `.runtime/gui-b4-native/`, sin tocar el perfil personal de Nova. Las fixtures se cerraron tras sus recibos.

## Preservación y límites de esta entrega

PolicyEngine, ApprovalGate, GrantIssuer y la autenticación del pipe siguen siendo la frontera de ejecución. No cambian los permisos, los receipts remotos, networking, primitives Browser, selección de herramientas o respuestas del modelo. No se modificó CLI ni se reinterpretó UNKNOWN como éxito. No se añadieron capacidades, voz o MCP. Los diálogos de consentimiento específicos de Memory/Knowledge conservan su mecanismo existente; no forman parte de la doble aprobación de herramientas sustituida aquí.

La documentación/evidencia anterior se contrasta por SHA-256 y permanece intacta. No se reabren campañas ni se cambian resultados históricos. No se hace staging Git, commit, push, tag, release, instalador ni compilación de ejecutables; sólo comprobación de TypeScript y bundles de renderer/main/preloads.
