# S4 — Host Process Execution Safety

Estado: **PASS**, gate cerrado en Windows el 2026-10-03. Único modelo:
`HOST_UNISOLATED`. No se implementó S5. Resultados y hashes en
[s4_resultados.md](s4_resultados.md) y [s4_manifest.json](s4_manifest.json).

## Base y fronteras

Reimplementación directa contra Core V1 y SECURITY V1.2, desde S3 PASS, sin
consultar/copiar/migrar SECURITY deprecated. Branch `main`, HEAD
`158b60effa484cd34a58b991f3ee4ca3f808d924`. Working tree preexistente preservado.

AgentRuntime sólo consume contratos/puertos Core. Application decide y coordina
admisión, policy, approval, grant y traducción de resultados. Infrastructure
implementa launcher, pipes y lifecycle nativo. ToolRuntime es la ruta común
para las tools principales/hijas. CLI y Desktop conservan el mismo backend
AgentSessionCoordinator y los schemas/nombres públicos Core; `bash` no cambia.

## Activación productiva y binding

ToolRuntime instala automáticamente ProcessExecutionService con los defaults
aprobados cuando hay ShellTool. No hace falta una inyección opcional para activar
S4. Si el servicio falta, se rechaza con `PROCESS_LAUNCHER_UNAVAILABLE`; no se
ejecuta el adapter legacy. AgentTool y StartSubAgent propagan el mismo servicio
a los hijos, incluidos background: comparten cupo, no crean uno nuevo por hijo.

`ProcessLaunchRequest` es un snapshot interno inmutable con command, argv host
compilado, cwd/executable absolutos, environment efectivo, timeout y límites.
`processBinding` integra argv/límites/timeout/modelo en el digest de GrantRequest;
un binding vacío conserva los digests previos. El environment efectivo también
queda ligado. Policy no constituye prueba de efectos de un comando.

Después de waits/approval y de ToolStarted se revalida el request/grant
consumido, sin consumir nuevamente el one-shot. Se vuelve a validar justo antes
de Popen. Command/cwd/env/descriptor, revisiones, revocación y liveness distintos
impiden launch. La configuración vigente y el snapshot aprobado deben coincidir.

El one-shot grant autoriza launch; su expiración no constituye lease físico de
todos los efectos posteriores. La supervisión respeta el deadline Core y el
timeout efectivo aprobado. No se añade artificialmente un cap de cinco minutos
por el TTL de launch al máximo aprobado de 600 s.

PlatformShellExecutor permanece como facade compatible sobre el **mismo**
HostProcessLauncher bounded, no como fallback alternativo. Un cwd explícito
relativo de un caller compatible se convierte una vez a absoluto sin os.chdir.
ShellTool proyecta el ProcessReport nativo al resultado tipado/legacy. El adapter
para executors no nativos inyectados se conserva para compatibilidad/test; no
se alcanza desde las rutas agentic normales de ToolRuntime.

## Defaults y environment aprobados

Decisiones exactas y limitaciones: [SEC12_OD_02_03_S4.md](SEC12_OD_02_03_S4.md).

- stdout y stderr: 100 KiB retenidos **cada uno**.
- Vista legacy combinada publicada: 100 KiB incluidos marcadores.
- Timeout default 120 s, máximo efectivo 600 s, cleanup grace 5 s.
- Hasta dos launches simultáneos en el servicio compartido principal/hijos.
  El tercero recibe PROCESS_CONCURRENCY_LIMIT sin PID, launch, cola o retry.

Son límites operacionales, no cuotas preventivas OS ni reducción de autoridad.

El environment de launch contiene únicamente los 20 nombres Compatible mínimo
documentados en la decisión, con denylist/prefijos sensibles prevaleciendo.
Se excluyen credenciales Nova/provider/grants y hooks/inyección no necesarios.
El contexto Core original y el environment global del provider se conservan;
se filtra una copia efectiva que participa del digest y se entrega a Popen.

Preservar PATH/perfil/configuración permite compatibilidad normal, pero un
binario puede leer credenciales/config/hook files con permisos del usuario.
S4 no impide ese acceso ni analiza todo el output. Modelo completo
Environment/Secrets, pass/UX/redacción permanecen en S6.

## Canales, captura y outcomes

Popen usa cwd/env explícitos, `stdin=DEVNULL`, `close_fds=True`, stdout/stderr
PIPE y `shell=False`. El host selecciona el intérprete; el LLM no cambia el
ejecutable. No runas/UAC/elevación, retry ni fallback de seguridad.

La captura incremental usa como máximo 4096 bytes transitorios por lectura,
buffers acotados desde el inicio y drenaje/descarte del exceso. No se almacena
todo antes de truncar con communicate(). Flags por stream y `truncated=true`
global; UTF-8/publicación y marcadores permanecen dentro del cap. PID/exit/outcome
se conservan. Las consultas fijas de descubrimiento/versiones del host no son
commands del LLM; no se afirma aquí un límite general de todos los procesos de Nova.

Estados root y cleanup son distintos. Cancel/timeout posteriores al launch
devuelven `outcome_unknown` con efecto desconocido aun si cleanup se confirmó.
Falta de executable/prelaunch refusal no inventa PID/efecto. Replay idéntico
devuelve el mismo resultado; replay cambiado se rechaza; no retry automático.
ToolRuntime conserva un terminal especializado Core por operación.

## Cleanup y alcance real

Windows usa un Job Object anónimo/no heredable, sin cuotas OS, token restringido,
restricciones UI/FS/red, breakaway especial ni elevación. Assignment ocurre
**después de Popen**, best-effort: existe una ventana y no se certifica captura
universal de descendientes. `cleanupConfirmed=true` significa root terminado,
EOF de pipes propios y cero miembros **del job asignado**. Fallos de
assignment/query/cleanup producen PROCESS_CLEANUP_UNKNOWN/outcome_unknown.

Pipes, handle de proceso y job propios se cierran. Fixtures de hijos adquieren
un handle de identidad vivo, hacen handshake antes del stop/root exit y
comprueban ese mismo handle señalado tras cleanup.

POSIX dispone de process groups best-effort, sin evidencia host-real S4 en
esta máquina. No se declara certificación Linux/macOS ni contención física.
S3 media sólo read/write/edit/glob/grep; un shell aprobado sigue pudiendo
acceder fuera del workspace, usar red y lanzar binarios con permisos de usuario.

## Audit mínimo y deuda diferida

ProcessExecutionService devuelve registros retrospectivos de launch/terminal por
operación con command/cwd/executable, correlación/digest, PID, tiempos, exit,
estados, flags y outcome. No duplica stdout ni environment ni objetos bearer.
No es audit live/durable ni observa syscalls. Persistencia, redacción de command,
retención/privacy completa y journal de seguridad quedan para S7.

SEC12-OD-02 está cerrada. Sólo el mínimo S4 de SEC12-OD-03 está cerrado; S6
completa su alcance. No quedan OPEN DECISIONS que bloqueen S4. Core OD-06 de
cuotas generales de LLM/subagentes no se cierra mediante este cupo de launches.
La limitación heredada de workspace rebinding no se modificó como mejora adyacente.

El informe/manifest PARTIAL previo están archivados byte por byte en
`s4_evidence/previous_partial`; todos los raw logs previos, incluida evidencia
S3 WinError 1314 y symlinks posteriores, permanecen intactos.
