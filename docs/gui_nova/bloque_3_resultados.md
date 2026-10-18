# GUI-B3 — Inicio e Historial

Fecha: 2026-10-16. Proyecto: `nova-min/nova-assistant`.

## Resultado funcional

- Enviar conserva Inicio compacto; no abre Historial automáticamente.
- El icono aparece cuando Application proyecta el primer mensaje humano aceptado o una conversación restaurada explícitamente.
- Inicio e Historial utilizan la misma `AgentSession`, transcript, turno activo, preguntas y permisos. Cambiar de vista no envía comandos de ejecución, no crea otro agente y no cancela el turno.
- Cada mensaje público de Nova completado mientras Historial está oculto suma una notificación. Una explicación antes de una herramienta y una respuesta final cuentan como dos mensajes cuando sus identidades son distintas.
- Tokens, thinking, herramientas, resultados, entradas vacías, cancelaciones y fallos no suman notificaciones. Snapshots repetidos, replay, reconexiones y remount del renderer conservan la deduplicación.
- Abrir Historial limpia la burbuja; las respuestas que llegan mientras está visible se consideran leídas. Minimizar, ocultar o recargar la ventana retira la visibilidad efectiva.
- Usuario a la derecha, Nova a la izquierda, Markdown renderizado como datos, horas únicamente cuando Application las observó. Las entradas antiguas sin timestamp no reciben uno inventado.
- El scroll sigue respuestas nuevas sólo cuando el usuario está cerca del final. Abrir Historial sitúa la conversación al final; leer mensajes anteriores o seleccionar texto no fuerza el scroll ni el foco del compositor.
- Las respuestas parciales canceladas/fallidas permanecen visibles con su estado; no se convierten en mensajes completos ni en contexto nuevo para el modelo.
- Readiness, selección de modelo, borrador ante rechazo, Enter/Shift+Enter/IME, detener, preguntas y aprobación nativa se conservan.

## Implementación

Application añade un sidecar de presentación en el snapshot del turno: `userMessage` y metadata de `displayMessages` con ID host, timestamps UTC y estado del segmento. El `generationId` procede del host; la relación con el transcript canónico utiliza la identidad del objeto realmente añadido, nunca coincidencias de texto. Al terminar la captura se publica su `sourceIndex` exacto.

Estos campos no entran en el prompt, en el transcript de inferencia ni en su persistencia. `resume` retira únicamente sidecars obsoletos y el cambio de workspace remapea índices conservando identidades; no altera outcomes ni revive operaciones.

Electron conserva el estado de lectura fuera de React. El archivo `desktop-conversation-view.json` bajo `app.getPath('userData')` contiene sólo IDs observados/no leídos por sesión: hasta 20 sesiones y 10 000 IDs por conjunto, con tamaño total acotado y escritura atómica. No almacena mensajes, argumentos, herramientas, permisos o authority. Un fallo de disco muestra aviso y mantiene el funcionamiento en memoria. Una nueva carga del cliente toma su primer snapshot como historia previa, conservando IDs no leídos persistidos sin notificar de nuevo todo el transcript.

El IPC `set-history-visible` valida el sender principal y un booleano. Sólo cambia presentación; no evalúa ni concede permisos. También se rechazan snapshots con revisión anterior, aunque tengan la misma secuencia, para impedir que reaparezca una conversación limpiada.

### Archivos

- `local_cli/application/session.py` y `tests/test_gui_conversation.py`.
- `desktop/shared/application.ts`, `desktop/src/types.ts`.
- `desktop/electron/application_client.ts`, `conversation_notifications.ts`, `conversation_preferences.cjs`, `conversation_preferences.d.cts`, `main.ts`, `preload.ts`.
- `desktop/src/App.tsx`, `components/MessageBlock.tsx`, `i18n.tsx`, `styles.css`.
- `desktop/vite.config.ts`: inclusión del pequeño almacén CommonJS en el bundle.
- `desktop/tests/conversation_client.test.cjs`, `conversation_preferences.test.cjs`; ajuste del test de citas de `knowledge_k7.test.cjs` para comprobar el mismo disclaimer en el idioma predeterminado ES.
- `ci/pytest_contracts.json` y `.github/workflows/nova_knowledge_v1.yml`: incorporación a CI ordinaria, sin Ollama, GPU, GUI o empaquetado.

## Verificación

- Python: **76 PASS, 2 SKIP** en conversación, readiness, sesión, proveedores y contratos Desktop. Los omitidos requieren runner nativo/aceptación manual; no se presentaron como PASS.
- Dentro de esa ejecución: **10/10 PASS** nuevos, incluyendo el loop productivo real con `ReadTool` y proveedor scripted. La generación sigue el orden real `llm_start → deltas → append assistant → assistant_message → tool → siguiente generación`; el sidecar no se basa en un orden simulado distinto.
- Desktop Node: **104/104 PASS** en las doce suites ordinarias, incluyendo identidad, streaming, dos respuestas por turno, deduplicación, replay, reconexión, restore, snapshot de revisión obsoleta, parcial cancelado, persistencia y aprobación nativa.
- TypeScript: `tsc --noEmit` **PASS**.
- Bundle Vite de renderer, Electron main y preload: **PASS**; sin electron-builder/instalador.
- Inventario CI: **3924 contratos estáticos**, sin contratos nuevos sin clasificar. Los nueve nuevos selectores Python y las dos suites Node se incluyen en los jobs ordinarios existentes.
- La validación de archivos fue repetida desde el proyecto destino. La documentación previa se contrastó por SHA-256; ningún archivo histórico se modificó.

En una primera ejecución concurrente desde destino, una escritura de la fixture del almacén devolvió `false` en el test de retención de 20 sesiones; ese intento no capturó el error de filesystem subyacente. La suite del almacén aislada pasó 5/5 y la siguiente ejecución completa pasó 104/104, sin cambiar código ni expectativas. Se conservan ambos logs en staging; no se presenta ese intento inicial como PASS. El producto conserva el aviso no fatal y el contador en memoria cuando no puede guardar preferencias.

La revisión visual usa el renderer real y `DesktopApplicationClient` real contra una fixture owned de snapshots/receipts, sin ejecutar efectos externos ni utilizar conversaciones personales. Se comprobó: Inicio sin icono inicial; envío con Enter sin cambiar de vista; preámbulo y final con contador 2; abrir Historial limpia; una segunda respuesta recibida en Historial no genera pendientes; volver a Inicio y recargar conserva cero; una tercera petición en Inicio genera dos pendientes que siguen siendo dos después de recargar. Se observaron nueve mensajes compartidos y exactamente tres `SubmitUserInput`, sin comandos causados por alternar las vistas. Se comprobó la presentación ES/EN. Esto verifica la interfaz y su integración de proyección, no la calidad de un LLM.

Limitación registrada durante una regresión ampliada independiente: `test_cancel_started_shell_marks_unknown_effect_without_retry` no alcanza su mock de inicio de shell dentro de dos segundos; el mismo fallo se reprodujo con el source anterior a B3. No se cambió Shell/Policy para alterar ese resultado. El intento queda en el staging de validación, fuera de la evidencia histórica.

## Alcance y preservación

No hay cambios en CLI, prompts del modelo, selección de herramientas, Policy, Approval, Grant, networking ni primitives Browser. El transcript sigue siendo propiedad de Application. La presentación detallada de outcomes de herramientas y la unificación de consentimiento corresponden al bloque GUI-B4; este bloque conserva el flujo nativo existente. Las etiquetas de resultados legacy se muestran de forma neutral, sin inferir éxito de una herramienta por la mera existencia de texto.

No se ejecutaron campañas de modelo real, certificaciones históricas, instaladores ni compilación de ejecutables. Se comprobó TypeScript y el bundle de renderer/main/preload. No se hizo staging Git, commit, push, tag ni release. La documentación y evidencia anteriores permanecen byte intactas.
