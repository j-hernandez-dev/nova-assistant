# SECURITY V1.2 — S1: contratos y autoridad lógica

Fecha: 2026-10-03. Modelo de procesos: `HOST_UNISOLATED`.

Este documento describe la implementación nueva de S1 contra Nova Core V1 y SECURITY V1.2 §11, §12 y §29. No incorpora código del proyecto SECURITY deprecated. Los contratos están implementados y probados; su composición con Policy/Approval/ToolRuntime corresponde a S2 y todavía no modifica la ejecución productiva existente.

## Fronteras y significado

`local_cli/core/security.py` contiene valores y algebra independientes de ejecutores/UI; sólo importa DTOs de `local_cli.core.contracts`. `local_cli/application/grants.py` contiene el servicio confiable `GrantIssuer`. AgentRuntime, ToolExecutionPort, ExecutionContext, Application API, frontends y schemas públicos permanecen intactos.

Un grant autoriza una solicitud de Nova. No reduce los permisos del usuario Windows ni limita todos los efectos que pueda producir un proceso. `process.execute`, `process.spawn` y cualquier scope `PROCESS_REQUEST` exigen `ControlClass.HOST_UNISOLATED`. `BROKER_ENFORCED` identifica una superficie que debe ser realmente mediada; su declaración en S1 no implementa ni certifica el broker futuro de S3.

No hay sandbox, adapters de seguridad externos, puerto de sandbox, fallback ni nuevos claims de aislamiento. El ledger interno tampoco protege frente a código hostil con ejecución Python arbitraria dentro del mismo proceso/cuenta.

## Contratos Core

| Contrato | Semántica implementada |
|---|---|
| `Permission` | Identificador extensible como `filesystem.read`; comparación exacta, sin jerarquía implícita read→write. |
| `ResourceScope` | Archivo exacto, árbol por segmentos, URL exacta/origin, request de proceso exacto, variable de entorno, repo o sesión. Sin wildcard implícito. |
| `ControlClass` | `APPLICATION_ENFORCED`, `BROKER_ENFORCED`, `HOST_UNISOLATED`, `BEST_EFFORT`; la intersección no cambia la clase. |
| `Capability` | Permission + scope + clase + restricciones inmutables. |
| `AuthorityCeiling` | Techo lógico instalado por el host, ID/revisión/fingerprint y conjunto finito de capabilities. |
| `GrantSubject` | session/turn/operation/toolCall/agent y linaje explícito de padre. |
| `GrantLifetime` | Intervalo UTC `[not_before, expires_at)` y `one_shot=True` por defecto. |
| `GrantRequest` | Snapshot canónico interno y `request_version=1`; no es una API pública. |
| `CapabilityGrant` | Valor inmutable de delegación; construir/copiar un objeto no prueba emisión. |
| `SecurityError` | Código tipado acotado; el mensaje no incluye argumentos, rutas ni secretos. |

Los diccionarios se copian y congelan recursivamente; listas se convierten a tuples. No se admiten objetos arbitrarios ni NaN/infinito. Límites: profundidad 32, 10 000 nodos por snapshot, strings hasta 65 536 caracteres, claves/labels hasta 512, enteros signed 64-bit y hasta 128 capabilities por colección. Strings con surrogate Unicode inválido se rechazan antes de construir el digest. Los labels y revisiones tienen validación estricta; bool no pasa como revisión numérica.

### Algebra conservadora

`Capability.covers(child)` requiere permiso y clase exactos, scope incluido y preservación de todas las restricciones del padre. Cada restricción es una condición opaca de igualdad exacta; añadir condiciones atenúa, quitarlas/ampliarlas no. La comparación usa JSON canónico, de modo que `true`, `1` y `1.0` no se confunden. No se inventa semántica de maxBytes, duración o regex por el nombre de una clave.

`Capability.intersect` devuelve el scope más acotado y la unión compatible de condiciones, o `None` si no puede representar una intersección demostrada. `AuthorityCeiling.intersect` intersecta pares de capabilities; un resultado vacío no puede emitir una request con autoridad. El fingerprint incluye ID/revisión/contenido completo; orden y duplicados idénticos de declarations no amplían autoridad ni cambian el digest. La identidad de la intersección es conmutativa.

Los paths se evalúan léxicamente con flavor Windows/POSIX explícito. Windows exige drive absoluto y rechaza UNC/device/extended namespace, ADS, traversal, wildcard, nombres DOS reservados y aliases ambiguos. POSIX exige absoluto, sin traversal. La inclusión de árboles se calcula por segmentos, no prefijos de strings. No hay resolución de symlinks/junctions/reparse/TOCTOU ni atestación de objetos; esas condiciones son de S3. Casefold Windows no es una garantía sobre directorios con sensibilidad física especial.

URL/origin sólo representan intención; no constituyen política de red S5. El request de proceso liga acción multilínea exacta, ejecutable y cwd, sin parsear el shell ni limitar su autoridad OS. Variables de entorno tienen comparación Windows case-insensitive o POSIX exacta según el flavor declarado.

## Binding y requestDigest v1

El digest SHA-256 usa UTF-8 y JSON ordenado, compacto y sin conversiones tolerantes. Incorpora:

- versión, tool, argumentos canónicos y acción;
- workspace/cwd, capabilities, resource intent, clases y restricciones;
- sessionId/turnId/operationId/toolCallId/agentId y linaje explícito;
- policyRevision, ceilingId/revision/fingerprint;
- parentGrantId y parentAuthorityFingerprint;
- environmentIntent, networkIntent, effectClassification y lifetime.

Cambiar cualquiera de esos campos invalida un claim anterior. `GrantRequest.from_invocation` toma DTOs Core reales, preserva IDs, verifica coherencia operationId/context, policyRevision y deadline, y copia environment del contexto si no se proporciona otra intención explícita. La Application confiable deberá validar el significado de las capabilities/acción/efecto antes de emitir; el constructor no reemplaza Policy.

El scope del cwd debe quedar dentro del workspace declarado. Esto no exige que todas las capabilities FS apunten a ese workspace: una lectura externa explícita sigue pudiendo representarse. No hay resolución de archivos al calcular el digest.

## GrantIssuer y lifecycle lógico

El host crea `GrantIssuer(ceiling, policy_revision=..., clock=...)` y conserva el objeto, las revisiones y los cancellation ports. No se agregó endpoint de emisión en ApplicationCommand, renderer ni tools del modelo.

| API | Comportamiento |
|---|---|
| `issue` | Emite raíz sólo si request ⊆ ceiling actual, revisiones/fingerprint coinciden, lifetime válido y cancelación no solicitada. |
| `derive` | Emite hijo ligado al grant padre registrado; capabilities y lifetime no amplían padre ni host ceiling. |
| `claim` | Valida digest exacto, ledger/issuer, revisiones, lifetime, cancelación y ancestros; consume one-shot atómicamente. |
| `revoke` | Revocación persistente en memoria; invalida también futuros usos de descendientes. |
| `cancel_session` | Cancelación sticky para ese issuer; atraviesa linaje aun cuando el hijo tenga otra sesión. |
| `replace_ceiling` | Mismo ID y revisión estrictamente creciente; grants anteriores quedan stale. |
| `update_policy_revision` | Revisión estrictamente creciente; no reescribe ni reactiva grants antiguos. |

La clave `(session_id, operation_id)` impide emitir otro grant para revivir la misma operación. Repetir la emisión idéntica antes de consumirla devuelve el mismo objeto sólo si request, parent y cancellation port son los mismos. Una request distinta para esa clave falla. Tras consumir un one-shot, reemitir/claim falla. El lock protege emisión y claim concurrentes.

Core crea subagentes con sesiones propias. Por eso el hijo puede tener session/turn nuevos, pero debe declarar y ligar exactamente parentSession/parentTurn/parentOperation/parentAgent/grant/fingerprint. Sin ese linaje explícito sólo se permite derivación dentro de la misma session/turn. La profundidad está limitada a 32. Cancelación/expiry observadas quedan latched y no se revierten por un port malformado o por rollback posterior del reloj.

`one_shot=False` es una decisión explícita del host para autoridad reutilizable/delegable; no es el default de operaciones. Un parent one-shot no puede delegar un hijo reusable. Una vez emitido válidamente el hijo, consumir normalmente el padre no lo revoca; revoke/cancel/expiry/revision sí invalidan la cadena. El host S2 decidirá cómo instalar estas delegaciones junto al lifecycle existente.

Un claim no es ejecución, cleanup ni rollback. Si una operación ya fue consumida y luego falla o queda UNKNOWN, S1 no vuelve a habilitarla. El ledger es local al issuer y en memoria; S2 debe componer una autoridad host única con deduplicación/lifecycle Core. No hay persistencia/crash recovery ni retención S7 en esta fase.

## Exposure y errores

`CapabilityGrant` no tiene serialización bearer. `json_safe_copy` de Core lo rechaza; copiar/deserializar un dataclass equivalente o conocer un grantId no crea autoridad válida. El issuer sólo acepta el objeto exacto registrado. `correlation_metadata()` retorna IDs y ControlClass, sin request body, digest, scopes o environment. Request/arguments/environment/network están excluidos de repr donde contienen datos sensibles; estas medidas no sustituyen una política general de redacción S7.

Errores: `INVALID_CONTRACT`, `AUTHORITY_EXCEEDED`, `REQUEST_MISMATCH`, `REVISION_MISMATCH`, `PARENT_MISMATCH`, `GRANT_UNKNOWN`, `GRANT_CONSUMED`, `GRANT_REVOKED`, `GRANT_CANCELLED`, `GRANT_EXPIRED`, `GRANT_NOT_YET_VALID`.

## Reanudación en S2

S2 deberá componer estos contratos con PolicyEngine V2, ApprovalGate y ToolRuntime, sin crear autoridad desde renderer/LLM ni alterar los schemas públicos. Deberá sustituir el binding anterior de approval por el requestDigest completo y validar la request vigente inmediatamente antes de claim/ejecución. Esta integración no se realizó en S1.

Las siete `SEC12-OD-*` siguen abiertas. No bloquean el gate de contratos S1; los defaults de aprobación, límites, environment, red, audit, Git y elevación deben resolverse en sus fases correspondientes.
