# Contexto configurable e icono oficial de Nova

Fecha: 17/10/2026. Proyecto: `nova-min/nova-assistant`.

## Control de contexto

Ruta: **Configuración → Conexión y modelo → Tokens de contexto**.

- Deslizador dorado con cinco pasos: **4K, 8K, 16K, 32K y 64K** (4096–65536 tokens).
- Indicador del borrador, marcas seleccionables y opción **Automático**, que conserva la política AUTO del motor.
- Acciones Guardar y Cancelar cambios. Cerrar el modal descarta el borrador.
- El guardado se aplica al siguiente turno y conserva la conversación. Durante una ejecución, los controles esperan a que termine.
- Etiquetas, confirmación y errores en español e inglés. Control nativo de rango con nombre accesible, valor textual y navegación de teclado.

El contexto incluye instrucciones, conversación y resultados de herramientas. La selección manual utiliza la política común de Nova: valida los límites conocidos del modelo, proveedor y recursos configurados. Si faltan los metadatos del modelo antes del primer turno, el host los consulta al guardar, sin iniciar inferencia. Un tamaño rechazado o un fallo al guardar conserva el valor anterior.

Cuando los límites no están disponibles, se mantiene el contrato existente de selección manual sin verificación completa. La aceptación de 64K no demuestra que exista suficiente RAM/VRAM para ejecutarlo. El límite de salida de la respuesta mantiene su configuración propia.

### Persistencia y aplicación

`SetContextWindow` acepta exclusivamente `requestedTokens` como entero: `0` para AUTO o uno de los cinco tamaños. Application valida sesión, revisión y ejecución activa; después guarda atómicamente y actualiza su selección. La petición repetida con el mismo identificador conserva la idempotencia existente.

El servidor de Desktop guarda la preferencia en `<state_dir>/desktop-context.json`. Al arrancar utiliza esa preferencia válida; si falta o está dañada, utiliza `num_ctx` de la configuración de arranque. La configuración de CLI se gestiona por sus mecanismos existentes.

La vista recibe `services.context` con el valor solicitado, el seleccionado para el próximo turno y cualquier error de límites. La interfaz espera la proyección del host; el recibo por sí solo no actualiza el valor confirmado. Los errores de este formulario quedan aislados de los errores de conversación.

## Logotipo oficial

Origen: `C:/Users/joseh/Downloads/Emblema Astral de Órbita Luminosa.png`, de 1254 × 1254 píxeles.

SHA-256 del original: `2fb0f6e794e77945da979f53eacbd570066702c5494df873ad88935b9f3fc294`.

Conversión de formato y tamaño mediante Pillow, conservando el diseño y los colores suministrados:

- PNG para la interfaz, favicon y recursos de escritorio.
- ICO con tamaños 16, 24, 32, 48, 64, 128 y 256 píxeles para Windows.
- ICNS y conjunto de PNG de macOS actualizados con el mismo logotipo.
- La ventana utiliza los recursos públicos en desarrollo y los del bundle al ejecutar la compilación.
- El botón de inicio de la barra lateral utiliza el logotipo oficial. El nombre de producto de Desktop queda como Nova.

## Verificación

- TypeScript: correcto.
- Compilación `build:source`: correcta.
- Suite Desktop: **290 pruebas correctas**.
- Regresión dirigida de contexto, sesión, conversación y fechas: **73 pruebas correctas**.
- Comprobación final de formularios y acciones: **17 pruebas correctas**, incluidas en la suite Desktop.
- Inventario de contratos: **3963**, con las cinco nuevas pruebas Python clasificadas como regresión portable de GUI.
- Electron/Windows: **24 comprobaciones correctas** con perfil temporal, herramientas y persistencia reales; inferencia y embeddings simulados.
- Revisión visual nativa del modal, icono y control; comprobación del estilo calculado de la barra de 6 píxeles y su degradado dorado en el ensayo específico de ajustes.

Evidencia de esta ejecución: `C:/Users/joseh/.codex/visualizations/2026/09/26/01a0dc94-cfd5-78c3-b475-fdf6e91883a0/nova-context-logo/`. Se conservan los intentos y los resultados finales. `context-electron-05/result.json` contiene el recorrido completo; `context-electron-06/result.json`, la revisión específica final de ajustes. Las pruebas no ejecutan un modelo real a 64K ni certifican su consumo de memoria.

Durante una variante que reiniciaba el backend antes de comprobar Memoria, el indicador existente `gap` dejó esos controles deshabilitados. El recorrido final verifica las funciones de Memoria antes del reinicio y verifica después la recuperación de la preferencia de contexto. Este cambio no certifica el uso de Memoria inmediatamente después de un reinicio con un indicador de interrupción pendiente.
