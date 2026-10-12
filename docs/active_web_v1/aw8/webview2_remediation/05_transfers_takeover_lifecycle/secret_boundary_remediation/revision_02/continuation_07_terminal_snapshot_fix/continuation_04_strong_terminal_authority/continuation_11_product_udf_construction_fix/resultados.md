# Block05 — reparación productiva mínima de UDF construction

PRODUCT_UDF_PROFILE_CONSTRUCTION_FIX = PASS  
C07_TERMINAL_SNAPSHOT_FIX = PASS  
BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PASS  
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS  
SAFE_TO_ADVANCE_TO_BLOCK_06 = true

Cierre prospectivo y aditivo. Los manifests/resultados BLOCKED/PARTIAL anteriores y la corrida 527 PASS / 10 FAIL no se modifican ni recalifican.

## Implementación

La única modificación de un archivo existente es la construcción del UDF en WebView2HostClient. Se añade una primitive Infrastructure para elegir Windows LocalAppData/Nova/Wv mediante API de known folder, no variables de entorno/modelo. No se usa literalmente el root diagnóstico B3.

Se conserva exactamente nova_wv2_<session>_<instance>, bws_/bhi_ + 32 hex lowercase, LifecycleServer, marker de instance, ACL nativa, reparse rejection, Job Object y cleanup. El nuevo root tiene DACL protegida del usuario, marker de ownership/version, comprobación writable y límite de 1024 entradas sin eviction. Un root ajeno o inválido falla cerrado.

MAX_PRODUCTIVE_UDF_PATH_BUDGET = 128 unidades UTF-16 del path completo; en este host = 119. Es presupuesto conservador de admisión Nova respaldado por B3, no claim de límite de WebView2/MAX_PATH ni atribución a una subcausa concreta. Un known folder demasiado largo/no local/no válido falla antes del host, sin fallback largo ni IDs recortados.

No se cambian C#, handlers, Perform, provider, headers, Content-Disposition, DefaultDownloadFolderPath por separado, staging, FILE_DOWNLOAD, Approval/Grant, BrowserTools, outcomes, timeouts ni retries. Dos archivos nuevos: la primitive del root y sus 24 contratos. Ningún test anterior se modifica.

## Validación del mismo candidato

| Etapa | Resultado |
| --- | --- |
| A — construcción UDF/ownership/budget | 24 PASS |
| B — cuatro downloads productivos originales | 4 PASS |
| C — lifecycle/IPC/guard/observations/actions/transfers/takeover/secrets | 399 PASS |
| D — única full Block05 completa | 561 PASS / 0 FAIL / 0 ERROR / 0 SKIP |

D = 537 inventario previo + 24 pruebas nuevas. Los focales se solapan; no se suman como un denominador de cierre. Sin skip/xfail, quality retry, exclusión de casos ni cambio de producto entre focal y full. JUnit completo y stdout originales se conservan con hashes y referencias en regression_results.json/raw_evidence_inventory.json. Duración JUnit de D: 905.905 s.

B ejecuta la semántica productiva completa, no cancel diagnóstico: smoke SUCCEEDED_OBSERVED con payload sintético de 35 bytes/digest correcto; drive-by DOWNLOAD_DENIED sin staging ni .crdownload; completed staging conserva owner/lifetime después de browser close y se descarta explícitamente; ToolRuntime entrega SUCCEEDED_OBSERVED/STAGED dentro del join8 original con Approval/Grant exactos, audit sin gap y retryAllowed=false. La capability verificada sintética del test ToolRuntime sólo acredita wiring, no disponibilidad host/publicOnly.

Runtime real Windows X64: SDK 1.0.4258.31 / Runtime 154.0.4258.62. Se mantiene la configuración existente. Las pruebas directas/sintéticas no se presentan como evidencia nativa; el JUnit distingue IDs y archivos.

## Criterios de cierre

PRODUCT_UDF_PROFILE_CONSTRUCTION_FIX = PASS  
DOWNLOAD_NATIVE_INITIATION = PASS  
DOWNLOAD_DRIVE_BY_DENIAL = PASS  
DOWNLOAD_STAGING_LIFECYCLE = PASS  
DOWNLOAD_TOOLRUNTIME_APPROVAL_PATH = PASS  
CONFIRMED_TERMINAL_CAN_RESUME = PASS  
UNCONFIRMED_TERMINAL_FAILS_CLOSED = PASS  
HUMAN_TAKEOVER_BOUNDARY = PASS  
BROWSER_CONTEXT_EPOCH_INVALIDATION = PASS  
SECRET_NON_EXPOSURE = PASS  
HOST_FILE_SELECTION_AUTHORITY = PASS  
WEBVIEW2_UPLOAD_PATH = PASS  
DOWNLOAD_AUTHORIZATION_AND_STAGING = PASS  
TRANSFER_OUTCOME_INTEGRITY = PASS  
HOST_UDF_CHILD_LIFECYCLE = PASS  
STRONG_TERMINAL_AUTHORITY = PASS  
TERMINAL_SNAPSHOT_PROVENANCE = PASS  
CONTROL_DOCUMENT_ORDERING = PASS  
LATE_EVENT_REJECTION = PASS  
TRUE_SHORT_COMMITTED_DENIAL = PASS  
BOUNDED_TRANSIENT_SENSITIVE_VALUE_POLICY = PASS  
MONOTONIC_SENSITIVE_KNOWLEDGE = PASS  
SCHEMA_AWARE_REDACTION = PASS  
CROSS_DOCUMENT_SECRET_REDACTION = PASS  
MODEL_PROJECTION_SECRET_BOUNDARY = PASS  
SECRET_REGISTRY_LIFECYCLE = PASS  
BLOCK05_FINAL_REGRESSION = PASS  
C07_TERMINAL_SNAPSHOT_FIX = PASS  
BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PASS  
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS  

Confirmed terminal puede reanudar; lineage sensible retirada sin submit/fuente viva de checkpoint deniega SECRET_BOUNDARY_UNCONFIRMED sin nueva observation. Las únicas autoridades terminales siguen SUBMIT_CONFIRMED y TAKEOVER_END_CHECKPOINT. Genuine terminal corto sigue denegado; no se vuelve a reparar ni redefinir secrets/takeover.

SECRET_NON_EXPOSURE se limita a la política aprobada de inputs declarados sensibles/known values y a sus superficies públicas. No es DLP/information-flow universal, secure memory ni forensic erasure.

## Cleanup e integridad

Las fixtures nativas comprueban cierre de controllers/Page, host, Job/process tree y UDF owned; staging tiene lifecycle separado y ownership finito. El caso de staging completado confirma drain del Job, UDF eliminado y staging conservado únicamente hasta discard explícito. No quedan procesos de esta campaña en el snapshot posterior.

Permanecen dos directorios NUEVOS con sentinel foreign/unowned creados por el contrato histórico sin modificar (C y D). El producto los rechaza con OWNERSHIP_MISMATCH/CLEANUP_UNCONFIRMED y no los borra. No se afirma CLOSED para ellos ni se realiza mantenimiento. Root marker y recibos guard durables pueden persistir: no son UDF/staging huérfanos.

Los 36 UDF de la corrida histórica permanecen CLEANUP_UNCONFIRMED, intactos y fuera del root nuevo. No se realizó mantenimiento sobre ellos. Arquitecturas V1/V1.1, AW0–AW8, bloques anteriores, P1/Q1/microprobes/bisección y outputs/XML históricos conservan hashes. La nueva modificación autorizada está registrada before/after; los demás sources permanecen congelados.

HOME/USERPROFILE continúa como deuda heredada; FAIL JSONL histórico permanece preservado. No se ejecuta Core ni se sustituye esa evidencia con un PASS posterior.

## Límites y detención

networkEgressControl = UNKNOWN  
publicOnly = UNKNOWN  
available = UNKNOWN  
AW8 = BLOCKED  
ACTIVE_WEB_CORE = NOT_READY

SAFE_TO_ADVANCE_TO_BLOCK_06=true no inicia Block06. Sin network recertification, tool activation, AW8 E2E, commit, push, tag o release. Se detiene para revisión humana.

