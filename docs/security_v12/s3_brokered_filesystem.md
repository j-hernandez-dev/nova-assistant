# SECURITY V1.2 — diseño S3: filesystem mediado

Fecha: 2026-10-03. Alcance autorizado: sólo S3. Norma: Core V1 y SECURITY V1.2 §§16 y 29. Estado del gate: PASS tras revisar los 25 casos host-real de `after_symlink_permission/`, incluidos ambos symlinks. Evidencia, límites y cierre vigentes en `s3_resultados.md`; no se inicia S4.

## Fronteras y ruta de ejecución

ToolRuntime conserva la ruta común de CLI, JSONL/Desktop y subagentes. Application calcula intent/policy y coordina aprobación, issuer y FilesystemAuthority. Core declara FilesystemBrokerPort/FilesystemPlanPort, raíz e identidad y errores tipados, sin llamadas OS. Infrastructure implementa el broker Windows y los cinco adapters. AgentRuntimePort no se cambia.

La selección concreta del broker queda detrás del factory interno del adapter Tool existente, frontera de composición de la migración flat-module de Core. Application no importa la implementación Windows. El plan sólo hace consultas de metadatos y abre handles durante preparación: no lee contenido, crea directorios ni escribe antes del claim. El requestDigest incorpora el binding físico inmutable; emisión/derivación y claim exacto preceden al efecto. El broker vuelve a validar el grant registrado, ya reclamado, y su liveness sin consumirlo otra vez.

`read`, `write`, `edit`, `glob` y `grep` no llaman `execute` de sus implementaciones legacy ni la caché legacy. Cada nueva operación abre y valida objetos actuales. Repetir el mismo operationId devuelve el resultado terminal anterior, sin repetir I/O; esto es deduplicación, no nueva autorización. `cached: false` preserva el campo existente. Los nombres, schemas, normalización de aliases, IDs y terminal único de Core se mantienen.

## Raíces, scopes y objetos

- El host instala la raíz workspace y conserva un lease de identidad (volumen + file ID). No se deriva autoridad de un path absoluto, cwd o worktree.
- Cada plan recorre desde la unidad, abre un componente por vez relativo al handle del padre y verifica tipo, nombre real y objeto. La raíz reabierta debe ser el mismo objeto que el lease. Un rename/recreate de la raíz entre operaciones causa `FILESYSTEM_RESOURCE_CHANGED`.
- La ascendencia activa niega share-write/share-delete. El leaf se fija por handle y snapshot de identidad, tamaño, mtime y atributos; los directorios se validan por identidad, no por estabilidad de sus hijos. Estos handles se cierran incluso si aprobación/claim/ejecución falla.
- La lease ociosa permite rename; mantiene vivo el objeto anterior para evitar reuso de su file ID. No convierte la raíz en confinamiento del usuario OS.
- `filesystem.read` y `filesystem.write` siguen siendo capacidades diferentes. `edit` requiere ambas. Las capacidades FS de estas cinco tools son `BROKER_ENFORCED`; el permiso genérico de invocar una tool no sustituye el permiso FS.
- Se anuncia soporte conservador de rutas locales Windows/NTFS, sin directorios case-sensitive. Case aliases normales se aceptan sólo tras abrir el objeto. UNC, dispositivos, ADS, reparse de cualquier tipo, hardlinks múltiples, aliases cortos/tilde, nombres reservados y espacios/puntos finales son DENY/UNSUPPORTED. POSIX, ReFS y otras superficies no tienen adapter autorizado ni fallback en S3.

## Raíz externa one-shot

`ToolRuntime.authorize_external_filesystem` es un hook interno del host, no un schema de tool ni ApplicationCommand accesible al modelo/renderer. Selecciona una raíz real y capacidades finitas para un request exacto. No equivale a consentimiento: la operación externa siempre exige ApprovalGate humano exacto, con binding físico en el digest, incluso si la policy léxica permite el intent.

El ticket se ata a sesión, operationId, toolCallId, tool/args, workspace/cwd/env, revisión y deadline. Se consume al preparar esa operación y no puede reutilizarse por una operación nueva, argumentos diferentes o un hijo. La aprobación y el grant siguen siendo one-shot. Los permisos lógicos añadidos al ceiling no bastan para abrir otra operación externa: sin su ticket, FilesystemAuthority rechaza el path. S3 entrega este mecanismo backend; no incorpora una nueva UI pública de selección de raíz externa (S6 no se implementa).

Los hijos comparten broker/authority y issuer/policy, con grants atenuados. Un worktree fuera del scope original se niega: ser un worktree no amplía el ceiling ni genera un ticket externo. Un hijo no cierra la authority del padre.

## Lectura, enumeración y write atómico

Lectura y glob/grep trabajan con handles del plan. La enumeración recursiva abre cada hijo sin seguir reparse y verifica cada objeto antes de leer. Encontrar una superficie no soportada causa error tipado; no se transforma en una búsqueda vacía aparentando éxito.

Write crea sólo padres necesarios mediante el padre fijado, después del claim y liveness. El temporal exclusivo `.nova-s3-<uuid>.tmp` se crea relativo al padre final, se escribe, se hace flush y se renombra por el handle del temporal dentro de ese mismo directorio. No hay temporal global ni `Path.open`/`os.replace` por pathname en esta ruta. Las comprobaciones de liveness/cancel/deadline se repiten entre chunks de 64 KiB y justo antes del commit.

La apertura relativa usa `NtCreateFile` con RootDirectory y `FILE_OPEN_REPARSE_POINT`. El rename usa `NtSetInformationFile(FileRenameInformation)` con nombre simple y RootDirectory NULL, que refiere al directorio del handle fuente, no al cwd del proceso. Se verificó la semántica y ABI contra fuentes primarias y ejecución real: [NtCreateFile](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile), [FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information) y [GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex).

El guard del leaf previo se libera justo antes del reemplazo. El commit sustituye la **entrada** del directorio fijado, no sigue el destino de un leaf link. S3 impone scope, no una transacción/CAS global contra todos los escritores del host: no promete impedir lost updates o toda sustitución concurrente del leaf. El test determinista de parent-rename impide redirección de la ascendencia; otro test sustituye el leaf por una junction entre guard y commit y verifica que el rename falla sin seguirla ni tocar el sentinel externo.

Ante error/cancelación antes del commit se elimina el temporal por su handle. Si ya se crearon padres, se informa efecto `partial`; no se promete rollback de directorios. Si cleanup no puede confirmarse, se informa `unknown`. Un error con efecto parcial no se presenta como DENIED-before-effect. El resultado mantiene un único terminal y no habilita retry automático de la operación consumida. No se promete durabilidad transaccional ante corte de energía ni cleanup absoluto ante caída del proceso.

Se conservan los formatos de read/edit/write y el comportamiento de newline TextIO de Windows. La verificación posterior de sintaxis analiza el contenido exacto que produjo el broker; el wrapper informa la advertencia sin reabrir un pathname mediante el harness legacy. Las funciones legacy siguen existiendo para consumidores/test low-level, pero no son fallback de ToolRuntime productivo.

## Límite del claim y del gate

S3 protege sólo estas cinco tools mediadas. Un shell o proceso `HOST_UNISOLATED` puede acceder fuera del scope FS usando los permisos normales de la cuenta. Policy, Approval, CapabilityGrant, cwd y worktree no producen aislamiento físico. No se implementan SandboxPort, SandboxBroker, contenedores, VM ni dependencias de seguridad externas. Providers, RAG y servicios host no se convierten en tools mediadas por inferencia.

No hay OPEN DECISION normativa necesaria para implementar S3. SEC12-OD-01 ya fue resuelta por el usuario en S2 (Equilibrado). OD-02–07 se conservan para sus fases; no se deciden aquí. La falta inicial de permiso para crear fixtures symlink fue un bloqueo de evidencia externa, resuelto con la corrida manual del usuario; no una nueva decisión de policy ni autorización para auto-elevation.

Resultado, lista de archivos, pruebas y deuda: `s3_resultados.md`. El gate no se rebaja sustituyendo symlink por junction/mock o marcando esas pruebas como skip.
