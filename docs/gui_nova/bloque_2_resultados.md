# GUI-B2 — Preparación real y configuración inicial

Fecha: 2026-10-15. Proyecto: `C:\Users\joseh\Downloads\nova-min\nova-assistant`.

## Resultado

**GUI-B2 = PASS.** Desktop diferencia la conexión de protocolo de la preparación observada del chat local, explica los requisitos pendientes y guarda la selección de modelo confirmada para próximos arranques.

Base: [propuesta de implementación](02_propuesta_gui_nova_y_bloques.md). No se reetiquetan entregas históricas ni se declaran completados otros bloques GUI.

## Comportamiento entregado

| Situación observada | Presentación y acción |
|---|---|
| Inicio/comprobación pendiente | «No listo» y «Comprobando Ollama y el modelo seleccionado…». No se usa el snapshot de conexión como prueba de preparación. |
| Backend desconectado | «No listo», motivo de conexión y recuperación existente. El borrador se conserva. |
| Ollama inaccesible | «No listo» / «Termina la configuración» / explicación para abrir Ollama. **No aparece Abrir configuración** para este motivo. Se puede volver a comprobar. |
| Ningún modelo instalado | Aviso para descargar y seleccionar un modelo, con acceso al gestor actual. No hay descarga automática. |
| Modelo seleccionado ausente | Aviso específico y «Abrir configuración» lleva a Modelos. No se elige una alternativa silenciosa. |
| Modelo sólo de embeddings | No listo: se solicita un modelo de conversación. |
| Modelo instalado con soporte de conversación | «Listo» y envío disponible. Browser, búsqueda, Memory semántica y RAG opcionales no condicionan este estado. |
| Cambio de modelo en curso | Se espera la aceptación y el runtime observado correspondiente. El selector no se actualiza optimistamente. |
| Cambio rechazado/no confirmado | Mensaje visible, sin repetir la operación. Si no llega confirmación después de la aceptación, la espera se limita a 10 segundos. |
| Fallo al guardar la preferencia | Se informa que la selección está activa pero no pudo guardarse para el siguiente inicio. No se finge persistencia ni se revierte el runtime. |

La preparación comprueba disponibilidad y compatibilidad declarada mediante los endpoints de metadatos existentes; no es una garantía de que todas las generaciones futuras tendrán éxito. Un modelo de conversación sin native tool calling no queda bloqueado por ese solo motivo: se conserva el soporte existente del harness. No se concede autoridad a herramientas mediante esta comprobación.

ES/EN cubre los nuevos estados y avisos. El idioma del modelo y de CLI permanece intacto.

## Arquitectura

```text
Desktop host
  → get_readiness(sessionId)
  → Application.get_readiness
  → ProviderManager: catálogo/info del proveedor configurado
  → observación con identidad y revisión del runtime
  → DesktopSessionView.readiness
  → Listo/No listo + requisito pendiente
```

El DTO contiene versión, sesión, proveedor, modelo, revisión, `ready`, motivo, hora UTC, modelos instalados y acción de configuración pertinente. No incluye credenciales, excepciones privadas, Grant ni argumentos de herramientas.

El cliente valida la identidad de sesión/modelo/revisión antes de aceptar una observación. Resultados tardíos, de otro runtime o posteriores a desconexión no pueden volver a marcar «Listo».

La observación usa un worker JSONL separado y único para no bloquear cancelaciones o aprobaciones mientras se consulta Ollama. Hay una comprobación periódica cada 15 segundos, al enfocar la ventana, al cambiar de runtime y mediante «Volver a comprobar», con coalescing y caché mínima de 5 segundos para solicitudes normales. El cliente limita la espera de observación a 20 segundos; los timeouts de red del proveedor siguen siendo los existentes. Un fallo se muestra como estado de preparación, sin duplicar un error técnico en el chat.

`status.ready` conserva su significado de protocolo. No se bloquea el acceso a Modelos/Configuración por estar el chat «No listo». El botón de enviar sí requiere preparación válida; el borrador se mantiene editable y no se borra ante rechazo. Detener/resolver interacciones de un turno existente sigue dependiendo de su protocolo y contratos actuales.

## Persistencia del modelo

Archivo nuevo exclusivo de Desktop:

```text
%APPDATA%\nova-desktop\desktop-runtime-preferences.json
```

Contenido permitido:

```json
{
  "schemaVersion": 1,
  "providerId": "ollama",
  "modelId": "tag-exacto-confirmado"
}
```

Se escribe únicamente cuando coinciden:

1. Una petición de cambio de modelo aceptada por Application.
2. Un snapshot del mismo runtime/proveedor con el modelo exacto y una revisión posterior.

La escritura es atómica, con validación y error no fatal. Un recibo aceptado por sí solo, una selección rechazada, un snapshot incompatible o uno llegado fuera de la espera de confirmación no guardan la preferencia.

Al crear el proceso Python siguiente, Electron utiliza esta pareja como selección predeterminada de Desktop mediante el entorno del hijo. Si el entorno de arranque ya contiene `LOCAL_CLI_MODEL` o `LOCAL_CLI_PROVIDER`, esa elección explícita prevalece y no se mezcla con la pareja guardada. La preferencia GUI tiene prioridad sobre los valores generales de modelo/proveedor del archivo de configuración en ese lanzamiento Desktop; no escribe ni migra ese archivo. CLI iniciado por separado no recibe esa modificación de entorno.

Si el tag guardado fue eliminado de Ollama, se conserva su identidad y aparece «No listo» con el requisito correspondiente. No se descargan modelos, se cambia contexto/output ni se elige otro modelo para evitar el aviso.

El combo del compositor sigue limitado a los tags instalados. El cerebro conserva el catálogo completo. Descargar un modelo ya no provoca un cambio automático de selección.

## Archivos afectados

| Área | Archivos |
|---|---|
| Preparación host | `local_cli/application/providers.py`, `local_cli/application/session.py`, `local_cli/interfaces/jsonl_application.py` |
| Cliente y DTO | `desktop/electron/application_client.ts`, `desktop/shared/application.ts`, `desktop/src/types.ts` |
| Composición/persistencia | `desktop/electron/main.ts`, `preload.ts`, nuevos `desktop_model_preferences.cjs` y `.d.cts` |
| Interfaz | `desktop/src/App.tsx`, `i18n.tsx`, `styles.css`, `components/ModelPicker.tsx`, nuevo `components/ReadinessNotice.tsx` |
| Bundle | `desktop/vite.config.ts` incluye el helper CommonJS nuevo |
| Tests | `tests/test_gui_readiness.py`, `desktop/tests/desktop_model_preferences.test.cjs`, `desktop/tests/readiness_client.test.cjs` |
| CI vigente | `ci/pytest_contracts.json`, `.github/workflows/nova_knowledge_v1.yml`: incorporar pruebas deterministas GUI, sin requerir Ollama ni GPU |

No se modificaron Policy, Approval, Grant, ToolRuntime, el loop del agente, networking web ni las primitives Browser. Los servicios compartidos reciben una consulta de observación aditiva; no cambia la selección lingüística ni la autoridad de efectos.

## Validación

| Verificación | Resultado |
|---|---|
| Readiness Python + regresión de sesión/proveedores | **64 PASS**: 17 casos nuevos de preparación y 47 de regresión. |
| Contratos Python Desktop | **2 PASS, 2 SKIPPED**. Los dos perfiles que requieren Electron/LLM real se mantienen como gates manuales y no se declaran ejecutados. |
| Diez suites ordinarias Node Desktop | **90 PASS**. Incluyen 11 casos nuevos del cliente de preparación y 5 de persistencia, además de puentes/Approval/Memory/Knowledge existentes. |
| TypeScript | PASS: `tsc --noEmit`. |
| Bundles | PASS de renderer/main/preload con Vite. Sin `electron-builder`, `.exe` ni instaladores. |
| UI owned | PASS: Ollama ausente sin botón de configuración, modelo ausente → abrir gestor → seleccionar → Listo; cambio rechazado conserva selección; envío rechazado conserva borrador; etiquetas EN/ES. |
| Ventana mínima | Compositor y acciones de configuración dentro de 600×400, sin desbordamiento horizontal. |
| Inventario CI | **PASS**, 3915 contratos estáticos y cero sin clasificar. Incorporación aditiva de los 10 contratos Python y de las tres suites Desktop de GUI B1/B2; clasificaciones anteriores conservadas. |

La suite Node usa el flag de transformación TypeScript ya empleado por el job CI. Ejecutarla sin dicho flag provoca un error del runner en una suite existente, no un fallo del producto; la ejecución final con el perfil del job pasó completa.

Después de aplicar el candidato, se repitieron desde el proyecto destino: TypeScript, 90 tests Node, los 66 tests Python (más dos perfiles manuales omitidos) y el validador de inventario CI. Todos los checks ejecutados pasaron. Los fixtures visuales y de metadatos no se incorporaron al producto.

### Smoke del servidor productivo JSONL

Se inició la composición real en carpetas owned, con estado y configuración de prueba aislados. Se enviaron peticiones `get_readiness`, sin inferencia ni herramientas:

| Escenario | Resultado observado |
|---|---|
| Ollama personal `127.0.0.1:11434`, `qwen3.5:9b` | `ready=false`, `OLLAMA_UNAVAILABLE`, sin acción de configuración. La conexión fue rechazada. Había proceso de bandeja `ollama app`, pero el endpoint no escuchaba. No se inició/reinició ese servicio. |
| Fixture HTTP owned compatible con la API de metadatos Ollama | `ready=true`, modelo exacto instalado y validado. Se utilizó el adaptador productivo, no un flag de readiness del renderer. |
| Endpoint local inaccesible owned | `ready=false`, `OLLAMA_UNAVAILABLE`. Servidor JSONL permanece operativo y finaliza normalmente. |
| Modelo ausente contra el endpoint owned operativo | `ready=false`, `MODEL_NOT_INSTALLED`, `requiredAction=SELECT_MODEL`. Sin alternativa automática. |

**El perfil live no se presenta como PASS de un Ollama operativo:** verificó el bloqueo honesto existente en este equipo. El estado preparado y los cambios de configuración se verificaron con fixtures deterministas y los adaptadores reales. No se descargó ni cargó un modelo para esta etapa.

## Corrección causal adicional dentro de B2

La revisión detectó que una selección aceptada sin snapshot coincidente podía dejar `pendingModel` indefinidamente. Se añadió terminalización de la confirmación ante snapshot incompatible/fallido y un plazo de 10 segundos tras la aceptación. No se repite `ChangeModel`, no se fuerza otro runtime y no se persiste un resultado no confirmado. Los tests cubren mismatch, error y vencimiento.

## Ejecución y límites

Reiniciar Desktop para cargar el main/preload y backend nuevos:

```powershell
Set-Location "C:\Users\joseh\Downloads\nova-min\nova-assistant\desktop"
npm.cmd run dev
```

Si aparece el aviso de Ollama, abrir Ollama y usar «Volver a comprobar», o esperar la comprobación periódica. Con el servicio disponible, seleccionar un tag instalado desde el combo o desde Modelos. No se requieren flags manuales para activar B2.

No se hizo staging, commit, push, tag, release, instalación de modelos ni cambios de preferencias personales durante la validación. Los fixtures y sus procesos pertenecen únicamente a preparación. Los documentos de B1 y la auditoría/propuesta anteriores se conservan intactos. B3–B8 y sus comportamientos pendientes mantienen el alcance documentado.
