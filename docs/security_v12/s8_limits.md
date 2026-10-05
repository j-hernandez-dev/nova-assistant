# SECURITY V1.2 — límites del producto y claims S8

Plataforma anunciada por esta revisión: Windows con filesystem local NTFS.
Linux/macOS no quedan recertificados por una corrida Windows.

Nova ejecuta comandos con los permisos normales de tu cuenta. El único modelo
es `HOST_UNISOLATED`. No proporciona aislamiento OS. Una approval expresa
consentimiento para el request exacto; no hace confiable un binario ni garantiza
rollback. `AuthorityCeiling`/grants de proceso son intención lógica, no límites
físicos de archivos/red. La policy sintáctica puede fallar al clasificar un script.

| Superficie | Claim limitado |
|---|---|
| read/write/edit/glob/grep | `BROKER_ENFORCED` por S3 sobre objetos/rutas soportados; read ≠ write. Sin fallback directo. Reparse/symlink/junction, UNC, ADS, alias especiales no soportados se deniegan. |
| bash y shell de subagentes | `HOST_UNISOLATED`: control del launch, no confinement físico del padre ni del workspace. S3 no media las syscalls de archivos del shell. |
| red del shell/Git | Autoridad normal host; no firewall ni network-brokered. |
| web_fetch | Cliente `BROKER_ENFORCED`: sólo HTTP(S) público, cada DNS/redirect revalidado; file/private/loopback/especiales denegados. No concede red a otras tools. |
| provider/Ollama | Servicio host separado; local-first, sin requisito cloud. Su red/credenciales no autorizan tools. |
| todo_write/ask_user | `APPLICATION_ENFORCED`; una respuesta conversacional no es aprobación. |
| cancelación y cleanup | `BEST_EFFORT`; cancel requested ≠ termination confirmed. No prueba universal de ausencia de procesos o efectos no observados. Job Object/process groups sirven sólo para lifecycle. |

Límites operacionales autorizados: stdout y stderr 100 KiB retenidos cada uno,
truncated al excederlos; timeout default 120 s, máximo configurable 600 s,
cleanup grace 5 s, dos launches simultáneos. Son límites del capturador/admisión,
no cuotas preventivas OS. web_fetch tiene presupuesto total 30 s (redirects
incluidos), cuerpo retenido 2 MiB, cinco redirects y texto publicado 50.000
caracteres incluyendo marcador, o max_length menor.

Environment compatible mínimo; selección host confiable por operación exacta
para adicionales, con approval humana vigente. No carga .env automáticamente.
Secretos internos/provider/grants/proofs/hooks no se entregan por defecto.
Un valor entregado al root puede ser heredado por hijos según semántica OS;
Nova no impide físicamente esa herencia. Redacción sólo de secretos conocidos,
no detección universal de secretos del disco o contenido arbitrario.

Security Audit es JSONL local fuera del workspace: segmentos 10 MiB, 100 MiB
o 30 días; purga sólo segmentos cerrados propios, nunca activo/ajenos/evidencia
manual. fsync previo al efecto y terminal/cierre/rotación. Fallo previo deniega;
fallo posterior conserva lo observado y declara gap, sin retry ni rollback.
Crash sólo recupera registros completos válidos, no inventa outcomes. Audit no
es inmutable ante la cuenta host. No identifica cada efecto interno del shell.

Frontend presenta, Application decide. CLI requiere TTY humana para aprobar;
Desktop requiere confirmación host exacta. --yes no amplía ceiling, no resuelve
approval humana ni convierte DENY en ALLOW. Texto de archivos/web/RAG/tool
results puede influir en propuestas del modelo, pero no emite grants. Los tests
de injection fuerzan un modelo sintético a obedecer: prueban el boundary host,
no resistencia universal del LLM a prompt injection.

No se requieren sandbox, Sandboxie, contenedores, VM, drivers ni daemons de
seguridad externos. Node/Electron, Python y Ollama son runtimes de aplicación;
las dependencias Desktop instaladas para el gate no son nueva infraestructura
de seguridad. Git/RAG siguen opcionales y su indisponibilidad no bloquea chat.

La matriz `s8_matrix.json` cubre SEC12-INV-001..028. Mapear una prueba o publicar
este texto no equivale a haberla pasado. El estado válido queda en resultados
y manifest con evidencia y hashes; no declarar READY si queda un gate pendiente.
