# Corrección de esperas y comprobaciones de Ollama

## Cambios

- La cancelación se transmite desde el bucle del agente a la instancia de proveedor fijada para el turno y a su petición HTTP. Una vigilancia por solicitud interrumpe su socket durante la espera de cabeceras o de un bloque, sin cancelar otras solicitudes del mismo cliente.
- La cancelación también interrumpe la espera entre reintentos por sobrecarga. El agente comprueba la cancelación antes de procesar herramientas y conserva la presentación interrumpida mediante el estado del turno.
- Una respuesta que acaba sin el bloque terminal se trata como un corte de la generación, en lugar de confirmar una respuesta completa. No se repite automáticamente ese stream.
- Las comprobaciones automáticas de disponibilidad se omiten durante un turno activo. Las comprobaciones explícitas siguen disponibles; el plazo del cliente cubre las dos consultas consecutivas de metadatos del proveedor.
- Un fallo temporal conserva el catálogo anterior como observación y marca la disponibilidad como no confirmada. Los errores tardíos de peticiones ya terminadas quedan asociados a su petición y no se convierten en avisos nuevos del chat.
- La tarjeta distingue «Comprobando conexión», «Estado de conexión» y una configuración pendiente, con sus textos en inglés. Un conflicto de turno explica que se rechazó una acción porque ya hay una tarea activa.
- `project_chats` puede consultar metadatos durante una generación. Los borrados y los cambios de proyecto conservan sus bloqueos. Los errores de transporte de chats se resuelven por su identidad en el cliente propietario, incluidas respuestas tardías conocidas.

## Verificación

- 642 pruebas Python correctas: cliente HTTP, proveedor fijado, sesiones, cancelación, bucle del agente, proveedores existentes, disponibilidad y chats.
- 90 pruebas Node correctas: disponibilidad, correlación de errores, estado de generación, modelos, actividad, proyectos y presentación/traducción.
- Nueve pruebas nuevas de transporte/cancelación, con servidores HTTP locales simulados: espera antes de cabeceras; bloqueo dentro de una línea; cliente compartido; cancelación previa; corte inesperado; ausencia de reintentos o herramientas posteriores; liberación del turno y aceptación del siguiente prompt; clientes inyectados antiguos; cancelación durante la espera por sobrecarga.
- Prueba nueva del servidor JSONL: consulta de chats durante un turno permitida, con borrado y cambio de proyecto bloqueados.
- Electron real en Windows, perfil sintético: consulta durante generación, botón Detener, segundo prompt aceptado, ausencia de conflicto global y ausencia de repetición de la tarea.
- TypeScript y `build:source` correctos. Inventario CI: 3982 contratos clasificados.

Las pruebas de inferencia y los servidores bloqueados son simulados; no se ha vuelto a ejecutar el prompt del juego contra el modelo real. Estas comprobaciones verifican los fallos reproducidos del control de ejecución y conexión. La duración de generación propia del modelo sigue dependiendo de sus recursos y del contexto seleccionado.
