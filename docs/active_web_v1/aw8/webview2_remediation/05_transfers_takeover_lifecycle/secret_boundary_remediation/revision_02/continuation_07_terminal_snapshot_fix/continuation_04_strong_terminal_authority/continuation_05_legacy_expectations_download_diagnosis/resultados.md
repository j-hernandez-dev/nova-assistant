# Six legacy expectations / four download failures — continuación acotada

## Resultado

`FASE_1_LEGACY_EXPECTATION_RECONCILIATION = PASS`  
`FASE_2_DOWNLOAD_ROOT_CAUSE_DIAGNOSIS = INCONCLUSIVE`

Las seis expectations autorizadas y el archivo completo pasaron. No se modificó producto de secrets/takeover ni de transfers. Los cuatro downloads se ejecutaron efectivamente una sola vez cada uno y siguen FAIL. El diagnóstico identifica boundaries concretos, pero **no cierra las cuatro causas internas**. No se implementó reparación funcional ni se cambió un timeout.

Se conservan literalmente:

```ini
BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED
SAFE_TO_ADVANCE_TO_BLOCK_06 = false
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

La corrida previa **527 PASS / 10 FAIL / 0 ERROR / 0 SKIP** permanece histórica y byte-intacta. No se transforma retrospectivamente en 533/4 ni se reejecuta full Block05.

## FASE 1 — reconciliación prospectiva, sin producto

La clasificación se escribió antes de editar/medir: [classification_before_measurement.json](classification_before_measurement.json). Sólo SUBMIT_CONFIRMED y TAKEOVER_END_CHECKPOINT terminalizan.

| Caso | Reason interno requerido | Fuente terminal |
|---|---|---|
| observed_edit_buffers[prefix] | SHORT_COMMITTED_VALUE | Checkpoint vivo; terminal real longitud3 |
| observed_edit_buffers[same] | TERMINAL_CONTINUITY_UNCONFIRMED | Generación sensible retirada; no submit/checkpoint vivo |
| observed_edit_buffers[cross] | TERMINAL_CONTINUITY_UNCONFIRMED | Generación sensible retirada; no submit/checkpoint vivo |
| observed_edit_buffers[history] | TERMINAL_CONTINUITY_UNCONFIRMED | Generación sensible retirada; no submit/checkpoint vivo |
| page_leaf_redaction[opaque-case-4] | SHORT_COMMITTED_VALUE | Checkpoint vivo; terminal real longitud1 |
| page_leaf_redaction[opaque-case-5] | SHORT_COMMITTED_VALUE | Checkpoint vivo; terminal real longitud1 |

Todos los valores/longitudes originales se conservan.

Cambios exclusivamente en `tests/secret_revision02_runner/Program.cs` y las expectations correspondientes de `test_secret_revision02.py`. El runner reutiliza el observer escalar interno C06 y reflexión privada del registry; no añade comando/autoridad IPC ni transmite el material.

La rama de denial exige conjuntamente: edición sensible/knowledge realmente observado, ownership Page/Session, retirement sin witness para los tres escenarios navigation, o snapshot CHECKPOINT exacto y revisiones iguales para los cortos; reason interno exacto; error externo SECRET_BOUNDARY_UNCONFIRMED; no resume/epoch0; capture imposible; conocimiento retenido; serializer cerrado/framing/control-plane válidos; cierre real y registry vacío. No es aceptar cualquier return/error. Un return0 del runner significa que **la prueba de denial esperado** se cumplió, no que Nova reanudó.

Las assertions originales de los casos positivos permanecen intactas. En las seis ramas cerradas no se fabrica una observation para comprobar strings públicos: se demuestra que ninguna puede publicarse. Ni valores, fixtures, secuencias, redacción, autoridad terminal, monotonicidad ni genuine-short denial se cambian.

Validación, en orden:

| Ejecución | Resultado |
|---|---|
| Sólo los seis autorizados | 6/6 EXPECTED_OUTCOME, 0 FAIL/ERROR/SKIP/xfail |
| `test_secret_revision02.py` completo | 24 PASS, 0 FAIL/ERROR/SKIP/xfail |

Los seis pertenecen al archivo24; no se suman como30 casos únicos. Before/after SHA, expectativas y prueba semántica: [legacy_expectation_reconciliation.json](legacy_expectation_reconciliation.json). El producto de46 pins quedó sin drift, antes/después.

## FASE 2 — diagnóstico, no reparación

Se conservaron las fixtures/assertions/driver, las ventanas existentes3s/join8 y la semántica STARTED→UNKNOWN. No hay quality retry, campaña estadística, nuevo secret fix, reclasificación como flaky/Policy/preexisting ni continuación automática.

El harness aditivo tiene dos niveles separados:

- Python: wrappers test-only para prepare/dispatch/IPC/Approval/ToolRuntime/stage y joins; guarda únicamente tiempos monotónicos, enums y IDs opacos; no modifica retornos ni excepciones.
- Native: build diagnóstico externo del mismo proyecto con observadores en copias de TransferRuntime/WebView2Runtime. No modifica los sources productivos. Observa recurso controlado, callbacks/estado, wait/catch y cleanup. Network/Audits/Log sólo como observación CDP, sin setDownloadBehavior, userGesture, request interception, flags, page JS ni nuevo IPC. Registros acotados256, sin contenido/URLs, buffer en memoria y escritura al cleanup.

**Limitación material del harness:** el primer setup smoke falló porque mktemp ya había creado el directorio y el builder intentó mkdir otra vez. El smoke no ejecutó su cuerpo. El cached host ordinario quedó disponible para los siguientes tres, que se ejecutaron una vez con metadata Python pero sin observer nativo. Se preservan ese ERROR y tres FAIL. Sólo se corrigió `mkdir(exist_ok=True)`; se ejecutó únicamente el smoke cuyo cuerpo nunca había iniciado, sin repetir los otros tres. Resultado efectivo: cuatro cuerpos, uno por caso; los cuatro FAIL, y un ERROR de preparación separado. Véase [diagnostic_preparation_failure.json](diagnostic_preparation_failure.json).

No se oculta esa limitación ni se presenta metadata Python como trace native. El build preflight había compilado sin correr ningún cuerpo; su carpeta fue creada directamente, por lo que no ejercitó la colisión con mktemp.

### 1. Smoke — INCONCLUSIVE

Observado en la única ejecución efectiva, runtime WebView2154.0.4258.62 / SDK1.0.4258.31:

```text
prepare → exact validated target → STARTED ack
→ DownloadSlot creado
→ recurso fixture realmente solicitado: 200 / 35 bytes
→ no DownloadStarting observado / slot.Operation=null
→ download.Done.Task.WaitAsync vence
→ TimeoutException → UNKNOWN
→ cleanup posterior y confirmado
```

Primer boundary identificado: **DOWNLOAD_EVENT_NOT_RECEIVED / DOWNLOAD_COMPLETION_TIMEOUT**. El timeout ocurrió a t25035.204ms desde inicio del trace; cleanup comenzó a t25227.944ms y terminó t26959.635ms. No hubo asignación de destino native ni llamada Python stage(). El root de staging inicial sí existía, con0 entries.

La evidencia histórica Interrupted/FileFailed0/35 permanece intacta, pero no se reprodujo en esta ejecución: el fallo actual está antes de crear una operación nativa. Falta determinar por qué el engine no inicia DownloadStarting para la respuesta controlada, y si FileFailed histórico responde a otra decisión/ruta. Los observadores pueden alterar timing; no prueban equivalencia temporal con la certificación.

No se infiere ACL, MAX_PATH, stream disposal, cancel del browser ni fallo de cleanup a partir de FileFailed. Microsoft lo define como error genérico de archivo; hay reasons distintos para access denied y filename too long. [API oficial](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2downloadinterruptreason?view=webview2-dotnet-1.0.3800.47), corroborada por XML del SDK pinneado1.0.4258.31.

### 2. Drive-by — INCONCLUSIVE

CLICK devolvió SUCCEEDED_OBSERVED. Las114 consultas existentes de metadata durante la ventana3s no encontraron DOWNLOAD_DENIED. No hubo entry Python de staging y cleanup terminó correctamente.

Primer boundary: **DOWNLOAD_EVENT_NOT_RECEIVED dentro de la ventana del test**, no una prueba de que el evento nunca pueda emitirse. Falta metadata nativa de esa ejecución para distinguir: suppression antes del handler, callback tardío, otra ruta o ausencia real de download. La documentación vincula DownloadStarting a un download iniciado, no garantiza que cualquier click programático lo inicie. [Evento oficial](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.downloadstarting).

No se atribuye el FAIL a un bug de fixture ni se declara drive-by effect/denial por ausencia de señal. No se aumentó la ventana.

### 3. Completed staging survives cleanup — INCONCLUSIVE

Prepare/resolve/dispatch ocurrieron. El IPC download devolvió nativeStarted=true y nativeOutcome=UNKNOWN después de24.764491s; stage() no fue llamado. Por ello nunca se alcanzaron evidencia positiva Completed, finalización/ownership ni DownloadRef válido.

Primer boundary observable: **native outcome != SUCCEEDED_OBSERVED → adapter UNKNOWN**, antes de la finalización Python. Cleanup ocurrió después del resultado. El root inicial se creó y finalmente se eliminó. Falta nativeState/InterruptReason y la branch Done/timeout/file de esta ejecución; no se infiere completion timeout sólo por su duración.

### 4. ToolRuntime exact Approval — INCONCLUSIVE (boundary de join identificado)

El trace demuestra:

```text
ToolRuntime entra
→ Approval.resolve(approved=true) retorna
→ prepare retorna
→ adapter dispatch entra
→ IPC download entra
→ join8 retorna: worker vivo y sin resultado
→ finally del test solicita cancelación
→ HostIpcError → adapter UNKNOWN
→ ToolRuntime retorna outcome_unknown
→ segundo join termina worker
```

Boundary identificado: **DOWNLOAD_RESULT_JOIN_TIMEOUT** con download aún in-flight. No hubo return previo consumido ni worker exception observado. Approval sí propagó hasta transfer runtime/host IPC; no es evidencia de denial Policy ni de pérdida de resultado entre un completion y Application.

La causa de la espera nativa sigue UNKNOWN: falta callback/state antes de join8/cancel. No se aumentó join8 ni se convirtió cancelación en rollback/no-effect.

## Evidencia faltante y decisión de detención

[download_failure_analysis.json](download_failure_analysis.json) enumera por caso lo observado, lo no demostrado y la evidencia faltante. Los cuatro son INCONCLUSIVE como root-cause completa, aunque smoke y join tengan boundaries específicos identificados. No se propone un fix funcional como causalmente confirmado.

Se solicita revisión humana sobre cómo completar esa evidencia nativa limitada; no se ejecuta otra muestra por iniciativa propia. No hay full regression hasta resolver los cuatro downloads.

## Integridad / cleanup / historia

[manifest.json](manifest.json), [test_results.json](test_results.json), [diagnostic_metadata_evidence.json](diagnostic_metadata_evidence.json), [integrity.json](integrity.json) y los XML/stdout íntegros del root nuevo:

`C:/Users/joseh/AppData/Local/Temp/nova-legacy-download-diagnosis-20261011T083647Z`

Cada ejecución phase2 terminó con host exited, UDF ausente, cleanupConfirmed=true, staging eliminado/0entries. La observación final no encontró procesos/children o UDF/transfer roots owned pendientes del root nuevo. Las pruebas phase1 también exigen cierre de UDF y disposal del registry.

Los46 archivos productivos, V1/V1.1,18 tracked heredados y toda evidencia anterior —incluido527/10— conservan pins. Los grupos heredados pueden solaparse; no se suman como archivos distintos. Las únicas ediciones existentes son los dos archivos de test autorizados; dos archivos diagnósticos son nuevos y test-only, excluidos del build productivo.

Los36 UDF históricos continúan CLEANUP_UNCONFIRMED, sin mantenimiento. HOME/USERPROFILE y el FAIL JSONL previo siguen registrados; no se ejecutó Core ni se reinterpreta su causa. No se afirma PUBLIC_ONLY, network readiness, Active Web disponible, secure memory ni DLP universal.

Sin Block06, AW8 final, READY, commit, push, tag ni release. Detención para revisión humana.

