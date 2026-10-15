# SEC12-OD-05 — RESUELTA: JSONL local + barreras durables

Fecha de autorización humana: 2026-10-04. El usuario eligió explícitamente ambas
recomendaciones y concretó los requisitos siguientes. El documento anterior
`SEC12_OD_05_S7_PENDING.md` se conserva intacto como historia de la consulta,
no como decisión vigente. Esta ADR sólo autoriza/cierra S7, no S8.

## Decisión autorizada

- JSONL local fuera del workspace.
- Segmentos de hasta **10 MiB** (no dividir registros).
- Máximo **100 MiB o 30 días**, primer límite alcanzado.
- Purga sólo de segmentos **cerrados propios de Nova**. Nunca segmento activo.
- Evidencia histórica/manual previa, repositorio y logs ajenos fuera de política.
- `flush + fsync` antes de iniciar un efecto, al terminal y al cerrar/rotar.
- No se exige `fsync` por cada evento interno.
- Fallo antes del efecto: denegar. Fallo después: conservar resultado observado,
  informar pérdida/gap, no reintentar ni simular rollback.
- Crash: recuperar únicamente registros válidos completos y reportar gaps,
  sin inventar outcomes.

## Concreción de implementación dentro de esta decisión

Composition roots CLI y Desktop/backend instalan el mismo adapter/servicio.
Windows: `%LOCALAPPDATA%/Nova/security_audit/v1`; POSIX:
`$XDG_STATE_HOME/nova/security_audit/v1`, con fallback al estado local del perfil.
No usa config del proyecto, `.env`, argumentos de tool ni selección renderer.
Directorio no alias/reparse y fuera del workspace; se revalida el workspace
actual por registro/admisión, también tras rebinding del host.

Nombre reservado UUID + header de ownership/schema identifican segmentos.
Sólo archivos regulares con un link; archivos ajenos/manuales, links y headers
no propios no se purgan. Locks nativos de coordinación identifican writers
vivos: otro backend no sella/purga sus activos. Un activo huérfano se sincroniza
y pasa a cerrado al reabrir; no se trunca/repara su tail. Luego se aplica la
retención autorizada sobre cerrados, por tamaño total de segmentos y edad del
header (creación). El activo está excluido de la purga por edad. Si activos vivos
consumen la capacidad, se rechaza append antes de sobrepasar el presupuesto,
sin borrarlos. No se garantiza que el filesystem tenga siempre espacio libre.

Registros internos hacen flush para visibilidad; barreras hacen fsync. Creación
también sincroniza header; POSIX sincroniza metadata de directorio cuando puede.
En Windows no se afirma durability de rename ante fallo eléctrico/hardware:
los archivos sincronizados y ambas extensiones se validan al reopen.
Un writer que sufrió fallo queda cerrado para nuevas entregas; ninguna operación
se reejecuta para compensarlo. Cierre normal usa atexit; un crash no depende de él.

Consultas validan newline/schema/campos/tipos/límite y reportan tail, rows inválidas,
duplicados/sequences faltantes y request/terminal ausentes. No reconstruyen bytes
perdidos ni terminales. Retención significa historia acotada, no continuidad
universal; las operaciones sin terminal disponible quedan `not_observed/unknown`.

## Privacidad y límites

Se redacta con el registro S6 antes de persistir; no bearer grants, valores de
environment, output/body/contenido bruto, prompts ni exception traces. URLs sin
credentials/query/fragment. Sólo command/scopes/IDs/observaciones resumidos.
Modo privado del runtime/perfil; no log OS inmutable ni resistente a la cuenta
del usuario. `HOST_UNISOLATED` conserva su autoridad normal. No conocimiento
universal de cambios internos del shell ni claim de aislamiento.

## Alternativas consideradas

JSONL es simple/inspeccionable y requiere scans/rotación. SQLite permite índices
y transacciones pero añade mantenimiento/WAL; no se implementa. Best-effort
fail-open reduce dependencia del almacenamiento, pero admite efectos sin
trazabilidad: no fue autorizado. No quedan parámetros OD-05 pendientes para S7.
