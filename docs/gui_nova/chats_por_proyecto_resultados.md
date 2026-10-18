# Chats por proyecto

## Cambios

- Desktop guarda y recupera una conversación independiente por proyecto. Cambiar de proyecto guarda el chat saliente y muestra el del destino, conservando las fechas y sin volver a ejecutar acciones anteriores.
- Ajustes → **Chats**, después de General, muestra los proyectos por su nombre, sin el prefijo «Chat ·». Permite abrir o borrar cada chat y borrar todos los chats del perfil.
- El encabezado de la conversación muestra **Chat · nombre del proyecto**. El acceso superior al chat solo aparece cuando el proyecto activo tiene conversación.
- Un modal de confirmación nativo de Desktop permite cancelar o confirmar el borrado de un chat, de todos los chats o la retirada de un proyecto. El modal de permisos existente conserva su funcionamiento.
- «Quitar proyecto» explica que se elimina su chat y se retira la carpeta de los accesos de Nova. Los archivos de la carpeta permanecen en el equipo.
- Textos y confirmaciones disponibles en español e inglés. La confirmación admite teclado y mantiene el foco dentro del modal.
- El almacenamiento identifica cada proyecto con su ruta y un hash, evitando colisiones entre nombres parecidos. Los archivos antiguos solo se recuperan cuando su ruta registrada corresponde al proyecto; su borrado no permite que reaparezcan después.

## Validación

- TypeScript y `build:source`: correctos después del ajuste final de nombres.
- 117 pruebas Node correctas: cambio de proyecto, aislamiento de mensajes, borrado, confirmaciones del host, permisos existentes y presentación.
- 55 pruebas Python correctas: persistencia, fechas, conversaciones independientes, errores de guardado, borrado y migración de almacenamiento.
- Inventario CI: 3972 contratos clasificados, sin contratos pendientes de clasificación.
- Electron real en Windows: dos recorridos completos, con ocho comprobaciones de independencia entre proyectos, proyectos vacíos, cancelación, borrado individual y global, retirada de proyecto conservando sus archivos, español/inglés y persistencia tras reiniciar el backend.

Las pruebas usan perfiles y carpetas sintéticos e inferencia simulada. Las decisiones de los modales se inyectan en el host de prueba con su identidad exacta; también se verifica que el renderer principal y los clics sintéticos de la página no pueden confirmarlos. No se ha borrado historial personal ni generado instaladores.
