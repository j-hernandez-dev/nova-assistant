# Historial automático y ajustes de Chat

## Cambios

- Desktop recupera el chat guardado del proyecto seleccionado al iniciar y al restablecer el backend. Se usa la operación de restauración de Application; no se reanudan herramientas, permisos pendientes ni ejecuciones anteriores.
- Se elimina el aviso con los botones «Restaurar conversación» y «Descartar». La vista compacta de Inicio continúa disponible y el historial recuperado no genera notificaciones nuevas.
- Ajustes incorpora **Chat**, inmediatamente después de General. «Borrar todo el historial» requiere confirmación y elimina los autoguardados de chat de todos los proyectos del perfil, además de vaciar la conversación activa. Cancelar no envía ninguna operación.
- Application bloquea el borrado durante una ejecución. Un fallo del almacenamiento devuelve un error; la conversación activa se conserva si el borrado no se confirma. El borrado solo enumera los archivos de conversación del perfil y rechaza rutas enlazadas antes de eliminar archivos.
- Las opciones de proyecto pasan a «Añadir proyecto», «Cambiar proyecto» y «Quitar proyecto», con sus equivalentes en inglés. Se conserva «Abrir en el Explorador».
- La parte superior de la barra lateral contiene Proyectos y Modelos. Se retira el botón del logotipo y se conserva el acceso inferior a Ajustes.

## Fechas

- Los mensajes nuevos conservan sus fechas exactas de creación y finalización en los metadatos de presentación persistidos. La restauración y los autoguardados posteriores mantienen esos valores.
- Para archivos antiguos sin fechas por mensaje, se conserva la fecha real del encabezado de guardado como `savedAt`. El historial la identifica como «Guardado el…» / «Saved on…», sin atribuir al mensaje una hora de envío desconocida.
- Los metadatos de fecha se retiran de los mensajes usados para inferencia y no restablecen autoridad de ejecución.

## Validación

- TypeScript y `build:source`: correctos.
- 71 pruebas Node y 50 pruebas Python correctas: presentación, traducciones, persistencia, borrado entre proyectos, errores de almacenamiento y límites de rutas.
- Inventario CI: 3967 contratos clasificados, sin contratos pendientes de clasificación.
- Electron real en Windows, con perfil y proyectos sintéticos: recuperación automática; historial sin avisos de restauración; fechas exactas y fechas antiguas tras reiniciar Python; cancelación sin efectos; borrado de dos proyectos; traducción a inglés; ausencia del historial borrado tras otro reinicio.

La validación usa inferencia simulada y carpetas de prueba aisladas. No se ejecuta el borrado sobre el historial personal ni se empaquetan instaladores.
