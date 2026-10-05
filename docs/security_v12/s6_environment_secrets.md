# S6 — Environment / Secrets: diseño y límites

Referencias normativas: Core V1 y SECURITY V1.2, secciones Environment/Secrets
y gate S6. Implementación directamente contra el Core/S0–S5 actual, sin código
del SECURITY deprecated.

## Ruta de ejecución

Infrastructure `EnvironmentBuilder` implementa el puerto Core. Construye una
base explícita sin leer ambiente al ejecutar ni mutar el source. La captura
legacy `get_sanitized_env` delega en esa base para impedir herencia accidental
también en los consumidores existentes. La selección adicional es separada.

Application `EnvironmentService` resuelve únicamente nombres seleccionados por
el host, valida hooks/credenciales protegidas, toma un snapshot y declara permisos
read/pass exactos. ToolRuntime mantiene la ruta común: policy, approval vigente,
grant/claim, revalidación y launcher. El digest incluye valores exactos privados,
argv, comando, cwd, límites, correlación, revisions y lifetime; mostrar valores
redactados no altera ese binding.

Cada selección se liga a una operación y se elimina en todos sus terminales.
Cambiar/reemplazarla mientras la operación está activa se rechaza. Replay de
una operación terminada devuelve el mismo resultado sin lanzar otra vez;
seleccionar otra vez para ese ID se rechaza. Cambios de args/cwd/ambiente,
policy/ceiling, cancelación o expiry invalidan la aprobación antes del launch.
Los hijos no amplían su parent grant ni reciben automáticamente valores extras.

No cambia ningún nombre/schema público de tools. AgentRuntime no recibe una
dependencia nueva de Infrastructure/Application: continúa usando contratos y
puertos Core. Provider binding/redacción y coordinación permanecen en Application;
los adapters y launcher siguen en Infrastructure. CLI/Desktop comparten backend.

## Redacción antes de publicación/persistencia

`SecretRedactor` mantiene valores conocidos en memoria: environment con nombres
sensibles, credenciales explícitas de los adapters provider, valores seleccionados
por el host y componentes password conocidos de URLs de proxy/database. Registra
formas exactas, JSON escapado y URL-encoded; no inspecciona archivos secretos.

Se integra antes de publicar ToolResult/errores/metadata, eventos y journal,
snapshots/transcript/working prompts, SessionLogger/LegacyAuditLog y repositorios
de conversación/snapshots. La credencial necesaria para autenticar el provider
permanece en su adapter; el prompt, los resultados y los procesos tool no la reciben.
Los snapshots/fresh providers comparten el registro, no exponen la credencial.

Los streams retienen un posible prefijo entre chunks y lo redactan antes de
timers, batches y consumidores. Al finalizar un prefijo ambiguo puede sustituirse
conservadoramente por el marcador. Los outputs completos no se tratan como
truncados. Los bordes realmente truncados se redactan antes de los marcadores de
presentación. La expansión del marcador no aumenta los bounds S4 de stdout,
stderr o texto publicado; se conserva `truncated` si hay recorte adicional.
El marcador es idempotente, incluso con valores conocidos cortos.

Campos de schema/correlación/lifecycle generados por Core/Application se preservan;
la redacción no cambia IDs, status/effectState, números o requestDigest de aprobación.
La memoria interna necesaria para verificar el request nunca se sustituye por la
vista redactada. Una excepción del selector es un error acotado sin dispatch.

No se reescriben los archivos de transcript/evidencia históricos. Leer/restaurar
y volver a publicar o guardar una conversación usa la vista redactada actual;
no es una migración ni un borrado retroactivo.

## Alcance real

Todo proceso sigue siendo **HOST_UNISOLATED**. PATH, perfil/configuración y locale
compatibles no aíslan al proceso: puede leer archivos del usuario, usar credenciales
de toolchains en disco o acceder a la red con sus permisos OS. Root puede transmitir
el pass a hijos OS; la fixture nativa lo demuestra. Policy/approval/capabilities
expresan autoridad lógica, no aislamiento, firewall ni cuotas preventivas.

No se garantiza descubrir secretos desconocidos, transformaciones arbitrarias,
fragmentos deliberadamente ofuscados, memoria o archivos externos. La redacción
se refiere a material conocido por Nova en las superficies mediadas. Permanecen
intactos los claims S3 de filesystem y la policy PUBLIC_ONLY de web_fetch S5.

Audit sólo conserva el mínimo/live existente de S4/S5 con redacción. No se
implementan durabilidad, retención, nuevas bases de datos, S7 ni una UI general
de secretos. No hay sandbox, virtualización o dependencia externa de seguridad.
