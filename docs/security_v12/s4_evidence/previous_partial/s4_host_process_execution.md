# S4 — Host Process Execution Safety (bloque independiente)

Estado: **PARTIAL**, pendiente de `SEC12-OD-02` y del mínimo S4 de `SEC12-OD-03`.
No es un cierre del gate ni una autorización para S5.

## Base y frontera

Se reimplementó directamente contra Core V1 y SECURITY V1.2 desde el working tree
S3 PASS. No se consultó ni copió implementación SECURITY deprecated.
HEAD: `158b60effa484cd34a58b991f3ee4ca3f808d924`, branch `main`.
Las 110 entradas del manifest S3 coincidían antes de editar. Los archivos previos,
incluida la evidencia S3 con WinError 1314 y la posterior con permiso de symlink,
se conservan; sus manifests históricos no se regeneran con código S4.

`AgentRuntime` sigue usando puertos Core. `ToolRuntime` sigue siendo la ruta común
de tools principales/hijas. Application admite, valida y traduce resultados;
Infrastructure implementa el launcher, pipes y control nativo de lifecycle.
`AgentSessionCoordinator` admite inyección host de un `ProcessExecutionService`
compartido, propagado a subagentes tanto por `agent` como por `StartSubAgent`.
CLI/Desktop conservan el mismo backend. Nombres/schemas públicos no cambian.

## Lo implementado sin elegir defaults

- `ProcessLimits`, `ProcessLaunchRequest`, `ProcessReport` y puerto de launcher en
  Core: configuración explícita, snapshot inmutable, cwd/executable absolutos,
  environment copiado e IDs/digest como correlación. No hay defaults productivos nuevos.
- Binding interno opcional `processBinding` en `GrantRequest`: argv compilado,
  límites, timeout efectivo y `HOST_UNISOLATED` participan del digest. Un binding
  vacío no cambia los digests S1/S2/S3 existentes.
- Revalidación del request/grant ya consumido después de `ToolStarted` y justo
  antes del launch. Revisión, revocación, command/cwd/env y descriptor distintos
  impiden launch. No se consume otra vez el one-shot.
- Launcher parametrizado: `stdin=DEVNULL`, `close_fds=True`, `shell=False`, cwd/env
  explícitos, sin elevación, sin retry ni fallback a otro ejecutable.
- Captura incremental: como máximo 4096 bytes transitorios por lectura y buffers
  stdout/stderr acotados desde el inicio. Se continúa drenando y descartando el
  excedente, sin `communicate()` que almacene todo antes de truncar. Flags por
  stream, límite adicional de texto legacy y corte UTF-8 sin expandir el cap.
- PID/exit, deadline más estricto, cancel, estados de root y cleanup, errores
  tipados y `outcome_unknown`. Todo stop posterior al launch conserva incertidumbre
  sobre efectos, incluso si se confirmó terminación de miembros observados.
- Servicio Application con cupo compartido explícito: sin cola indefinida ni
  resubmisión automática; saturación devuelve `PROCESS_CONCURRENCY_LIMIT` antes de
  launch. No se modificaron cuotas de inferencia/subagentes ni scheduler general.
- Audit mínimo por operación en metadata: command/cwd/executable, correlación,
  PID, tiempos, exit, estados, flags, outcome y clase de control. Se entrega al
  retornar la operación; no es un journal live/durable ni contiene environment
  bruto, stdout duplicado o objetos bearer. Persistencia/rotación/privacy S7 no
  se implementan. No se atribuyen syscalls o cambios internos del shell.
- Mecanismo de environment mínimo con allowlist **obligatoriamente explícita**:
  sin herencia implícita, ni credenciales conocidas, ni variables Nova/provider.
  No se implementa aún UX/grants de variables del proyecto ni redacción completa S6.

## Activación pendiente (no hay PASS productivo)

La inyección explícita está verificada en ToolRuntime y en la Application común.
La composición normal todavía **no instala por defecto** ese servicio ni el
environment mínimo: hacerlo exige las elecciones del usuario. Mientras tanto,
la ruta compatible Core conserva captura legacy posterior al resultado y env
basado en el sanitizer existente. Sus valores anteriores no cierran OD-02/03.

Sí están activos en la ruta compatible el stdin cerrado/handles explícitos y la
última revalidación de launch. No se anuncia como S4 productivo completo.

Una vez decididos límites/base mínima, falta instalar la configuración común,
conectar todas las rutas normales de `bash` al launcher nuevo sin bypass legacy,
probar esa composición por defecto y repetir el gate completo. No debe quedar
una configuración opcional presentada como protección universal.

## Alcance de cleanup y claims

Windows usa un Job Object anónimo/no heredable **sin** límites de seguridad,
FS/red, token restringido, cuotas OS, UI restrictions ni elevación. Assignment
ocurre después de Popen y es best-effort: existe una ventana previa y no se
afirma captura universal de descendientes. `cleanupConfirmed=true` sólo dice
root terminado, EOF de pipes propios y cero miembros **del job asignado**.
Fallo de assignment/query/cleanup produce `PROCESS_CLEANUP_UNKNOWN` y outcome
unknown; no hay downgrade silencioso ni éxito inventado.

Linux/macOS tienen mecanismo de process group, pero no se ejecutó host-real de
S4 en esas plataformas y no se declara su gate aprobado. Un grupo tampoco
confina recursos ni garantiza observar hijos que lo abandonen.

Pipes, handles de proceso y job propios se cierran. Las fixtures de hijos son
finitas y el handshake adquiere un handle de identidad vivo antes de solicitar
stop/salida del padre. El test comprueba ese mismo handle señalado tras cleanup.

S3 sólo media `read/write/edit/glob/grep`. Un shell aprobado puede leer/escribir
fuera del workspace, usar red y lanzar binarios con permisos normales del usuario.
Job/process group, policy y grant no son sandbox ni límites físicos de FS/red.

## OPEN DECISIONS presentadas al usuario

`SEC12-OD-02`:

- Recomendación Equilibrado: stdout 100 KiB, stderr 100 KiB, texto combinado
  100 KiB; default 120 s, máximo 600 s, cleanup 5 s, 2 launches concurrentes.
- Conservador: 50 KiB por stream/texto combinado, mismos tiempos, 1 launch.
- Valores configurables host, no argumentos nuevos del modelo ni quotas OS.
  El primero mejora uso cotidiano; el segundo reduce memoria/cupo a costa de
  más truncamiento y rechazo de operaciones simultáneas. Ninguno está adoptado.

Mínimo S4 de `SEC12-OD-03`:

- Compatible mínimo recomendado: `PATH`, `SystemRoot`, `WINDIR`, `COMSPEC`,
  `PATHEXT`, `SystemDrive`, `TEMP`, `TMP`, `HOME`, `USERPROFILE`, `HOMEDRIVE`,
  `HOMEPATH`, `APPDATA`, `LOCALAPPDATA`, `LANG`, `LANGUAGE`, `LC_ALL`, `LC_CTYPE`,
  `TERM`, `NO_COLOR`.
- Estricto: el anterior sin HOME/USERPROFILE/HOMEDRIVE/HOMEPATH/APPDATA/LOCALAPPDATA;
  menos configuración heredada pero puede afectar Git/toolchains.
- En ambos, no proxies, SSH/Git especiales, NODE_OPTIONS/PYTHONPATH, hooks o
  credenciales por defecto. Pass explícito/UX queda en S6; no se cierra esa parte
  de OD-03. Ninguna lista productiva está adoptada todavía.

Fuentes técnicas primarias consultadas para los helpers nativos:
[CreateJobObjectW](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw),
[AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject),
[QueryInformationJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject),
[TerminateJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject),
[accounting information](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information),
[PeekNamedPipe](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe).
