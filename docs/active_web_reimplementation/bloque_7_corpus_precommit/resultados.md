# Bloque 7 — corpus funcional, correcciones y pre-commit

Fecha local: 2026-10-14 (America/Mexico_City).

Repositorio revisado: `C:\Users\joseh\Downloads\nova-min\nova-assistant`.

## Resultado y alcance

Se corrigieron fallos de entrega de respuestas y cancelación de la CLI. Se revisaron el corpus con el modelo local real, la integración Browser existente, el inventario CI, los workflows, los ignores y el README. No se compiló un ejecutable ni se realizó staging, commit, push, tag o release.

El corpus completo original conserva **8/10 tareas con comprobación completa**, **10/10 con respuesta visible** y **0 crashes observados**. El diagnóstico HTML posterior pasó por separado; no reemplaza los fallos ni cambia el denominador original. No se declara una nueva certificación Active Web ni se cambia retrospectivamente ningún estado HUX.

`READY_TO_COMMIT = false`: este checkout comenzó con **3813 archivos tracked eliminados**, 656 modificados y 168 untracked respecto a su HEAD de Active Web. El alcance de esos cambios previos necesita revisión humana antes de seleccionar el commit. La copia reducida no se restauró ni se modificó para aparentar un árbol limpio.

## Por qué faltaban respuestas

El traceback aportado carga módulos de `nova-local-cli\nova-assistant`, aunque se esperaba usar `nova-min\nova-assistant`. La instalación editable del entorno `nova-precommit-venv` apuntaba al checkout anterior. Lanzar desde el directorio personal o Downloads hizo visible esa diferencia. Se reinstaló el paquete editable desde `nova-min`; la comprobación desde fuera del checkout confirma la nueva ruta. Esto no migró configuración personal.

Se encontraron además causas en el código actual:

1. La espera de eventos ejecutaba `_snapshot_unlocked()` en cada poll, aproximadamente cada 20 ms. Esa operación reconstruía y redactaba todo el historial bajo el lock de la sesión, incluso cuando no había una pérdida de eventos. Ahora el snapshot se obtiene mediante un proveedor diferido, únicamente para recuperar un gap/evento demasiado grande. La redacción sensible y las validaciones de sesión/cursor se conservan.
2. La CLI dependía de deltas para mostrar la respuesta. Un runtime que devolviera sólo `final_content` podía completar el turno sin imprimirlo. Al recibir el terminal, la CLI consulta una vez el estado canónico y muestra el final que falte. Una respuesta parcialmente transmitida imprime únicamente el sufijo pendiente. Los fallos/cancelaciones recuperados desde snapshot también tienen explicación visible.
3. El segundo Ctrl+C podía escapar mientras se esperaba la cancelación o se despachaba `CANCEL_TURN`. Ambas rutas están protegidas. Si detener la ejecución sigue sin confirmarse, se informa de esa incertidumbre sin inventar un terminal ni rollback.
4. En la composición sin Browser, el prompt repetía descripciones largas ya incluidas en los schemas. Los tests de contexto conservador de 4K agotaban el presupuesto después de herramientas/approvals y no podían producir el final. Sólo esa repetición se acortó a la primera frase. El contexto, las reservas y los schemas completos permanecen iguales. El prompt compacto Browser no se cambió.

La CLI muestra `Working…` una vez por turno en modo normal. El modo debug identifica la ruta del código cargado. El guard existente de respuestas vacías sigue permitiendo una única reemisión y termina con una explicación si no obtiene contenido; no produce un éxito ficticio.

El `SECURITY_AUDIT_PRE_EFFECT_FAILED` del registro original pertenecía al checkout anterior. No se borró ni se reparó el audit personal para eludirlo, y no se afirma haber diagnosticado su almacenamiento privado. La prueba actual de error de audit conserva la prohibición de ejecutar antes de registrar el efecto.

## Validación

Los resultados y las identidades exactas están en `local_preflight_results.json`, `source_manifest.json` y `preflight_candidate_identity.json`. Los recuentos de distintas ejecuciones solapadas no se suman como tests diferentes.

| Verificación | Evidencia |
| --- | --- |
| Respuesta vacía, final sin deltas, prefijo parcial, recuperación de snapshot, doble Ctrl+C y eventos/CLI | `response-final-complete.xml`: 73 casos PASS, resumidos en `local_preflight_results.json` |
| Regresión focal adicional de prompt, schemas, AgentLoop, subagents y terminal | `focused-final.xml`: 277 casos PASS; intento anterior a los últimos ajustes de proyección, conservado con su identidad |
| Security | 666 casos PASS |
| Memory | 789 casos PASS |
| Knowledge | 1014 casos PASS |
| Desktop | 68 tests PASS y TypeScript `--noEmit` PASS; sin build de Electron |
| Core completo | 2906 casos seleccionados: 2899 PASS y 7 skips preexistentes; resultado y selección positiva en `local_preflight_results.json`, bajo `officialJobs.core` |
| Inventario | 3905 funciones estáticas clasificadas; cero sin clasificación |
| Workflows | Tres YAML válidos, triggers y rutas comprobados; permisos `contents: read`. `actionlint` no estaba instalado |
| Entrada real de CLI | Desde carpeta externa y perfil owned: fuente correcta, respuesta visible, exit 0, sin traceback; `cli_entrypoint_evidence.json` |
| Browser nativo | 15 checks focales PASS sobre páginas owned; `native_regression.json` |

La primera ejecución ordinaria detectó expectativas antiguas que no contemplaban Browser opcional, `keep_open`, explicación tras respuesta vacía o refresco de schemas. Se actualizaron las comprobaciones de regresión sin regenerar el golden histórico. Un test de variables de entorno usa ahora la sintaxis del shell real. Tres tests que comparan bytes exactos de un candidato M8/K7/K8 histórico pasaron a la clasificación histórica explícita; conservan sus asserts y evidencia. Las pruebas funcionales actuales de subagents, Memory y audit siguen seleccionadas.

Se conservan los intentos fallidos previos. Un intento Core intermedio fue invalidado por cambios de código/tests durante su ejecución; no se usa como gate final. El preflight definitivo se ejecutó con las fuentes fijadas en `preflight_source_freeze.json` y se comprueba que no derivaron. Una importación sintética grande que excedió su espera durante la ejecución concurrente pasó al repetirla aisladamente y en Knowledge final; no se aumentó su timeout.

## Corpus con qwen3.5:9b

Perfil: `temperature=0.6`, `top_p=0.95`, `top_k=20`, `num_ctx=8192`, `think=false`. No se descargó ni cambió el modelo. No se estableció un límite especial de output para favorecer estos resultados.

| Caso original | Resultado observado |
| --- | --- |
| Noticias de México ES | `web_search → browser_navigate`, fuente owned leída y resumida: PASS |
| Noticias EN | Search, navegación y observación: PASS |
| Contenido generado por JavaScript | Marcador real recuperado: PASS |
| Seguir enlace | Navegación y click con referencia observada: PASS |
| Click aprobado | Canario del fixture ejecutado exactamente una vez: PASS |
| Browser + README | El modelo eligió `web_fetch` para loopback: denegado correctamente; leyó README y explicó el bloqueo. Tarea parcial |
| Crear HTML | Receipt de escritura real a `create_html/catalogo.html`; no se encontró en el destino exacto esperado por el corpus. Tarea parcial |
| Lectura coloquial de README | Read y marcador real: PASS |
| PowerShell explícito | Receipt de comando y resultado real: PASS |
| Pregunta normal | Respuesta sin herramientas de efecto: PASS |

Los snippets, noticias y marcadores de este corpus son sintéticos. No se presentan como noticias reales obtenidas de Internet. El modelo ve el catálogo operativo y elige herramientas; no se añadieron regex de intención ni lanes para estas frases.

El diagnóstico HTML posterior capturó los argumentos exactos y confirmó escritura en `catalogo.html`, existencia, tamaño y SHA256. Es evidencia de que la creación puede completarse y responder en este perfil, sin afirmar estabilidad 100%, belleza visual ni certificación de autocontención/rendering. No se parcheó una ruta elegida por el modelo ni se amplió filesystem scope. Los contadores de generaciones/approvals del corpus original tenían un defecto de instrumentación y se marcan como no fiables; no se usan como prueba de cero aprobaciones.

## Repositorio y documentación

El README se reorganizó alrededor de instalación editable desde el checkout correcto, uso natural, Browser incluido/default, Chrome/Edge opcionales, comandos canónicos, datos locales, permisos y checks de desarrollo. Se corrigieron dependencia `pypdf`, modelo recomendado y enlace a `LICENSE`. Se distingue el componente generado de Browser de una instalación Python limpia que aún no lo contiene.

`.gitignore` conserva los datos locales, entornos, caches, `bin/obj`, dependencias Node y `build/dist` fuera del versionamiento. Se añadió la ruta precisa de configuración local `.claude/settings.local.json`. La regla global de logs se acotó a logs runtime de raíz/Desktop y herramientas Node para dejar visibles los receipts documentales. No queda ningún archivo tracked cubierto por las reglas. No se ignoraron fuentes, fixtures requeridos, matrices ni manifests.

Los tres workflows tienen permisos de lectura explícitos. Se preservó su separación entre contratos ordinarios, tests nativos/manuales y evidencia histórica. `/help` anuncia los mismos 35 comandos que los handlers; `/fetch` es el comando canónico y no se reintrodujeron aliases redundantes.

El inventario completo, archivos grandes, probes de ignores, búsqueda de patrones literales de credenciales, estado Git e integridad están en los recibos de este directorio. Los archivos grandes detectados pertenecen a evidencia histórica Memory; no se ocultaron ni borraron por su extensión o tamaño. El escaneo literal no sustituye una garantía universal sobre secretos.

## Preservación y limpieza

`historical_preservation.json` verifica los 1601 archivos documentales existentes al entrar en este bloque. No hubo restore-by-hash. Las 3813 eliminaciones previas se distinguen de cualquier cambio nuevo de esta ejecución.

Los listeners, procesos Browser y perfiles temporales del corpus y del smoke nativo tienen receipts propios de cleanup. Los outputs de preflight y el perfil de la CLI de prueba se conservan bajo el directorio owned de Temp para diagnóstico; no son corpus de producto ni datos personales migrados. Los recursos históricos con cleanup no confirmado conservan su estado y no se volvieron a borrar.

## Revisión humana

La entrega de respuestas de la CLI queda corregida y comprobada. Las limitaciones observadas del modelo permanecen registradas. Antes de hacer commit se debe revisar el conjunto ya existente de eliminaciones/reemplazos del checkout reducido y seleccionar expresamente los cambios que se quieren versionar. No hay archivos staged ni autorización de release.

```ini
CLI_RESPONSE_DELIVERY = PASS
GITIGNORE_AUDIT = PASS
CI_INVENTORY = PASS
GITHUB_ACTIONS_CONFIGURATION = PASS
LOCAL_CI_PREFLIGHT = PASS
CORPUS_COMPLETION = PARTIAL
READY_TO_COMMIT = false
COMMIT_PUSH_TAG_RELEASE = NOT_PERFORMED
```
