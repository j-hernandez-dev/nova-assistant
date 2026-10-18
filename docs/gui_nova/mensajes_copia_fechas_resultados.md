# Mensajes, copia y fechas — Desktop

Fecha: 2026-10-17. Proyecto: `nova-min/nova-assistant`.

## Cambios

- Copia de mensajes públicos del usuario y de Nova usando el contenido Markdown original del host; no se copia el HTML renderizado, la salida de herramientas ni los diagnósticos.
- Controles al pie revelados por hover y foco de teclado. Usuario: hora, copiar. Nova: copiar, hora. El espacio se reserva para evitar saltos. En dispositivos sin hover permanecen accesibles.
- Icono de confirmación y **Copiado / Copied** únicamente tras una escritura confirmada por el host. Los errores de copia se muestran sin excepción sin controlar.
- Separadores centrados por día: **hoy / today** y hora del primer mensaje para el día actual; **DD/MM/AAAA** para días anteriores. Se usa el calendario local de Windows y se actualiza al cambiar el día.
- Las fechas observadas nuevas se incluyen opcionalmente en las copias guardadas, dentro de `_nova_display`. Al restaurar se extraen hacia la proyección privada del propietario; no entran al transcript del modelo y no restauran operaciones, Approval, Grant ni resultados de herramientas.
- Los lectores legacy conservan por defecto su formato anterior sin estos metadatos. No hay migración ni asignación de fechas a mensajes históricos que nunca las guardaron.
- Placeholder: **Trabaja con Nova. / Work with Nova.** El textarea recupera su altura de una línea tras enviar o borrar un borrador multilínea; también se ajusta al cambiar el ancho. Padding vertical simétrico.

## Verificación

- TypeScript y bundle de fuentes renderer/main/preload: PASS; sin empaquetado de ejecutables.
- Desktop: **286 pruebas PASS**.
- Backend, conversación, sesión y persistencia: **108 pruebas PASS**.
- Electron Windows: **20 flujos PASS**, incluyendo Markdown con negritas y bloques de código, confirmación de copia, orden de hora/controles, separador diario, prompt multilínea y restauración.
- Inspección visual nativa: prompt alineado y confirmación **Copied** con hora al pie.
- El destino del portapapeles del runner es aislado: se verifica el texto enviado por el trayecto IPC real sin reemplazar el portapapeles personal. La inferencia y los embeddings del smoke son programados; el backend, sus herramientas y la persistencia son reales sobre datos propios.
- Inventario CI: **3958 contratos**, sin adiciones sin clasificar. Las pruebas nuevas de fechas son ordinarias; las pruebas Electron siguen siendo un perfil manual, sin dependencia de GPU/Ollama en cada push.

No se cambiaron Policy, Approval, Grant, los parámetros de inferencia ni el idioma de CLI. No se modificaron informes históricos. No se hizo staging, commit, push, tag ni release.
