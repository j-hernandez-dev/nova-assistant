# Actividad compacta de conversación — Desktop

Fecha: 2026-10-17. Proyecto: `nova-min/nova-assistant`.

## Resultado

La conversación muestra un encabezado de duración por turno, las respuestas públicas de Nova y una línea compacta de actividad. Durante la generación aparece **Pensando**; cuando existe una herramienta realmente en ejecución, aparece su operación y el comando o recurso correspondiente. Al terminar se muestra **Pensó durante** o **Trabajó durante**.

El encabezado de tiempo y la línea de actividad abren la misma lista de acciones. Cada acción dispone de un segundo desplegable con argumentos/comando y salida. Los identificadores técnicos quedan en diagnóstico opcional. Las respuestas públicas del modelo se conservan; los eventos internos del harness ya no aparecen como chips separados. Las generaciones sin texto no dejan tarjetas vacías.

La duración usa las marcas observadas de Application, conservando la identidad del turno a través de snapshots y recarga. El contador activo se actualiza cada segundo y se detiene al finalizar. Los mensajes históricos sin marcas no reciben una duración inventada. Los resultados antiguos sin receipt tipado conservan su condición de ejecución no confirmada.

## Alcance

- Presentación de Desktop y proyección de metadatos de turno en Electron.
- Interfaz ES/EN; no se traduce ni se altera la respuesta del modelo o la salida de herramientas.
- Sin cambios en ejecución de herramientas, Policy, Approval, Grant, CLI o parámetros de inferencia.
- UNKNOWN, denegaciones y errores conservan su significado; no existen reintentos de efectos desde la interfaz.

## Comprobaciones

- TypeScript: PASS.
- Bundle de fuentes de renderer/main/preload: PASS, sin empaquetar instaladores.
- Pruebas Desktop: **276/276 PASS**.
- Smoke integrado de Windows/Electron: **18/18 PASS**, incluido contador del turno activo, dos niveles cerrados por defecto, recarga sin duplicados, permisos, reconexión e idiomas.
- Inspección visual nativa: apertura desde el tiempo del turno, lista de acciones y detalle individual.
- El smoke usa inferencia programada y backend/herramientas reales con archivos propios. No se requirió otra campaña con el LLM para este cambio de presentación.
- Guard histórico existente: **1629 archivos verificados sin cambios** antes de aplicar. La entrega sólo escribe los archivos de presentación/prueba enumerados y este informe nuevo.

Los intentos del runner y los logs quedan fuera del repositorio. Se corrigieron dos supuestos de las pruebas: volver a Historial tras recargar y seleccionar el contador por el ID del turno activo.

No se realizó staging Git, commit, push, tag ni release.
