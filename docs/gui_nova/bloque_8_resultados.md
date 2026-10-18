# GUI-B8 — Validación Windows

Fecha: 2026-10-16. Proyecto: `C:\Users\joseh\Downloads\nova-min\nova-assistant`.

## Resultado y alcance

Validación funcional de la GUI Nova, con Electron/main/preloads/React y el backend Python Application reales. Se ejecutan flujos integrados con inferencia controlada y tres tareas con `qwen3.5:9b` real. Los perfiles, conversaciones, documentos, recuerdos y archivos de prueba están aislados; no se migran preferencias personales.

Entorno comprobado: Windows 11 Pro X64, versión 10.0.26300; Python 3.14.6; Node del tooling 24.16.0; Electron 33.4.11 (Chromium 130.0.6723.191, Node integrado 20.18.3); Ollama 0.40.3. Esto no acredita otros sistemas, todos los drivers ni todas las versiones de Windows.

## Correcciones pequeñas

1. **Reconexión del backend:** el aviso sólo ofrecía comprobar disponibilidad, aunque el host ya tenía `restartBackend`. Ahora, al estar desconectado, muestra **Reiniciar backend / Restart backend** y usa ese mecanismo existente. Con el backend conectado y Ollama no disponible sólo reconsulta el estado. Un bloqueo en vuelo evita solicitudes repetidas; el rechazo sigue siendo un error visible. No se reenvía el prompt ni se repiten herramientas/aprobaciones.
2. **Fallo de generación Ollama:** `OllamaRequestError` muestra una explicación propia ES/EN que pide comprobar Ollama y la memoria disponible, conservando el código técnico separado. No afirma que cualquier error de Ollama sea falta de memoria ni presenta una generación fallida como éxito.
3. **Comprobación sin instalador:** nuevos scripts `typecheck` y `build:source`. El segundo comprueba TypeScript y genera bundles de fuentes; no invoca electron-builder. Los scripts históricos de empaquetado siguen siendo explícitos. Los scripts nuevos de comprobación invocan las entradas Node locales de Vite/TypeScript. En la shell de validación el PATH heredado superaba 20.000 caracteres y su proceso cmd no encontraba ni `node` ni `where`; los mismos comandos aprobaron con un PATH acotado sólo a ese proceso. No se cambiaron variables globales. README prepara y deduplica el PATH de la sesión y ofrece un fallback acotado para ese error; `dev` mantiene su comportamiento existente.
4. **Fixture existente:** al cambiar de proyecto se recrea RAG mediante su factory. El fixture anterior sólo sustituía la inicialización inicial y terminaba intentando usar embeddings reales. Se mantiene también esa factory bajo el proveedor de embeddings scripted del test. No se cambia el producto RAG ni se descargan modelos.

## Flujos completos

| Flujo de la propuesta | Comprobación y resultado |
|---|---|
| UX01–02, preparación | Contratos de host para Ollama ausente, sin modelos, modelo no apto, selección y estados stale; observación positiva de Ollama real. El selector cambia a otro tag instalado del fixture, espera confirmación y persiste el tag; el backend reiniciado recupera esa selección. |
| UX03–04, Inicio/Historial | Enviar mantiene Inicio; una respuesta final suma una notificación. Recargar no duplica. Abrir Historial elimina la notificación; volver a Inicio conserva la conversación. |
| UX05, actividad | `read` real sobre archivo owned; receipt, salida exacta y tarjeta desplegable. No se interpretan logs como autoridad ni se duplican actividades. |
| UX06–07, permisos/errores | Una superficie nativa de aprobación creada por el host, handshake y permanencia tras recarga; cancelar sin efecto. Contratos ordinarios verifican Allow/Deny, nonce, correlación, sesión, permisos, UNKNOWN y ausencia de reintento. No se automatizó una decisión de permiso real con control de Windows. |
| UX08, desconexión | Terminar el proceso Python del fixture, mantener borrador, reiniciar desde el botón de la GUI y esperar historial restaurado. No quedan aprobaciones ni se repiten efectos. |
| UX09, proyectos | Preview real, cancelación del selector conserva carpeta; añadir cambia el workspace; abrir despacha la ruta confirmada; quitar vuelve al predeterminado. El diálogo y abrir Explorer usan sinks owned; no se abrieron carpetas personales. |
| UX10, modelos | Catálogo real observado; selección instalada confirmada y guardada. Contratos de catálogo/progreso, descarga fallida, operación tardía y cierre de modal conservados. No hubo descargas ni borrado de modelos reales. |
| UX11, Memory/Knowledge/RAG | Adjunto de texto adquirido mediante picker firmado; recuerdo no sensible creado y listado mediante host y store reales; RAG activar/consultar/desactivar con embeddings scripted. Contratos de permisos/sensibilidad permanecen. |
| UX12, ES/EN | Español inicial, guardar inglés y recargar; textos propios cambian y conversación previa conserva su contenido. Diálogos nativos y errores cubiertos por suites de localización. CLI no modificada. |
| UX13, accesibilidad | Foco dentro del modal, Tab cíclico, Escape y devolución del foco comprobados en Chromium; atajo Ctrl+, y etiquetas de Inicio/Ajustes inspeccionados con UI Automation de Windows. El runner habilita el soporte de accesibilidad de Electron como lo haría un cliente de asistencia. Movimiento reducido emulado y regla CSS aplicada. |
| UX14, tarea en curso | Cambio de modelo rechazado con `CONFLICT_ACTIVE_TURN`; recarga conserva tarea; Detener funciona. Contratos de proyecto ocupado permanecen. |
| UX15, ventana | Sin menubar de aplicación; controles nativos de ventana conservados. Compositor sin overflow a tamaño normal, mínimo aproximado 600×400 y zoom Chromium 125 %. El host Windows redondeó el mínimo solicitado a 601×402; se comprueba el tamaño observado. |
| UX16, Browser opcional | Chat/lectura/escritura no dependen de habilitar Browser. No se ejecutó otra campaña Browser ni se cambiaron sus primitives. |

El smoke completo final contiene **18 comprobaciones agrupadas aprobadas**. En zoom 125 % el viewport observado fue 1013×626 y `devicePixelRatio=1.5625`, sin overflow y con Enviar visible. El fixture espera el zoom aplicado; no supone que los píxeles de ventana y CSS coincidan bajo DPI de Windows.

## Modelo local real

Modelo: `qwen3.5:9b`, Q4_K_M, digest `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`. Configuración de inferencia heredada del producto, sin prompt especial del benchmark ni cambios de sampling/output/context. La selección automática vigente produjo contexto efectivo **8192**, observado en `/api/ps` de Ollama. No se aumentó para pasar las pruebas.

| Petición real | Resultado | Tiempo observado |
|---|---|---:|
| `Responde exactamente NOVA_GUI_OK. No uses herramientas.` | Respuesta final visible, sin herramientas | 88,34 s, incluye carga inicial |
| `Lee sample.txt y dime exactamente qué contiene.` | Herramienta `read` completada y respuesta visible | 15,54 s |
| `Crea hola.txt en la carpeta actual con el texto Hola mundo.` | `write` completado; archivo leído por el test y contenido verificado | 15,25 s |

**Intentos anteriores conservados:** los primeros dos intentos no cargaron el modelo por `cudaMalloc failed: out of memory`. El segundo aún tenía aproximadamente 3,9 GB libres. Tras liberar memoria el host reportó unos 7,5 GB libres y las tres tareas completaron. No se cambió de modelo, no se retocaron sus parámetros ni se ocultaron los fallos. Nova presentó error y siguió abierta; no hubo éxito falso ni escritura parcial en esos intentos.

Esto es un smoke de integración, no una medida de estabilidad estadística del modelo ni un cierre retrospectivo de HUX4.

## Regresión y ejecución

| Comprobación | Resultado |
|---|---|
| TypeScript completo | PASS |
| Bundle renderer/main/preloads, sin empaquetado | PASS |
| Desktop ordinario | 267/267 PASS |
| Backend proporcional | 185 PASS, 2 omitidas por gates manuales existentes |
| Electron integrado con proveedor scripted | PASS, 18 grupos |
| Electron + Ollama + herramientas reales | PASS, 3/3 tareas |
| Inventario CI actual | Sin contratos nuevos sin clasificar; smoke Electron/modelo explícitamente manual |

Las dos omisiones pytest son los wrappers históricos que requieren `NOVA_ELECTRON_E2E=1` y el opt-in de Ollama. Los trayectos actuales de GUI/modelo se ejecutan por el runner nuevo, con los selectores y formularios Nova actuales; no se reetiquetan los wrappers históricos.

Suites backend: `test_gui_readiness`, `test_gui_projects`, `test_gui_model_library`, `test_gui_conversation`, `test_gui_activity`, `test_nova_core_phase13_desktop`, `test_application_process_lifecycle`, `test_cli_preferences`, `test_cli_response_delivery`, S2 approvals, M5 Application y K1/K2 Application.

Se corrigieron también supuestos del runner durante su desarrollo: directorio temporal inexistente, arranque de ventana oculto que impedía marcar historial leído, cancelación de picker interpretada como éxito, wrappers de ventana comparados por identidad JS, espera del primer snapshot en lugar de la restauración posterior y equivalencia incorrecta entre bounds nativos y CSS bajo DPI. Los logs de estos intentos permanecen fuera del repositorio; no se ajustaron gates del producto para aprobarlos.

## Cómo repetir

Desde `desktop`, con Node y el Python correcto en PATH:

```powershell
npm.cmd run typecheck
npm.cmd run build:source
node --experimental-transform-types --test tests/*.test.cjs
```

Smoke Windows manual, con una ruta de salida nueva y owned por cada ejecución:

```powershell
$env:NOVA_TEST_PYTHON = $novaPython
$env:NOVA_GUI_TEST_OUTPUT = Join-Path $env:TEMP ("nova-gui-windows-" + [guid]::NewGuid())
.\node_modules\electron\dist\electron.exe tests/gui_windows.electron.cjs
```

Añadir `--real-model` ejecuta las tres tareas con el modelo local instalado y el perfil vigente; exige Ollama y recursos disponibles. No descarga modelos. `--inspect-only --real-model --hold` abre un perfil de inspección del host, **sin inferencia**, y se etiqueta `HOST_ONLY`. El modo scripted sustituye inferencia, embeddings, picker y apertura de Explorer; conserva host, transportes JSONL/IPC, herramientas, servicios, Policy, Approval y Grant reales.

## Archivos, preservación y límites

Cambios productivos: `App.tsx`, `ReadinessNotice.tsx`, nuevo `backend_recovery.ts`, mapeo de error `activity_presentation.ts` y texto `i18n.tsx`; dos scripts npm. Pruebas: `backend_recovery.test.cjs`, ampliación de `activity_presentation.test.cjs`, runner manual `gui_windows.electron.cjs`, mantenimiento de `tests/desktop_backend_fixture.py`. Inventario/workflow CI y README actualizados.

Los **1629 documentos anteriores** se verifican byte por byte antes/después de la entrega. No se modifican las evaluaciones anteriores, los estados PARTIAL, la CLI, Policy/Approval/Grant, las primitives Browser, Memory ni Knowledge de producto. Sin staging Git, commit, push, tag, release, instalador o nueva compilación `.exe`.

Los artefactos de ejecución y perfiles sintéticos están bajo el staging externo `nova-gui-b8-staging` de esta tarea. Se cierran las ventanas/backend owned al terminar. Ollama se inició para la validación y puede permanecer disponible para las pruebas del usuario. No se limpian carpetas personales.

No se probaron Narrator/NVDA, contraste alto del sistema, todas las combinaciones de varios monitores/DPI, todos los formatos documentales ni una descarga grande de modelos. La inspección visual y los contratos no equivalen a una certificación WCAG completa. El apagado/reinicio real probado fue el backend owned; Ollama ausente/recuperado se cubre con probes deterministas y su disponibilidad positiva real, sin interrumpir el servicio global durante las tareas.

GUI_B8_VALIDACION_WINDOWS = PASS
READY_FOR_HUMAN_REVIEW = true
