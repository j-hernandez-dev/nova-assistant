# SEC12-OD-05 — Security Audit persistence (PENDING)

Fecha del contexto del usuario: 2026-10-04. No existe autorización para cerrar
esta decisión en este documento. Se solicitó la elección al usuario después de
implementar y verificar lo independiente. **S7 no es PASS todavía.**

## Lo fijado independientemente

SecurityAuditPort, DTO versionado, codec validado, registros correlacionados y
redacción antes de entregar al port. Audit separado de transcript, EventJournal
y SessionLogger. Una operación sin terminal observado no se transforma en éxito.
No contenido bruto de archivos/bodies/respuestas/output ni valores de environment;
sí nombres, scopes resumidos, command redactado, hashes/identidades observados y
resultados tipados. Sólo valores conocidos: no detector universal de secretos.

La fixture en memoria reside en tests, no es un adapter productivo ni una
retención elegida. La composición normal conserva `security_audit_port=None`.
Ninguna configuración o argumento del LLM activa almacenamiento o da autoridad.

## Alternativas de almacenamiento y recomendación (no implementadas)

| Opción | Ventaja | Trade-off |
|---|---|---|
| JSONL local acotado — recomendada | Simple, inspeccionable, estándar, append y recuperación de tail explícitos | Consultas por scan; rotación/ownership deben implementarse cuidadosamente |
| SQLite local | Índices/consultas y transacciones | WAL, checkpoint, mantenimiento y recuperación más complejos |

Parámetros propuestos, sujetos a autorización: directorio de estado del usuario
fuera del workspace; segmentos de 10 MiB; total 100 MiB o 30 días, primer límite
alcanzado; configurables por el host. Purga sólo segmentos cerrados propios de
Nova. No tocar logs ajenos, evidencia del repositorio ni registros preexistentes
de S0–S6. Definir paths/ownership/rotación segura en el adapter elegido.

La retención puede dejar una operación incompleta. Consultas/reconstrucción deben
mostrarlo, no prometer historia ilimitada o continuidad que ya no existe.

## Durabilidad/fallos y recomendación (no implementadas)

Recomendación: flush+fsync confirmado antes de dispatch con efectos y al terminal.
Error de audit antes del efecto: denegar la operación con error tipado. Error
después: conservar el outcome/efecto observado, informar pérdida de audit; no
inventar rollback ni reintentar el efecto.

Alternativa best-effort: efectos permitidos aunque no se pueda registrar, con
advertencia explícita y aceptación de menor trazabilidad/durabilidad.

Crash/reopen propuesto: validar registros/versión; recuperar sólo registros
válidos; declarar tail incompleto/gaps/corrupción sin inventar terminales. Un
dispatch registrado no demuestra que el proceso inició; un launch/PID sólo se
afirma cuando observado. Falta implementar y probar la política autorizada.

## Límite de autoridad

Ninguna opción es un log OS inmutable o resistente a la propia cuenta del usuario.
Un proceso HOST_UNISOLATED conserva sus permisos normales. Retención/durabilidad
operacional no equivalen a aislamiento físico o conocimiento universal de sus
efectos internos. S8 y la UX general quedan fuera de este trabajo.
