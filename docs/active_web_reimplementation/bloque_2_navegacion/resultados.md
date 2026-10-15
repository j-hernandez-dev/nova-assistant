# Bloque 2 — Navegación productiva

Fecha: 2026-10-14. **BLOQUE_2_NAVEGACION = PASS**, con un perfil temporal de
diagnóstico preliminar retenido por rechazo de limpieza automática, detallado abajo.

Implementado en `C:/Users/joseh/Downloads/nova-min/nova-assistant`.

## Resultado funcional

El modelo recibe las herramientas Browser junto con archivos, terminal y fetch.
La Application compartida mantiene la página actual entre turnos. No se añadió
clasificador de intención, lanes, activación por slash command ni servidor de
búsqueda obligatorio. El motor arranca al navegar y usa el paquete incluido.

Herramientas disponibles: `browser_navigate`, `browser_observe`, `browser_click`,
`browser_type`, `browser_press_key`, `browser_back`, `browser_forward`,
`browser_reload` y `browser_close`.

Las observaciones contienen texto renderizado y refs opacas; el modelo no entrega
JavaScript, selectores, IDs CDP, epochs, Approval ni Grants. Policy evalúa cada
operación; clic, escritura y teclas pasan por Approval y Grant exactos de un uso.
Los campos introducidos en la página se consideran disclosure. La etiqueta del
botón no se usa como prueba de que el clic sea inocuo.

El servicio conserva Playwright en un único thread propio porque los turnos de
AgentSession pueden ejecutarse en threads diferentes. Sus errores operativos
vuelven al modelo como resultados estructurados. Una pérdida tras el dispatch
produce UNKNOWN y una barrera contra reintentos mutantes hasta una nueva petición
humana y observación. Un clic completado localmente informa `remoteOutcome=UNKNOWN`;
no se interpreta como recibo de una compra, envío ni otro resultado del servidor.

## Evidencia real

El [ensayo final con qwen3.5:9b](runs/model-final.json) pasó con el modelo instalado
Q4_K_M, digest `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`.
Perfil: contexto 8192, temperatura 0.6, top_p 0.95, top_k 20, think=false.
La reserva efectiva de salida fue 1024 según los reports del ContextManager.
No se descargaron modelos ni se cambiaron las preferencias personales.

Se ejecutaron dos peticiones humanas en español desde el cliente CLI sobre la
Application real, con página y archivo propios:

1. Abrir la URL del fixture, pulsar Aumentar una vez, leer README.md y comunicar
   contador y marcador. El modelo eligió `browser_navigate → browser_click → read`.
   El canario recibió un solo efecto y la respuesta indicó `Clicks: 1` y
   `PIEDRA-AZUL`, obtenidos de resultados reales.
2. «En esa página escribe Nova en el campo Nombre, pulsa Enter y dime qué saludo
   aparece». Eligió `browser_type → browser_press_key` sin pedir otra URL y
   respondió `Hola Nova`, presente en la observación.

El actor del harness de pruebas aprueba únicamente las interacciones inocuas del
fixture propio; no convierte un JSON del renderer/modelo en autorización humana.
La ruta productiva continúa exigiendo el actor verificado del CLI o Desktop.

El [smoke nativo final](runs/native-final.json) comprueba JS, input/Enter, clic con
canario, denegación de ref stale y de target DOM cambiado, ausencia de Approval y
Policy DENY antes del efecto. Comprueba enlaces, redirección conservando query y
fragment, historial, recarga y enlaces que solicitan otra ventana. Estos últimos
continúan en la misma vista administrada del host para conservar sus controles
y ciclo de vida. El motor conserva red normal: `HOST_UNISOLATED`, sin claim de
aislamiento de red.

El paquete actual incluye WebView2 Fixed Version 155.0.4283.45, SDK 1.0.4258.31 y
Playwright 1.64.0. Su [receipt](package_receipt.json) registra el assembly del host
`add85e2da7908b21d03e3bba2808a65ff22377ff597b024816e9388d61ff71ca`.
El paquete probado en Bloque 1 se conserva como build en
`dist/browser/windows-x64-block1/`; sus documentos y receipts permanecen intactos.

## Problemas encontrados y corregidos

Los primeros intentos reales se conservan en `runs/model-01.json` a
`runs/model-06.json`. No se presentan como PASS ni como resultados del host final.

- El prompt duplicaba las descripciones ya presentes en los schemas. Junto al
  catálogo ampliado, dejaba muy poco espacio para observaciones en 8K. Un repro
  determinista redujo un resultado Browser de 731 a 76 caracteres, con JSON roto
  y sin el ref del botón. La composición Browser usa ahora un prompt operativo
  compacto con las instrucciones y los schemas disponibles una sola vez.
- El recorte genérico cortaba JSON, URLs y refs. La proyección Browser ahora
  conserva campos completos, limita el texto en fronteras legibles y pagina los
  controles. Si el mínimo no cabe, produce un error de contexto acotado.
- Un paquete Browser antiguo sin cuota restante bloqueaba la preparación del
  siguiente turno. Ahora ese historial opcional puede omitirse; el resultado
  obligatorio más reciente mantiene validación estricta. La prueba cubre ambos
  turnos y refs completos sin aumentar contexto o reserva.
- El segundo intento de fixture usó `_poll` sin renderizar los eventos y no
  midió correctamente herramientas/aprobaciones. Se corrigió el harness del smoke.
- El fixture no fijaba inicialmente `context_selection` junto a las opciones
  Ollama; ahora ambos usan 8192, como el comando CLI documentado.
- El host inicial permitía una ventana WebView adicional sin incluirla en su
  cierre normal. Se manejan esas solicitudes navegando en la misma vista propia.
- Liberar un navegador cerrado ya no requiere consultar su DOM perdido. Esta
  recuperación de cierre pasó las pruebas focales y el job nativo posterior.

`runs/model-07.json` pasó antes del ajuste de enlaces en el host. El ensayo
`runs/model-final.json` repite las dos tareas con el host final y también pasa.
Estos son smokes de desarrollo; no acreditan una tasa de éxito general del LLM.

## Regresión y paridad

[Regresión](regression_results.json): 410 casos distintos aprobados, cero fallos
y cero skips. Incluye AgentLoop, ToolRuntime, Policy/Approval/Grant, fetch,
contexto, prompts, CLI, arquitectura y Bloque 1. Los 15 casos portátiles nuevos
incluyen Approval ausente/denegada, cambios durante aprobación, Grant replay/clone,
límites, UNKNOWN sin retry, runtime ausente y rechazo de JS/selector adicionales.

CLI y JSONL/Desktop usan el mismo ToolRegistry, Policy, servicio y ApprovalGate.
La prueba de backend rechaza aprobación JSON sin proof privado y acepta el
proof exacto de su actor host. No se duplicó lógica en React/Electron.

El inventario tiene 3847 contratos y cero sin clasificar. La ejecución nativa
manual final, [browser-block2 --special](runs/ci-close-final.json), ejecutó un caso
real y pasó; su [receipt nativo](runs/ci-native-close-final.json) confirma efectos
y limpieza. No se suma esa repetición a los 410 casos portátiles, ni se incluye
Ollama en CI ordinario.

## Limpieza y límites

Los perfiles, procesos y listeners de las pruebas finales quedaron cerrados.
No se observaron procesos ejecutándose desde los paquetes al terminar. El
[receipt de limpieza](cleanup_receipt.json) conserva una excepción preliminar:

`C:/Users/joseh/AppData/Local/Temp/nova-browser-profiles/nova-webview-45b4632109ab4b75bdfe4b8a950536c8`

Ese perfil pertenece al diagnóstico inicial de popups y quedó inerte. La revisión
automática rechazó su eliminación manual con «blocked by policy». Permanece
retenido; no se reintentó por otra vía ni se cambió ese resultado a confirmado.
Los builds y diagnósticos de desarrollo también se conservan intencionalmente.

Este bloque administra una página. La ventana es oculta; takeover, contraseñas,
upload/download y Chrome/Edge corresponden a bloques posteriores. La búsqueda
Browser como `web_search` corresponde al Bloque 3. No se modificaron SearXNG,
preferencias personales, transporte fetch, documentación histórica Active Web/HUX,
ni se hicieron staging final, commit, push, tag o release.

Las instrucciones de uso están en [README.md](README.md).
