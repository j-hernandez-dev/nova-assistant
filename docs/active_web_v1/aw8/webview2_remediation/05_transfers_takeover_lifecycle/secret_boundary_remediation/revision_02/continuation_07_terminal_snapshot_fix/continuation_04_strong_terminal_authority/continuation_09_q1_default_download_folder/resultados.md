# Q1 — Default download folder

`Q1 = FAIL`

`DEFAULT_DOWNLOAD_FOLDER_AS_SOLE_CAUSE = EXCLUDED`

`ROOT_CAUSE_DOMAIN = PRODUCT_BROWSER_HOST_CONFIGURATION`

Una única ejecución efectiva. La asignación/getter del directorio corto se confirmó antes de cargar contenido. El recurso fue solicitado y respondido con 200 / text/plain / 35 bytes, sin Content-Disposition. Durante los mismos 25 s de observación no llegó DownloadStarting ni se obtuvo DownloadOperation. No hubo segundo intento, segunda variante ni reparación.

## Medición previa al contenido

| Campo | Resultado |
| --- | --- |
| UDF productivo de esta sesión | 212 caracteres; no acortado |
| DefaultDownloadFolderPath original | 236 caracteres; dentro del UDF |
| DefaultDownloadFolderPath Q1 | 56 caracteres; fuera del UDF |
| Getter después de asignar | Coincide exactamente |
| Directorio existe / escribible / vacío antes de contenido | true / true / true |
| ACL diagnóstica | Protegida, FullControl únicamente del usuario actual |
| ProfileName antes / después | Cadena vacía / cadena vacía, sin modificación |
| SDK / runtime efectivo | 1.0.4258.31 / 154.0.4258.62 |
| Host PID / owner PID | 34252 / 44016 |

Los paths completos requeridos están en [q1_default_download_folder.json](q1_default_download_folder.json); son directorios temporales controlados de diagnóstico. No se leyó ni publicó contenido descargado.

## Control de la intervención

La única propiedad pre-frontera modificada en la copia diagnóstica fue CoreWebView2.Profile.DefaultDownloadFolderPath. Las tres copias nativas derivadas de P1 conservan sus SHA-256; el proyecto/programa productivo real no fue sustituido. Se conservaron environment options, seis settings efectivos, InPrivate, controller, HTML byte-exacto, response/stream, script Perform, argumentos y world. Sin userGesture, Content-Disposition, cambios de staging, Policy o semántica IPC.

El observer requerido obtiene DownloadOperation y establece Cancel=true / Handled=true **después** de recibir DownloadStarting; esa rama no se ejecutó porque el evento estuvo ausente. No se evaluó completion.

La etiqueta interna `mode=P1` del runner se conserva por reutilización exacta; esta ejecución es Q1 y no una repetición adicional de P1.

### Identidades efímeras

P1 ya había confirmado/eliminado su UDF. Q1 utilizó una nueva sesión efímera con la misma construcción productiva de namespace/profile, semántica y longitudes (root de contexto 71, managed root 129, UDF 212); no restauró datos ni refs retiradas. No se afirma igualdad literal del antiguo pathname/GUID ni del RemoteObject entre procesos. El binding objeto/world dentro de Q1 sí fue exacto; las identidades nuevas son propias de esta encarnación. La namespace del UDF/profile permanece por ello entre las hipótesis abiertas.

## Decisión

El cambio aislado al directorio corto, privado y escribible no restauró la frontera nativa en esta ejecución. Se excluye como **causa única de este caso**, sin atribuir causa a longitud, MAX_PATH, ubicación dentro del UDF o ACL.

`first_causal_individual_difference = NOT_IDENTIFIED`

`minimal_fix_candidate = none_confirmed`

Candidatos conservados: UDF/profile namespace; handlers/instrumentation; Perform/activation context; resource callback/stream behavior; scheduling. No se probó otra variable.

## Integridad y límites

46 pins de producto y 105 de fuentes previas sin drift; sólo se añadieron dos helpers test-only. V1/V1.1, 354 artifacts históricos, P1, microprobe, outputs nativos y la corrida 527 PASS / 10 FAIL permanecen sin cambios. Las dos exclusiones de pins antiguos corresponden a reconciliaciones humanas ya autorizadas; sus versiones aceptadas actuales también se verificaron sin drift. Los grupos de pins se solapan y no son un denominador único.

El teardown ordinario del probe reportó cleanupConfirmed=true. No se investigó cleanup como causa. Se retiene el root diagnóstico privado para evidencia. Los 36 UDF históricos permanecen intactos y CLEANUP_UNCONFIRMED.

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

No full Block05, secrets/takeover, Core, Block06, AW8 E2E, commit, push, tag ni release. Se detiene para revisión humana.
