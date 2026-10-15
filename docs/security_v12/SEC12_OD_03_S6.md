# SEC12-OD-03 — resolución S6

Estado: **CLOSED para S6**, decisión expresa del usuario del 2026-10-04.

Elección: **Compatible mínimo + pass por operación**. La decisión mínima S4
se conserva y se completa, sin reinterpretarla como autorización anterior de S6.

## Base autorizada

`COMPATIBLE_ENVIRONMENT_NAMES` sigue siendo la fuente de nombres: PATH,
SystemRoot, WINDIR, COMSPEC, PATHEXT, SystemDrive, TEMP/TMP, HOME,
USERPROFILE/HOMEDRIVE/HOMEPATH, APPDATA/LOCALAPPDATA, LANG/LANGUAGE,
LC_ALL/LC_CTYPE, TERM y NO_COLOR. Sólo se copian entradas presentes.
Windows compara identidad de variables sin distinguir case; POSIX sí lo distingue.
No se hereda el resto de os.environ. No se carga .env automáticamente.

## Variables adicionales

- Selección exclusivamente del host/configuración confiable; no del modelo,
  renderer, JSONL ni nuevos argumentos de bash.
- `EnvironmentSelection` toma una copia inmutable de valores y/o nombres a
  resolver desde un snapshot privado de configuración del host.
- ToolRuntime vincula la selección al fingerprint completo de una operación.
  `environment.read` y `environment.pass` tienen scopes exactos de nombre,
  control `APPLICATION_ENFORCED` y forman parte del grant/requestDigest.
- El mínimo implementado exige approval humana vigente para **todo** pass
  adicional. Un ALLOW sintáctico de shell, --yes o un callback legacy no la sustituye.
- La aprobación muestra nombres, valores `[REDACTED]` y riesgo HOST_UNISOLATED.
  CLI y diálogo nativo Desktop usan la misma solicitud Application.
- Se descartan selecciones al terminar, denegar, cancelar o fallar. No hay
  persistencia de valores ni reutilización automática por operaciones posteriores
  o subagentes. El ledger privado de grants y el registro de redacción permanecen
  en memoria para validar/idempotencia/redactar; no se serializan como autoridad.
- Nova/provider/approval credentials, material interno identificado y hooks
  peligrosos no pueden reincorporarse mediante el pass. Se rechazan también
  aliases que contienen un valor interno/provider protegido conocido.

No se crea una pantalla general de gestión de secretos. La extensión autorizada
es una API interna del host (`select_operation_environment`) y un hook opcional
de selección confiable del coordinator; no existe un selector productivo por
defecto que aplique variables indiscriminadamente a todas las operaciones.

## Precisión de herencia

Una variable entregada al proceso raíz **HOST_UNISOLATED puede ser heredada por
sus procesos hijos según el SO**. No se afirma impedir esa herencia. Los
subagentes Nova reciben una nueva base, no el pass temporal de otro lanzamiento;
esto es coordinación Application, no una frontera OS.

S7/SEC12-OD-05 (durabilidad/retención del Security Audit) no se decide ni implementa.
