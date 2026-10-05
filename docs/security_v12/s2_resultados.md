# SECURITY V1.2 — cierre S2

Fecha: 2026-10-03. Estado: **PASS del gate S2**, SECURITY V1.2 §29. Se implementó únicamente PolicyEngine V2 + approvals. S3 no se inició. El PASS corresponde a controles Application y evidencia unit/contract/mock/integration; no certifica aislamiento ni el producto SECURITY completo.

## Baseline y preservación

- Repo: `C:\Users\joseh\Downloads\nova-local-cli\nova-assistant`.
- HEAD/main se conserva: `158b60effa484cd34a58b991f3ee4ca3f808d924`.
- Se leyeron continuidad, Core V1, SECURITY V1.2 y cierres/manifests S0/S1. Los 36 pins del manifest S1 coincidieron con el baseline antes de modificar código.
- Working tree inicial: 107 entradas expandidas preexistentes, incluidos S0/S1. No era un checkout vacío; se conservó el trabajo previo.
- Baseline ejecutado antes de modificaciones de producto: 181 S1 + 326 regresiones pertinentes PASS, 10 subtests PASS, 1 smoke Ollama opt-in skipped y 2 tests nativos deselected.
- Preservación de 354 archivos disponibles preexistentes: 331 byte-identical, 23 modificados intencionalmente dentro de S2, cero faltantes. Las eliminaciones previas `README.easy-ja.md`, `README.ja.md`, `hello.py` no se tocaron. Las arquitecturas, continuidad externa y documentación/evidencia histórica S0/S1 no se reescribieron.
- El runner S2 se creó para tomar el snapshot; está excluido del conteo de archivos preexistentes. Su creación y las rutas nuevas de evidencia tampoco inflan las 107 entradas iniciales.
- No reset/clean/restore destructivo, staging, commit ni push. No se copió, migró ni reutilizó código SECURITY deprecated.

Procedencia: `s2_evidence/before/snapshot.json`, `s2_evidence/baseline/`, `s2_evidence/preservation_check.json` y `s2_manifest.json`. El baseline es Nova Core V1 + los contratos/issuer S1 del árbol actual, no un branch SECURITY histórico.

## Implementación

PolicyEngine V2 calcula effect/resource intent y decide ALLOW/REQUIRE_APPROVAL/DENY dentro del ceiling host y parent. ToolRuntime valida cada tool, solicita la aprobación exacta cuando corresponde, revalida, emite/deriva/reclama el grant S1 y sólo entonces despacha. Se comparte policy/issuer con subagentes sin heredar consentimiento humano. ApprovalGate es inmutable, cancelable, con deadline, revision y protección stale/replay.

CLI exige TTY humana verificada y niega en headless. `--yes` conserva sintaxis pública pero no autoriza requests sensibles ni DENY. Desktop exige correlación de request y diálogo nativo en main; valida sender/frame y autentica el command privado hacia Application. El renderer y JSONL unsigned no crean actores ni grants. La clave de ese canal no se hereda a las tools.

AgentRuntime conserva dependencias Core; Application coordina, ToolRuntime sigue siendo ruta común, y no se duplicó el backend CLI/Desktop. Los adapters existentes siguen realizando los efectos. Los procesos sólo se clasifican `HOST_UNISOLATED`; los scopes FS son admisión lógica previa, no broker S3. Se preservaron nombres/schemas públicos y lifecycle, salvo el endurecimiento de approvals exigido por SECURITY V1.2.

Decisiones y límites detallados: `s2_policy_y_approvals.md`.

## Archivos modificados por S2

Los nombres de la tabla son relativos al repo indicado arriba; no incluyen archivos sucios previos que S2 no tocó.

| Archivo | Cambio acotado |
|---|---|
| `local_cli/core/security.py` | Scopes finitos PROCESS_DOMAIN/URL_SCHEME y su algebra; se conserva HOST_UNISOLATED. |
| `local_cli/application/grants.py` | Sólo docstring de composición S2; issuer S1 existente. |
| `local_cli/application/tool_runtime.py` | Pipeline policy → aprobación → grant/claim → adapter, bindings y deduplicación. |
| `local_cli/application/interactions.py` | ApprovalRequest inmutable, actor confiable, digest de grant y revalidación/one-shot. |
| `local_cli/application/commands.py` | Actor opaco interno, excluido de DTO/serialización. |
| `local_cli/application/session.py` | Instalación de ceiling, actors, revisions y delegación StartSubAgent. |
| `local_cli/sub_agent.py` | ToolRuntime hijo con issuer/policy/parent compartidos. |
| `local_cli/tools/agent_tool.py` | Contexto de delegación interno; schema público intacto. |
| `local_cli/interfaces/cli_application.py` | TTY verificada, warning y headless deny. |
| `local_cli/interfaces/jsonl_application.py` | Proof privada y rechazo de aprobaciones unsigned. |
| `local_cli/bootstrap_server.py` | Retira credencial host del env al componer el adapter. |
| `local_cli/security.py` | Excluye únicamente NOVA_APPROVAL_HOST_KEY de herencia. |
| `local_cli/cli.py` | Ayuda de --yes conforme al contrato S2. |
| `desktop/electron/application_client.ts` | Firma privada de ResolveApproval y canonical DTO. |
| `desktop/electron/main.ts` | Sender/frame, native confirmation y clave privada por launch. |
| `desktop/vite.config.ts` | Inclusión del helper CJS en el bundle main. |
| `tests/security_v12/test_s0_frontends.py` | Caracterizaciones anteriores ajustadas al cambio explícito S2; evidencia histórica intacta. |
| `tests/test_nova_core_phase6_runtime.py` | Sesión estable, typed failures y nuevos defaults de aprobación. |
| `tests/test_nova_core_phase7_interactions.py` | Fixture legacy explícito y comando sensible no auto-elevation. |
| `tests/test_nova_core_phase7_session.py` | Actor host de prueba y nuevo comando sensible. |
| `tests/test_nova_core_phase8_providers.py` | Actor/comando de aprobación en regresión provider. |
| `tests/test_nova_core_phase11_adapter.py` | Respuestas host firmadas, unsigned/replay negativos. |
| `tests/test_nova_core_phase12_client.py` | Fixture sensible compatible con prohibición de auto-elevation. |

Total: 23 archivos preexistentes modificados. Los fixtures low-level legacy que usan `require_actor=False` no son composición productiva y no cambian los tests negativos del gate seguro.

## Archivos creados

| Archivo | Contenido |
|---|---|
| `local_cli/application/policy.py` | PolicyEngineV2, intent, reglas, validación de schemas existentes y ceiling host. |
| `local_cli/interfaces/approval_proof.py` | Proof HMAC-SHA256 del canal privado Desktop. |
| `desktop/electron/approval_host.cjs` | Correlación/dialog/proof/frame del host main. |
| `desktop/electron/approval_host.d.cts` | Declaraciones TS del helper. |
| `desktop/tests/approval_host.test.cjs` | 10 tests helper/diálogo mock. |
| `tests/security_v12/test_s2_policy.py` | 32 casos unit/contract de reglas, intent y scopes. |
| `tests/security_v12/test_s2_runtime.py` | 17 casos runtime/approvals/delegación, incluidos AgentTool y SubAgent reales con executor mock. |
| `tests/security_v12/test_s2_approvals.py` | 8 casos Application/CLI/JSONL/proof y frontera renderer. |
| `tests/security_v12/run_s2.py` | Harness aislado, corrida fresh, logs/JUnit y Node opcional. |
| `docs/security_v12/s2_policy_y_approvals.md` | ADR SEC12-OD-01, diseño y límites. |
| `docs/security_v12/s2_resultados.md` | Este cierre. |
| `docs/security_v12/s2_manifest.json` | Baseline, hashes y alcance final. |
| `docs/security_v12/s2_evidence/.gitignore` | Exclusión de estados instrumentales temporales privados. |
| `docs/security_v12/s2_evidence/` | Snapshot, baseline, bloques, final, parse, preservación e incidencias; logs/JUnit no reescritos. |

## Gate S2

| Criterio de §29 | Estado | Evidencia y límite |
|---|---|---|
| Ninguna tool agentic evita ToolRuntime/Policy | PASS | Wrappers main/hijo, arquitectura Core, grant claim antes de las cinco tools FS y web_fetch; composición AgentTool/SubAgent. Servicios administrativos siguen siendo host, no bypass agentic. |
| Approval requerida exacta y one-shot | PASS | Digest del grant, immutable snapshot, IDs/cwd/revisions/deadline; replay no repite efecto. |
| Approval no crea autoridad adicional | PASS | Emisión/derivación S1 comprueban ceiling y parent; scopes externos denegados y hijo atenuado. |
| ALLOW/REQUIRE_APPROVAL/DENY y shell destructivo/desconocido/high-risk | PASS | SEC12-OD-01 Equilibrado; ShellPolicy heurística adicional; --yes no reemplaza al humano. |
| FS read/write y web_fetch | PASS de intención lógica S2 | Distinción read/write, URL exacta y claim previo con adapters mock. No claim broker/redirect/private-network de S3/S5. |
| Stale/cancel/deadline/digest/cwd mismatch | PASS | Cambios args/cwd/env/policy/ceiling mientras se espera, cancel/expiry y respuesta mismatch antes de launch. |
| Spoof renderer y host confirmation Desktop | PASS unit/mock/integration | Sender/frame inspeccionados, helper main con diálogo mock y proof exacta Python/Node. GUI/packaging nativos no verificados. |
| TTY CLI/headless/--yes | PASS unit/mock/integration | TTY mock positiva y headless real StringIO sin lectura; parser conserva bandera y ayuda correcta. |
| Subagente | PASS | Shared issuer, derived grant, parent revocation, no aprobación heredada; AgentTool/SubAgent de producto con provider/executor mock. |
| Nombres/schemas/lifecycle y fronteras Core | PASS | 181 S1, regresión Core/frontends, snapshot schemas S0 y tests de arquitectura. |

Criterios normativos S2 incumplidos: ninguno en el alcance verificado. No se amplía este PASS a S3, process isolation, GUI, packaging ni NOVA_SECURITY_V1_2_READY.

## Pruebas ejecutadas

| Ejecución | Resultado | Tipo |
|---|---|---|
| Baseline S1/Core previo | 507 passed + 10 subtests; 1 skipped, 2 deselected | Unit/contract/in-process integration/regression/mock smoke. |
| Bloque policy + contratos S1 | 213 passed | Unit/contract. |
| Bloque runtime corregido + arquitectura | 21 passed | Unit/mock/in-process integration. |
| Bloque adapters corregido | 8 passed | Unit/mock/in-process integration. |
| Recheck de regresiones afectadas | 106 passed; 2 deselected | Contract/integration/frontends. |
| Final completo: S2 | **57 passed** | 32 policy + 17 runtime + 8 adapters. |
| Final completo: S1/Core/schema público | **508 passed + 10 subtests**; 1 skipped, 2 deselected | 181 S1 + 326 regresiones pertinentes + 1 snapshot de tools. |
| Final completo: helper Desktop | **10 passed** | Node real, crypto real; cliente y diálogo nativo mock. |
| Final completo: main/client TS | 2 comandos exit 0 | Sólo sintaxis con Node; no tsc/typecheck/bundle. |
| AST/compile y diff whitespace | PASS | Offline, sin bytecode; git diff --check. |
| Host-real de seguridad | NO EJECUTADO, no requerido por gate S2 | Sin comandos destructivos, GUI nativa, inferencia o experimentos de enforcement OS. |

Resultado final único: **575 tests passed + 10 subtests**, 1 skipped y 2 deselected. No se suman las ejecuciones repetidas/incrementales. El skip corresponde al smoke Ollama opt-in; los dos deselected son native_shell/windows_cancellation. Algunas regresiones Core crean hijos Python de fixtures, que son integración de lifecycle, no evidencia de aislamiento de shell.

La corrida final canónica es `s2_evidence/final_complete/run.json` con status PASS y exit 0 de sus cinco grupos. Sus comandos exactos, logs y JUnit se conservan. Reproducción en este entorno:

```powershell
& 'C:\Users\joseh\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B tests/security_v12/run_s2.py --output docs/security_v12/s2_evidence/<directorio_nuevo> --node
```

El runner exige salida nueva y usa estado temporal privado; no activa Ollama/Electron opt-in ni instala dependencias. Python/pytest presentes se usan tal cual. No se leyó contenido privado ni se lanzó red externa para estas pruebas.

### Incidencias y cambios de caracterización

Se conservan intentos fallidos/incompletos en `s2_evidence/development_incidents.json` y sus logs originales. Se corrigieron fixtures (snapshot inmutable, confirm callback y EventBufferConfig), binding de sesión y expectativas de seguridad deliberadamente cambiadas por V1.2: sudo ahora DENY, --yes no aprueba, actor/proof obligatorios, deadline CANCELLED. El comando de prueba sensible pasó a git reset --hard para seguir comprobando una aprobación en vez de auto-elevation; nunca se ejecutó realmente.

Una corrida frontend obtuvo 78 Python y 10 Node PASS pero el runner quedó incompleto al imprimir checkmarks con cp1252. Se corrigió únicamente UTF-8 del harness y se volvió a ejecutar el criterio íntegro, sin declarar aquel intento PASS global. Avisos de localización Python/pyreadline al shutdown se registran como instrumentales; las corridas finales terminan exit 0. Los logs fallidos no fueron editados para aparentar éxito.

Regresiones detectadas tras la verificación final: ninguna en las suites ejecutadas. No se declara cobertura de toda la suite histórica ni de plataformas/GUI no probadas.

## Deuda y OPEN DECISIONS

- SEC12-OD-01: RESUELTA por el usuario, Equilibrado; implementada y registrada en el ADR.
- Bloqueos/decisiones abiertas de S2: ninguno.
- SEC12-OD-02–07 permanecen pendientes donde corresponda a fases futuras; no se escogieron defaults arbitrarios. La prohibición normal de auto-elevation de V1.2 se respeta; no se habilitó una feature administrativa OD-07.
- No hay broker FS, protección symlink/junction/TOCTOU ni autorización de raíz externa mediada: S3.
- No se productizaron output/env/timeout/árbol de procesos del launcher ni un firewall de shell: S4/S6 y límites normativos.
- No se resolvió política privada/redirects de web_fetch: S5/OD-04. HTTP/HTTPS aquí son sólo el dominio de requests host.
- No se implementó audit persistente S7 ni gate E2E S8.
- Typecheck/build Electron y diálogo en GUI real quedan sin verificar por ausencia de dependencias locales; sin instalación de paquetes. Los tests de host-confirmation son explícitamente mock/in-process.

Siguiente fase lógica: **S3 — Brokered Filesystem**, sin implementar. Todo proceso shell sigue siendo HOST_UNISOLATED y conserva permisos normales de cuenta incluso cuando exista S3.
