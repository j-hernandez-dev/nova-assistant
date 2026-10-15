# SECURITY V1.2 — S2: policy, aprobación y autoridad lógica

Fecha: 2026-10-03. Implementación nueva contra Nova Core V1 y SECURITY V1.2 §§11–15 y §29. No se reutilizó código SECURITY deprecated. Este documento registra las decisiones de implementación; no modifica los documentos normativos ni certifica S3–S8.

## ADR SEC12-OD-01: defaults de shell

Estado: RESUELTA por el usuario en esta conversación. Respuesta explícita: «Equilibrado (recomendado)». La elección se implementa únicamente en S2.

| Decisión | Categoría implementada |
|---|---|
| ALLOW | Consultas simples reconocidas, con sintaxis deliberadamente limitada: `pwd`/`Get-Location`, `echo`/`Write-Output` literal, `Get-ChildItem` sobre el cwd y `ls` con variantes limitadas. |
| REQUIRE_APPROVAL | Mutaciones, instalación/publicación, operaciones de red, scripts, comandos desconocidos y comandos ambiguos; también los casos CONFIRM de ShellPolicy. |
| DENY | Bloqueos existentes de ShellPolicy, elevación automática reconocida (`sudo`, `doas`, `runas`, `-Verb RunAs`), requests inválidas o fuera del ceiling y autoridad de parent. |

ALLOW no admite encadenamiento, redirecciones, interpolación o ejecución de scripts. La lista corta aumenta las confirmaciones, incluso para comandos cotidianos no reconocidos. Fue preferida por el usuario a confirmar absolutamente todo o conservar el auto-approve previo. No se pretende interpretar perfectamente PowerShell ni demostrar el efecto de un comando: perfiles, aliases, hooks y programas conservan los permisos normales de la cuenta. ShellPolicy es una heurística adicional, nunca aislamiento.

`--yes`/`-y` sigue siendo una bandera pública reconocida. No proporciona actor humano, no amplía el ceiling, no cambia DENY ni omite una aprobación requerida. Su ayuda se corrigió para expresar este contrato.

## Composición y ruta común

Application instala un ceiling host al iniciar la sesión, antes de evaluar argumentos del modelo. Incluye únicamente los nombres registrados y las superficies que el host habilitó: invocación de tools de esa sesión, read/write en el workspace lógico, requests de proceso con ejecutable host y cwd dentro del workspace, URLs HTTP/HTTPS y estado/input de sesión cuando corresponde. No hay un grant universal fabricado por el LLM o renderer.

ToolRuntime ejecuta, en orden:

1. Normalización existente y validación contra el schema público existente.
2. Cálculo de effect/resource intent y PolicyEngine V2.
3. ApprovalGate, sólo para REQUIRE_APPROVAL.
4. Revalidación de la request actual, emisión/derivación y claim de GrantIssuer S1.
5. Dispatcher existente y resultado/eventos Core.

Los wrappers que recibe AgentRuntime, el AgentTool y los subagentes siguen esta ruta. AgentRuntime no ganó imports de PolicyEngine, GrantIssuer ni infraestructura. CLI y Desktop siguen consumiendo el mismo AgentSessionCoordinator. Los nombres, descripciones y schemas de tools no cambiaron; el snapshot público S0 sigue pasando.

Los servicios administrativos host —gestión de modelos, updater, RAG y similares— no se convirtieron en tools ni en mecanismos de aprobación. Sus rutas no amplían la autoridad de una tool agentic.

## Scopes y clases de control

S2 añade dos variantes finitas a ResourceScope sin renombrar los contratos S1:

- `PROCESS_DOMAIN`: dominio host de requests, ejecutable fijo y árbol de cwd. Contiene únicamente requests exactas o dominios más estrechos compatibles. El grant operacional fija comando, ejecutable y cwd; su clase siempre es `HOST_UNISOLATED`.
- `URL_SCHEME`: dominio HTTP o HTTPS habilitado por el host. Un grant `web_fetch` concreta la URL solicitada. No controla redirects, resolución DNS ni destinos privados: esas reglas/clientes son S5.

Las capabilities FS se diferencian por read/write; `edit` requiere ambas. En S2 la comprobación de scope es admisión lógica/lexical de la request antes del adapter existente. No se implementó FilesystemAuthority, broker, handle/object binding, reparse ni protección TOCTOU. `APPLICATION_ENFORCED` describe la ruta Application, no un claim filesystem brokered de S3.

Shell no tiene límites físicos de archivo, red o procesos derivados por estos scopes. Puede acceder a recursos externos con la autoridad normal del usuario. No se introdujeron sandbox, SandboxPort, SandboxBroker, dependencias de aislamiento ni terminología heredada G-T/G-H o TCB.

## Approval exacta y grant

La ApprovalRequest contiene un snapshot profundamente inmutable. Su digest es exactamente el del GrantRequest S1 e incorpora tool/args, executable/action, recursos, IDs Core, workspace/cwd, revisions, parent authority, environment/network intent, clasificación y lifetime. Los datos se revalidan durante la espera, al resolver y antes del claim.

La operación se deniega/cancela antes del efecto cuando cambian args/cwd/env, policy/ceiling, digest o bindings, o cuando vence el deadline o llega cancelación. La revision de policy es monotónica. La caducidad lógica queda limitada por el deadline de contexto/aprobación y el parent; sin uno más corto, el host usa cinco minutos. No es una quota ni un timeout preventivo OS de S4.

Cada `(sessionId, operationId)` puede abrir una sola aprobación. Replay idéntico sólo devuelve el resultado/ack previo; no ejecuta otra vez. Los grants operacionales son one-shot. Una aprobación nunca agrega capabilities: la request aprobada todavía debe pasar el ceiling y, si aplica, el parent. Revocar/cancelar/expirar autoridad impide claims posteriores; no se afirma que mate procesos ya iniciados.

Application registra actores de aprobación como objetos opacos internos. Un campo JSON, string de actor o ID inventado no puede registrarlos ni resolver una aprobación. El valor `approval_actor` de ApplicationCommand no se serializa. El modo `require_actor=False` aparece únicamente en fixtures explícitos de contratos legacy; la composición productiva utiliza el gate seguro.

## CLI y Desktop

CLI verifica stdin y stdout TTY, vuelve a comprobar el actor al resolver positivamente y muestra command/cwd y el aviso de permisos normales. En headless niega sin leer `yes` redirigido; `--yes` tampoco sustituye a la persona. Las pruebas TTY usan un verificador mock y no se presentan como una sesión humana nativa.

Electron main valida identidad de WebContents y frame principal, correlaciona el snapshot pendiente del backend y requiere un diálogo nativo para una decisión positiva. El diálogo tiene Cancelar como default/cancel; muestra cwd, comando y el aviso de permisos de cuenta. Después del diálogo se revalidan sesión, snapshot y deadline. El renderer no puede resolver por el canal JSONL legacy: `confirm_response` y ResolveApproval crudo se rechazan en esa ruta.

Cada launch del backend usa una clave privada de 32 bytes generada por Electron main. Main firma el command canónico ResolveApproval con HMAC-SHA256; el adapter JSONL verifica la prueba antes de adjuntar el actor interno. No se entrega clave ni grant al renderer. La prueba no es un bearer grant ni una nueva autoridad. El bootstrap retira la clave del entorno antes de construir tools; además se excluye de la herencia de hijos mediante la denylist existente. Esta exclusión acotada es necesaria para S2; no implementa el environment baseline S6.

Se mantienen los DTOs/versiones y eventos Core. El envelope privado JSONL agrega `hostApprovalProof` únicamente para esta decisión autenticada. Clientes headless o emisores de confirmación unsigned reciben error tipado; es un cambio intencional del contrato SECURITY V1.2, no una ruta alternativa de autorización.

## Subagentes

El host/AgentTool delega un grant parent reusable explícito, dentro del ceiling instalado. Cada tool del hijo deriva y reclama su propio grant más estrecho, ligado al parent y al nuevo contexto. La reutilización del parent permite varias operaciones del hijo, no replay del AgentTool: ToolRuntime deduplica la operación original.

La aprobación del padre no aprueba comandos sensibles del hijo. Los subagentes silenciosos no tienen un adaptador humano equivalente y sus requests REQUIRE_APPROVAL se deniegan. Los worktrees no agregan autoridad: un cwd fuera del dominio instalado falla cerrado. No se implementó gestión brokered de worktrees S3.

## Límites de verificación

Las suites verifican policy, contratos S1, gate, composición real de Application/AgentTool/SubAgent y adapters con proveedores, executors y diálogo mock. El helper Desktop corre realmente en Node y se verifica interoperabilidad de proof con Python. Los dos archivos TS pasan un chequeo de sintaxis, no un typecheck/build completo.

No hay node_modules/TypeScript/Electron instalados en este checkout. No se descargaron dependencias: packaging y GUI nativa quedan sin verificar. S2 no requiere experimentos de enforcement host-real. FS brokered, launcher safety, network mediation, environment baseline y audit persistente quedan para S3–S7. El cierre S2 no significa NOVA_SECURITY_V1_2_READY.
