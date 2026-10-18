# Pantalla de carga de Nova Desktop

## Implementación

- La ventana se muestra al tener su primer fotograma. La presentación inicial vive en HTML y CSS críticos, sin esperar al paquete de React.
- Emblema recreado con trazados SVG transparentes: estrella blanca y órbita con sombreado claro. No contiene el PNG, el recuadro negro ni el contorno de la imagen original.
- Brillo cíclico de la estrella y una estela que recorre la órbita. Ambas animaciones respetan `prefers-reduced-motion`.
- Textos iniciales en español o inglés según la preferencia persistida por Desktop.
- La primera instantánea de Application o un error inspeccionable deja ver la interfaz habitual. La disponibilidad de Ollama continúa usando los avisos de configuración existentes.
- Si el inicio tarda más de 15 segundos, ofrece abrir la interfaz ya montada o reintentar una carga de página fallida. No hay reintentos automáticos ni reenvío de conversaciones.

## Validación

- TypeScript y `build:source`: correctos, sin empaquetar instaladores.
- 24 pruebas Node: inicio, preferencias de presentación, ajustes y recuperación del backend.
- Electron sobre Windows, con perfil aislado y proveedor de prueba: carga retrasada, idioma guardado, animación, movimiento reducido y transición a la interfaz normal.
- Entrada de JavaScript cancelada: mensaje localizado, reintento manual y recuperación de la interfaz en el mismo perfil de prueba.

El icono nativo de la aplicación sigue usando los recursos oficiales existentes. El SVG animado pertenece únicamente a la pantalla de carga.
