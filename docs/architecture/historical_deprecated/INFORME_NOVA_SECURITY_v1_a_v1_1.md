# Informe de continuidad: Nova SECURITY V1 → propuesta V1.1

Fecha de corte: **2026-10-02**. Revisión de repositorio, documentación y evidencia existente. No es una enmienda normativa, una implementación ni una autorización experimental.

**Conclusión arquitectónica:** la evidencia favorece conservar S1–S3, hacer una revisión limitada de compatibilidad y completar/redefinir el contrato de S4 para `SANDBOXED_STANDARD`. No hay una razón técnica demostrada para rehacer S1, S2 o S3 desde cero, ni para reescribir Nova Core. Sí hay integración de proceso pendiente: actualmente la shell productiva no utiliza `SandboxPort` y no existe un `SandboxieAdapter` productivo. Reducir el gate de certificación no crea esa integración.

Los perfiles propuestos conservan Policy/Approval/Grant y la arquitectura por puertos. `SANDBOXED_STANDARD` ofrecería reducción práctica de riesgo, con backend activo y configuración conocida; `HARDENED_EXPERIMENTAL` conservaría la investigación de garantías rigurosas. Esto no permite etiquetar la ejecución host actual como Standard, cambiar los resultados históricos ni convertir una observación `UNKNOWN` en garantía.

## 1. Alcance, fuentes y criterio de lectura

Se inspeccionaron código productivo, composición CLI/server/Desktop, tests S0–S4, documentos canónicos, resultados de fases y artefactos del laboratorio. Se verificaron hashes y se ejecutó una selección de tests offline. **No se ejecutaron Sandboxie, un preflight, F02, controles host adicionales, ARM/EXEC/GO ni operaciones focales.** Tampoco se modificaron código, arquitectura canónica, configuración, ACL, fixtures, evidencias o GUI. El único artefacto nuevo de esta entrega es este informe.

Se encontraron tres ubicaciones distintas:

| Ubicación | Función y autoridad |
|---|---|
| [Repositorio actual](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main) | Checkout productivo real, Python y Desktop; fuente de verdad de implementación. |
| [Core V1](C:/Users/joseh/Downloads/nova-local-cli/NOVA_CORE_ARQUITECTURA_V1.md:1) y [SECURITY V1](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md:1) | Arquitectura vigente. SECURITY declara expresamente que es una especificación objetivo, no una certificación. |
| [Laboratorio F01/F02](C:/NovaS4SandboxieLab/free_20260930_f01) | Código diagnóstico, binarios, manifests, muestras y resultados independientes del runtime productivo. |

La ruta indicada por el contexto antiguo, `C:\Users\joseh\Downloads\nova-open-interpreter`, ya no existe en este equipo. No se auditó una copia supuesta de ella. La carpeta separada `C:\Users\joseh\Downloads\nova-assistant` no se ha tomado como implementación de este Core; sus posibles funciones no demuestran integración en el repositorio aquí identificado.

Este informe distingue:

| Etiqueta de componente | Significado |
|---|---|
| `IMPLEMENTED` | Código verificable y conectado a una ruta de producto declarada; no equivale a certificación global. |
| `PARTIALLY_IMPLEMENTED` | Código real, pero alcance, integración o requisitos incompletos. |
| `SPEC_ONLY` | Contrato/documento objetivo sin implementación concreta suficiente. |
| `EXPERIMENTAL` | Prototipo o instrumento de laboratorio, incluso si tiene binario y tests. |
| `HISTORICAL` | Evidencia de una ejecución/versión pasada, preservada con su clasificación original o revisión explícita ya aprobada. |
| `NOT_IMPLEMENTED` | Ausente en las rutas productivas inspeccionadas. |
| `UNKNOWN` | No puede determinarse con la evidencia disponible. |

Los estados de fase se usan separadamente: `NOT_STARTED`, `PARTIAL`, `IMPLEMENTED_NOT_VALIDATED`, `VALIDATED_FOR_CURRENT_CONTRACT` y `EXPERIMENTAL_ONLY`. Validar un contrato S1 no valida su enforcement físico; validar las cinco tools S3 no valida una shell arbitraria.

La nueva dirección de producto del usuario es el contexto para proponer V1.1. **La arquitectura V1 actual sigue sin editarse.** La alternativa B/B2 sigue siendo una decisión provisional histórica; su aceptación anterior no equivale a certificación G-T/G-H ni a adopción de Hyper-V.

## 2. Baseline exacto y estado de verificación

### 2.1 Checkout y versiones

| Elemento | Observación |
|---|---|
| HEAD | `158b60effa484cd34a58b991f3ee4ca3f808d924`. Commit: `feat(core): complete Nova Core V1 refactor`, 2026-09-29. |
| Commit anterior | `de1244b`, `chore: freeze Nova Core baseline before V1 refactor`, 2026-09-28. |
| Tag | `nova-core-v1-stable` existe. El nombre del tag no sustituye el alcance real de la validación. |
| Versión de producto | `0.12.6` en [pyproject](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/pyproject.toml:7), [paquete Python](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/__init__.py:8) y [Desktop](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/package.json:3). |
| Python usado para esta auditoría | `3.14.6`, x64, MSC 1944; ejecutable `C:\Users\joseh\AppData\Local\Python\pythoncore-3.14-64\python.exe`. |
| Plataforma observada | `Windows-11-10.0.26200-SP0`, AMD64. No se ensayaron Linux/macOS. |
| Estado antes de crear este informe | **24 archivos tracked modificados y 49 archivos untracked**, usando `git status --porcelain=v1 --untracked-files=all`. No hay commit SECURITY separado. |
| Inventario de checkout | 333 archivos tracked/untracked regulares verificados por hash antes de la entrega; excluye artefactos ignorados. |
| Comparación con S0 | Los 145 archivos productivos fijados por [manifest S0](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s0_manifest.json:1) existen; 17 cambiaron respecto de sus hashes S0. Se añadieron componentes y tests fuera de esos 145. |

**El baseline previo a ETAPA 2 — SECURITY sí está identificado:** HEAD/Core y el manifest S0, con sus pins exactos. El delta actual contra ese baseline se inventaría en §3 y §15. Lo que no existe es un checkpoint Git distinto “inmediatamente anterior a S2” dentro de SECURITY: S1/S2/S3 fueron entregas sucesivas sin commits intermedios. La partición exacta por bytes entre esas subfases es `UNKNOWN`; no se atribuye todo el diff contra HEAD exclusivamente a S2. La responsabilidad y cronología por componente se reconstruyen mediante código e informes.

El [informe Core fase 14](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_core_fase_14_resultados.md:7) declara implementación local validada en Windows y gate global pendiente por no ejecutar la matriz nativa Linux/macOS. **No declara NOVA CORE V1 STABLE global**, pese al tag. SECURITY no ha completado S4–S8 ni declara SECURITY V1 STABLE.

### 2.2 Tests: histórico frente a comprobación de hoy

| Validación | Evidencia y alcance |
|---|---|
| Core fase 14, histórica | Informe registra regresión completa y E2E Windows, incluidos Electron y Ollama activados en aquella fase; no implica que se hayan repetido ahora ni que otras plataformas estén certificadas. |
| S0, histórica | Regresión 477 passed, 3 skipped, 5 xfailed y 43 subtests; caracterización 40 passed/5 xfailed; smoke 12 passed, 1 skipped, 2 xfailed. [Resultados](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s0_resultados.md:35). |
| S1, histórica | Contratos 72 passed; regresión 572 passed, 3 skipped, 5 xfailed y 53 subtests. Son contratos y mocks de broker, no una sandbox OS. [Resultados](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s1_resultados.md:52). |
| S2, histórica | Regresión 616 passed, 3 skipped, 5 xfailed y 53 subtests; pruebas de host/IPC/cliente y compilación Desktop documentadas. Packaging Electron falló por privilegio de symlink; no se certificó el diálogo humano mediante ese build. [Resultados](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s2_resultados.md:1). |
| S3, histórica | Composición 13 passed; SECURITY 198 passed, 1 skipped, 5 xfailed; suite completa 2917 passed, 12 skipped, 5 xfailed y 53 subtests. Symlink de archivo real quedó skipped; junction/reparse, hardlink y carreras seleccionadas sí están documentados. [Resultados](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s3_resultados.md:29). |
| **Esta auditoría, Python** | **137 passed y 10 subtests passed**, 26.50 s. Contratos/grants/attestation simulada S1, binding aprobación↔grant/CLI/policy/IPC source S2, contratos/límites Core. Launcher existente aisló HOME/TEMP de tests y confirmó retirada de recursos temporales. |
| **Esta auditoría, Node** | **6/6 tests PASS** en `test_s2_host_approval.mjs` y `test_s2_ipc_origin.mjs`. Son tests unitarios del host/origen, sin abrir Electron. Warning MODULE_TYPELESS_PACKAGE_JSON, sin fallo funcional; no se editó package.json. |
| **Esta auditoría, estática** | 105 módulos Python productivos parseados por AST; cero imports concretos Application/Infrastructure/Interfaces desde los módulos de Core examinados. |
| Suite completa actual | **No ejecutada en esta auditoría**. El último resultado completo es histórico S3; no se presenta como una ejecución actual. |
| Laboratorio S4/F02 | Se leyeron resultados archivados. No se volvieron a ejecutar sus suites que crean pipes nativos ni sus ensayos host-real. |

La selección Python fue: `test_s1_authority_contracts.py`, `test_s1_grants.py`, `test_s1_sandbox_contract.py`, `test_s2_approval_grant_binding.py`, `test_s2_cli_approval.py`, `test_s2_policy_engine.py`, `test_s2_ipc_source.py`, `test_nova_core_phase2_contracts.py`, `test_nova_core_phase14_architecture.py` y `test_nova_core_phase7_interactions.py`, mediante `tests.security.run_s0.run_suite` en modo de selección offline.

Los xfails S0 caracterizan riesgos del baseline legacy. No son tests nuevos que acrediten protección, ni prueba de regresión de S3. Un skip tampoco es PASS.

### 2.3 Pins observados de arquitectura y backend

| Artefacto | SHA-256 actual |
|---|---|
| [Core V1](C:/Users/joseh/Downloads/nova-local-cli/NOVA_CORE_ARQUITECTURA_V1.md) | `293E29C8EC956707AB0F3403235CE21F29EC472E99AA83E52B03428CF6B38273` |
| [SECURITY V1 vigente](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md) | `96924C222E78D8080DE03E4C259E1E8AB36E1E15EDB749910AAD5C2B3ABF1975` |
| `C:\Windows\Sandboxie.ini` | `BE5EA0B65F42C630050A05E225CE5EAB25AFDCF8CEF634979009F2508522742C` |
| `C:\Program Files\Sandboxie-Plus\Templates.ini` | `C9E06A889ED23F1689B8DFCA1210015C256EA71477B2E33B34FEB0DC6FB07933` |
| [F01 histórico](C:/NovaS4SandboxieLab/free_20260930_f01/granted_read/NovaS4FsProbe_F01.exe) | `BC84E7587B6809193AFB1BD5F76FF625064795945ABC840ABD282E04904552E1` |
| [Fuente F01](C:/NovaS4SandboxieLab/free_20260930_f01/controller/nova_s4_fs_probe_f01.c) | `C5A2E6ACEA48F5C4D87A1B8350A49CA5DA19C59E26190DF148056101B92FDE2A` |

El hash canónico SECURITY actual es distinto del fijado al inicio de S0; ese documento tuvo evolución previa. Este informe conserva el hash actual y no lo ha modificado.

La inspección de metadatos de archivos instalados confirmó SandMan `1.18.5`, SbieDll/SbieSvc `5.73.5` y SbieDrv `5.73.2` en la instalación Sandboxie-Plus. El [expediente B0](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/bootstrap_b0_classification.json) ya examinó su combinación oficial. Leer versión/hash de binario no atesta que el driver esté aplicando una policy ahora; no se ejecutó una comprobación dinámica ni un nuevo preflight.

## 3. Inventario de SECURITY por capa

Esta tabla agrupa cambios reales respecto de Core/S0, separando lo conectado al producto de lo experimental. Las referencias apuntan al checkout actual; las entregas no están consolidadas en un commit de SECURITY.

| Área | Archivos/símbolos principales | Estado, dependencias y cobertura |
|---|---|---|
| Core contracts; Permission/Capability/ResourceScope | [authority.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/authority.py:33): `Permission`, `ResourceScope`, `Capability`, álgebra de autoridad | **IMPLEMENTED**, tipos puros Core. Tests S1 de valores/UNKNOWN/subsets. `ResourceScope` es referencia opaca del host; no es una string de path que por sí sola conceda acceso. |
| Ceiling, subject, lifetime | [authority.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/authority.py:105): `GrantLifetime`, `GrantSubject`, `AuthorityCeiling` | **IMPLEMENTED** como contratos inmutables, revisiones y bindings; no hay ceiling físico universal por ser un dataclass. |
| GrantIssuer | [grants.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/grants.py:87): `issue/verify/claim/revoke/replace_ceiling`, `request_digest` | **IMPLEMENTED** Application, registro interno por identidad, consumo one-shot, revocación/atenuación. Integrado productivamente para FS S3; todavía no para la shell. Tests S1/S2/S3. |
| Policy | [policy_engine.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/policy_engine.py:75): `PolicyEngineV2`, `ToolIntent`, `ToolPolicyDecision` | **PARTIALLY_IMPLEMENTED**: decisión estructurada integrada en ToolRuntime, pero reglas de shell y ALLOW para otras tools conservan semántica legacy; no es un compilador completo de autoridad del worker. Tests S2 golden/negativos. |
| Approval | [interactions.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/interactions.py:33): `ApprovalRequest`, `ApprovalGate`; [grants.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/grants.py:168) | **IMPLEMENTED** para bindings one-shot y vínculo comprobable con grants emitidos. Límite: grant shell productivo todavía no emitido. |
| ToolRuntime | [tool_runtime.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/tool_runtime.py:90): `ToolRegistry`, `ToolRuntime`, `LegacyToolAdapter` | **IMPLEMENTED**, ruta común de tools del harness compuesto por Application; autorización S2 y cinco adapters S3. Ruta shell directa legacy en `_execute_bound`. Tests de composición y Core. |
| Application/composition | [session.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/session.py:371), [bootstrap CLI](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/bootstrap_cli.py:263), [bootstrap server](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/bootstrap_server.py:215), [config](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/config.py:262) | **IMPLEMENTED** selección actual `filesystem_profile`, autoridad FS por sesión y rebind de workspace. No selector de los tres perfiles futuros. |
| FS authority / delegación | [filesystem_authority.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/filesystem_authority.py:48): `BrokeredFilesystemTool`, `FilesystemAuthority` | **IMPLEMENTED** para read/write/edit/glob/grep; grants por operación, parent grant de subagente, sin fallback si falta broker. Acoplamiento concreto a infraestructura a revisar, §6. |
| FS broker | [windows_filesystem_broker.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/windows_filesystem_broker.py:67) | **IMPLEMENTED**, único alcance productivo con enforcement de objetos/handles S3. Requiere WindowsHandleRoot y GrantVerifierPort. `osProcessSandbox=false` expresamente. |
| FS handles | [windows_fs_handles.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/windows_fs_handles.py:171): `_nt_open`, `WindowsHandleRoot` | **IMPLEMENTED**, raíces/objetos reales, operaciones relativas a handles, rechazo de superficies no soportadas. Pruebas S3 Windows; no certificación de cada alias existente. |
| SandboxPort | [authority.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/authority.py:345): `prepare/execute`, `SandboxRequest`, `SandboxAttestation` | **SPEC_ONLY** como puerto productivo concreto: el Protocol sí existe y se prueba con fake. No launcher conectado a él. |
| Attestation gate | [grants.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/grants.py:261): `require_attestation` | **IMPLEMENTED** como validador de contrato; no emisor/validador de evidencia OS confiable. `FakeBroker` de tests no es SandboxBroker productivo. |
| SandboxBroker | Objetivo [SECURITY §13](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md:220) | **NOT_IMPLEMENTED** como componente de proceso productivo. `WindowsFilesystemBroker` no es ese componente: media cinco tools FS host, no workers arbitrarios. |
| Worker / process | [shell_executor.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/shell_executor.py:109), [shell tool](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/tools/shell_tool.py) | **PARTIALLY_IMPLEMENTED** lifecycle legacy: Popen, cancel/deadline, captura y terminación best effort. Sin aislamiento de shell productivo ni autoridad menor que usuario. |
| Backend Sandboxie / selección | Código separado en [controller](C:/NovaS4SandboxieLab/free_20260930_f01/controller), sin imports/adapters en producto | **EXPERIMENTAL**. `SandboxieAdapter`/`SandboxieBackend` productivos **NOT_IMPLEMENTED**. Instalar Sandboxie no los crea. |
| Subagentes | [sub_agent.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/sub_agent.py:278), [AgentTool](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/tools/agent_tool.py:129), [StartSubAgent Application](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/session.py:849) | **IMPLEMENTED** delegación y revocación FS; **PARTIALLY_IMPLEMENTED** autoridad total porque shell/red de hijos siguen rutas legacy. |
| Networking | [web_fetch_tool.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/tools/web_fetch_tool.py:84), intent estructurado V2 | Runtime fetch heredado **IMPLEMENTED**; network grant/firewall/broker S5 **NOT_IMPLEMENTED**. `file://` es superficie relevante fuera de las cinco tools S3. |
| Environment/secrets | [security.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/security.py:159), token host approval [server.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/server.py:69) | Saneamiento por denylist heredada y retirada del token approval del entorno **PARTIALLY_IMPLEMENTED**. Allowlist del worker S6 existe sólo en laboratorio, no en shell productiva. |
| Audit / outcomes | Eventos ToolRuntime, `ToolResult/EffectState`; [AuditLog port](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/persistence.py:48), [persistencia](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/persistence.py) | Lifecycle/outcomes tipados **IMPLEMENTED**; SecurityAuditLog completo grant→backend→worker→cleanup **NOT_IMPLEMENTED**. Logs existentes no certifican S7. |
| Desktop/CLI approval trust | [host_approval.ts](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/electron/host_approval.ts:31), [ipc_origin.ts](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/electron/ipc_origin.ts:6), [JSONL](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/interfaces/jsonl_application.py:77), [CLI](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/interfaces/cli_application.py:28) | **IMPLEMENTED** S2: host controla resolución, renderer no autoridad, CLI exige TTY. No se cambió UX durante esta auditoría. |
| Tests / fixtures | [tests SECURITY](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security), laboratorio F01/F02 | Tests S0–S3 de producto; S4 prototipos opt-in y suites diagnósticas externas. No son un único gate release. |
| Documentación / investigación | [docs SECURITY](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs), fuentes canónicas y [evidence](C:/NovaS4SandboxieLab/free_20260930_f01/evidence) | Normativa **SPEC_ONLY** donde no hay código; informes/attempts **HISTORICAL**; controladores **EXPERIMENTAL**. |

Los 17 archivos alterados dentro del inventario «productFiles» de S0 incluyen un test Desktop. En la clasificación funcional del estado Git actual hay 16 tracked de producto/configuración y ocho tracked de tests, incluido ese test Desktop. Las nuevas seis piezas Python de autoridad/broker y dos helpers Electron son código nuevo, no cambios visibles en `git diff --stat` hasta incorporarlos a Git.

## 4. Estado real S0–S8

| Fase | Estado técnico | Alcance que puede justificarse |
|---|---|---|
| S0 | **VALIDATED_FOR_CURRENT_CONTRACT** | Baseline, threat model, caracterización de riesgos, hashes y tests previos. No sandbox. |
| S1 | **VALIDATED_FOR_CURRENT_CONTRACT** | Contratos, registro de grants, bindings, revocación y atenuación lógicas. Uso FS real incorporado en S3. No enforcement universal de cualquier permiso. |
| S2 | **VALIDATED_FOR_CURRENT_CONTRACT** para su entrega; **PARTIAL** respecto de toda la arquitectura objetivo | Decisiones/bindings/actor host y CLI implementados. Policy para otras tools y grant→worker shell aún incompletos. |
| S3 | **VALIDATED_FOR_CURRENT_CONTRACT** Windows, cinco tools | Broker de objetos/handles integrado. Raíces externas no implementadas, superficies rechazadas/coverage limitada documentadas. No sandbox de proceso. |
| S4 arquitectura/producto | **PARTIAL** | Puerto/attestation contracts y lifecycle legacy existen; backend/launcher/broker productivos no conectados. |
| S4 investigación | **EXPERIMENTAL_ONLY**, resultados **HISTORICAL** | Ensayos de backends y herramientas de atestación; no certificación global. |
| S5 | **NOT_STARTED** como fase nueva | Hay fetch/proveedores heredados e intents; no enforcement network V1. No se ha iniciado con esta tarea. |
| S6 | **NOT_STARTED** como fase nueva | Defensas legacy y prototypes de env no equivalen a integración S6. |
| S7 | **NOT_STARTED** como fase nueva | EventJournal y AuditLog de Core/legacy no cierran el gate SecurityAudit. |
| S8 | **NOT_STARTED** como gate integrado de SECURITY | Tests adversariales parciales de S0–S4 no forman la matriz final S0–S7. |

### 4.1 S0: fundamento que permanece útil

El [baseline S0](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s0_baseline.md:1) identifica diez tools públicas, composición común, contexto de ejecución, modelos/proveedores y threat model SEC-01..SEC-16. Distingue validación, policy, aprobación y enforcement; registra shell con autoridad host, FS absoluto, `file://`, secretos/env/logs, stdin y árbol best effort.

Los riesgos no desaparecen al bajar el alcance de certificación. V1.1 necesita una matriz de qué riesgo reduce cada perfil, sin declarar resuelto lo que sólo deja de ser gate obligatorio. No es necesario repetir la investigación general ni reconstruir el baseline conceptual. Sí habrá que mantener pins de un release nuevo y tests de regresión de su implementación.

### 4.2 S1: contratos y autoridad

| Pieza | Código y comportamiento real | Compatibilidad V1.1 |
|---|---|---|
| Permission / Capability | Verbos tipados, estados KNOWN/UNKNOWN; `known_authority` rechaza autoridad desconocida. | Conservar. No equiparar “capability concedida” a imposibilidad física de toda acción del worker. |
| ResourceScope | Referencia opaca `namespace/reference` con igualdad exacta, sin magia de path-prefix ni wildcard. | Conservar. El adapter/broker traduce scopes verificables; no rebajar tipos a paths libres del LLM. |
| AuthorityCeiling | Identidad/revisión/session/lifetime/capabilities/perfil, inmutable. | Conservar autoridad máxima lógica; revisar relación con strength/evidencia de perfil. |
| CapabilityGrant | Registro interno, digest, subject, ceiling/policy revisions, parent, lifetime. Copia igual por valores no es autoridad registrada. | Conservar; no convertirlo en credential JSON del renderer. |
| GrantSubject / Lifetime | Session/operation/toolCall/turn/agent/parent, fechas conscientes de timezone, lifetime hijo dentro del padre. | Conservar. |
| Parent/child attenuation | `authority_is_subset` + chain verification; revocar padre invalida uso derivado, revisión ceiling no reactiva grants antiguos. | Conservar; llevarlo a ejecución de proceso que todavía falta. |
| GrantIssuer | `issue` idempotente por operación/digest, `verify` sin consumo, `claim` one-shot bajo lock. | Conservar. |
| requestDigest | Argumentos y bindings de invocación, cwd/workspace, hash env, authority/revisions/lifetime y `requiredGuarantees`. [Código](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/grants.py:44). | Cambio menor necesario si cambia significado/taxonomía de perfiles: versionar digest y bindings, no relajar coincidencia. |
| Profile dominance | Comprueba inclusión de `required_guarantees` del ceiling y parent en request. [Código](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/grants.py:138). | **Debe revisarse**: nombre de perfil y niveles CONFIGURED/BEST_EFFORT no tienen semántica actual. Vaciar requiredGuarantees en Standard no define una relación segura entre perfiles. |
| SandboxAttestation | `covers` sólo considera `ENFORCED` y los requisitos declarados. Referencia de evidencia textual no autentica OS. | Conservar separación claim/evidencia, revisar gate por perfil; proofs antiguos pertenecen a Hardened. |

La cadena Policy→Approval→Grant→broker ya puede verificarse para operaciones FS y en tests del contrato. No se debe afirmar que todas las ejecuciones shell/productivas siguen esa cadena completa hoy.

### 4.3 S2: decisión, aprobación y actor

`PolicyEngineV2` distingue `ALLOW / REQUIRE_APPROVAL / DENY`, tiene reason codes y `ToolIntent` estructurado. Sus hints de paths/URLs/efectos **no son autoridad comprobada**. En [evaluate](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/policy_engine.py:115), tool desconocida se deniega; bash conserva `ShellPolicy`; el resto puede obtener `LEGACY_TOOL_ALLOW`. Cambiar el modelo de certificación no basta para transformar esas reglas en una policy de Sandboxie/grants de proceso.

`ApprovalRequest`/`ApprovalGate` vinculan approvalId, session/turn/operation/toolCall, argumentos congelados, cwd, revisión, digest, deadline y cancelación. Se rechazan stale, duplicados o mismatch. El issuer consulta la request aprobada del mismo gate; **approvalId no es un campo directo de CapabilityGrant**: el vínculo adicional está en el registro Application. Esa diferencia de representación no exige rehacer el modelo.

Desktop: Electron main conserva una credencial aleatoria por instancia, correlaciona `ApprovalRequired`, controla confirmación y envía `ResolveApproval`. El renderer no puede resolver mediante los dos canales expuestos; IPC verifica ventana activa, main frame y documento exacto. JSONL verifica el canal host y rechaza resoluciones no autorizadas. Esto refuerza una frontera renderer→host; no atesta que un proceso host comprometido sea honesto.

CLI: [has_interactive_approval_terminal](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/interfaces/cli_application.py:28) requiere stdin y stderr TTY. `--yes` no sustituye esa autoridad en los composition roots actuales, que usan `auto_approve=False`. Existe un parámetro interno `ToolRuntime(auto_approve=True)` y compatibilidad por callback; deben quedar fuera de una composición Standard si se exige aprobación, sin presentar su existencia como bypass del CLI actual.

**Conservar sin cambios funcionales previstos:** actor host/TTY, binding exacto, stale/cancel, resolución one-shot, boundary IPC y separación `ask_user`/approval. **Revisar sólo integración:** emisión de grant para proceso, decisiones por perfil y eliminación de rutas legacy implícitas en esa composición. No hay necesidad demostrada de sustituir ApprovalGate ni Desktop/Application API.

### 4.4 S3: filesystem real, alcance y límites

Ruta productiva:

~~~text
ToolInvocation → ToolRuntime → BrokeredFilesystemTool
→ FilesystemAuthority → GrantIssuer.issue/claim
→ WindowsFilesystemBroker → WindowsHandleRoot / handle relativo
~~~

No se concede HOME implícito. El host fija workspace como objeto raíz; los grants usan la referencia del broker. Read/glob/grep requieren `filesystem.read`; write requiere `filesystem.write`; edit requiere ambos. El default actual `BROKERED_FILESYSTEM_S3` es un perfil **de esas tools**, no un selector global SANDBOXED_STANDARD.

| Superficie | Implementación / test / limitación |
|---|---|
| read | Abre mediante root-relative handle; lectura sobre objeto, no executor legacy. |
| write | Preflight de ruta, parent handle, temporal bajo root y reemplazo relativo/atómico; efecto incierto si hay mutación parcial. |
| edit | Requiere read y write; lee objeto y reemplaza mediante broker. |
| glob / grep | Enumeración desde handles, traversal limitado; reparse no se recorre como salida autorizada. |
| Absolutos dentro de root | Se aceptan sólo si se normalizan al scope exacto y luego se abren relativamente al objeto raíz; test de case alias. |
| Absolutos externos, `..`, prefix parecido | Denegados; no se usa `Path.resolve()` como único enforcement. |
| Symlink/junction/reparse | `FILE_OPEN_REPARSE_POINT` y rechazo de objetos reparse; junction real probada. File symlink real quedó skipped por Win32 1314. No inventar esa cobertura. |
| Hardlinks / aliases | Hardlinks multi-link se rechazan como unsupported; case-insensitive probado. No hay certificación universal de todos los aliases de Windows. |
| UNC, ADS, device/special names | DENY/UNSUPPORTED explícito; no implementación prometida. |
| TOCTOU | Root/parent handles retenidos y operaciones relativas; tests de root rename+junction swap y cambio de nombre antes de replace. Dos carreras probadas no son prueba de todas las carreras concebibles. |
| Object binding | Root identity y apertura por handle; metadata `rootResourceId`/grant y resultado honesto. |
| Raíces externas | Flujo de grant adicional por operación especificado, **NOT_IMPLEMENTED** en composición actual; se deniega. |
| Worktree / subagent | El worktree no crea nueva autoridad; puede fallar si queda fuera del scope padre. Attenuation FS real, no contención universal del proceso hijo. |

Referencias principales: [_component/_nt_open](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/windows_fs_handles.py:159), [root/parts/open](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/windows_fs_handles.py:242), [write](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/windows_fs_handles.py:387) y [tests Windows](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s3_windows_broker.py:60).

El broker rechaza un request que pida garantía completa de proceso y publica `osProcessSandbox=false`. Si falla creación del broker en [session](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/session.py:390), los adapters permanecen brokered y ToolRuntime deniega, sin regresar a las tools FS legacy.

**S3 no depende de completar la definición fuerte de S4 para conservar su enforcement actual.** La propia arquitectura [tabla S3](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md:411) admite proteger las tools FS mientras bash no está aislado. Bajo Standard, S3 sigue siendo útil con el mismo scope. No implica que un comando shell, `web_fetch(file://...)`, un helper host o un proyecto aplicado fuera de ese broker ya estén cubiertos.

## 5. S4: producto frente a investigación

### 5.1 Arquitectura/producto actual

| Componente deseado | Estado real |
|---|---|
| SandboxPort | Protocol Core `prepare/execute`; ninguna implementación de proceso en la composición normal. |
| Worker launcher | Popen de shell legacy; launchers AppContainer/Sandboxie existen sólo en laboratorio. |
| SandboxBroker | Objetivo normativo sin implementación productiva para creación/control de workers. |
| SandboxieAdapter / backend selection | No hay adapter instalado en el runtime ni selección de backend global. |
| Process tree / lifecycle | Context cancellation/deadline y best-effort host tree termination existen. No atestación de descendientes Sandboxie en producto. |
| stdin / handles | El Popen actual no fija `stdin=DEVNULL`. No hay allowlist explícita del canal host para el worker productivo. Los prototipos S4 sí investigaron estas restricciones. |
| Timeout / cancel | Implementados en executor legacy; `taskkill /T /F` y kill no se pueden renombrar “contención preventiva”. |
| Output / recursos | Truncamiento de texto posterior a captura; no cuota física G-T ni garantía G-H. |
| Audit backend/box/cleanup | Eventos/IDs y resultados de tools existen; datos Sandboxie aparecen en expedientes diagnósticos, no en audit normal del producto. |
| Aplicación de resultados | S3 write/edit media sus propias operaciones. No hay importación productiva controlada de resultados de una box a proyecto original. |

[Shellexecutor](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/shell_executor.py:126) y [_terminate_process_tree](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/shell_executor.py:157) son la evidencia del estado actual. No debe sustituirse su lectura por el diagrama objetivo de SECURITY ni por una box ya instalada en Windows.

### 5.2 Inventario de investigación S4

| Línea | Archivos/evidencia | Resultado reutilizable y límite |
|---|---|---|
| AppContainer + Job + broker | [s4_windows_lab.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/s4_windows_lab.py:1), [tests prototypes](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s4_prototypes.py), [laboratorio](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_laboratorio.md:13) | Proceso suspendido, SID/perfil, Job KILL_ON_JOB_CLOSE, consulta identity, stdin NUL, handle list, env allowlist. Backend seleccionado históricamente para identidad/proceso, **sin integrar** porque FS ceiling ante ACL compartidas falló. |
| LPAC | Mismo laboratorio y tests | Opt-out ALL APPLICATION PACKAGES redujo acceso, pero permaneció acceso por ALL RESTRICTED APPLICATION PACKAGES/perfil propio. No resolver por el nombre LPAC. |
| Restricted Token | [test_s4_restricting_tokens](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s4_restricting_tokens.py), investigación en laboratorio | Bootstrap 0xC0000142 en combinación inicial; variantes restrictivas investigadas y congeladas. No convertir WRITE_RESTRICTED/World en read ceiling. |
| Job Objects | Laboratorio S4 | Identidad/árbol/limits específicos útiles; no cierran aislamiento FS ambiental ni storage agregado. |
| Windows Sandbox | [evidencia postreinicio](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_laboratorio.md:611), [último laboratorio](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_laboratorio.md:821) | Compatibilidad PowerShell/Python/Node/Git/npm offline, shares/staging, revocación/transporte, cierre y Ollama. VM puede sobrevivir a pérdida del controlador; no se probó G-T/G-H total. No adapter productivo. |
| Hyper-V | [plan](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_plan_validacion_hyperv.md), B/B2 | Plan y prerrequisitos, no evidencia de VM creada/ejecutada para certificar gates. Licencias/espacio/memoria no convertirlos en mediciones de nuestro futuro backend. |
| OpenCode/Open Interpreter | [auditoría comparativa](C:/Users/joseh/Downloads/auditoria_comparativa_seguridad_opencode_openinterpreter.md:1) | Auditoría estática de ZIPs. Permisos OpenCode no aíslan. Código de tokens/MXC/PSEC derivado de Codex debe distinguirse de autoría OI; no resolvió ceiling/storage, no se ejecutaron repositorios. |
| Sandboxie / Isolate | [auditoría estática](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_auditoria_sandboxie_isolate.md:1) | Minifilter con mediación FS adicional es propiedad investigable; redirección no cuota física. Isolate/Linux/WSL2 no backend Windows equivalente ni límite del consumo total del host. Licencias, instalación y TCB siguen responsabilidades futuras. |
| Perfil gratuito F01 | [laboratorio Sandboxie](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_laboratorio_sandboxie.md:140), [atestación](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/atestacion_previa_nova_s4_fs_free_f01.md) | Raíces de fixture no solapadas, lectura concedida/escritura virtualizada/closed externas; ConfigLevel=10 estabiliza defaults locales. No UseRuleSpecificity, certificado ni funciones comerciales. Herencias admitidas sólo para experimento focal no prueban ceiling productivo. |
| F01 native / READY / bootstrap | [fuente](C:/NovaS4SandboxieLab/free_20260930_f01/controller/nova_s4_fs_probe_f01.c), B0/B2/R1–R4 y expedientes | Bootstrap básico y transporte fijo demostrados en probes benignos; el antiguo 0xFFFFFFFF no tiene causa retrospectiva demostrada. |
| R1–R4 y H1–H4 | [pipeline](C:/NovaS4SandboxieLab/free_20260930_f01/controller/r1_lifecycle_pipeline.ps1), [estabilización offline](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_estabilizacion_offline_harness_h1_h4_20261001.md) | EnumProcessEx INOUT corregido, parser/agregación/Contains estabilizados, replays, dominios BOX_PROCESS/host separados. No reinterpretar PIDs históricos por timing. |
| STOP-only histórico | [informe estabilización](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_estabilizacion_stop_only_20261001.md), expedientes de reproducción | Último READY+STOP concluyó HISTORICAL_READY_FAILURE_NOT_REPRODUCED; no explica el fallo antiguo. Reader dedicado no ligado a SampleAll. |
| op1 | [informe](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_etapa3_op1_ejecucion_13005c81_20261001.md) | PASS lectura concedida; resultado correlacionado + mismo objeto/hash + lifecycle box. No denegación externa. |
| op3 | [informe](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_one_op3_ejecucion_7a64df79_20261001.md) | PASS create/write virtualizado; host ausente y copia exacta presente. La copia **se conserva** como baseline, no se limpia. |
| Host control op6 | [informe](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_control_host_op6_38ac23ae_20261001.md) | ALLOW read-only usuario no elevado/fuera de box sobre objeto de fixture. No repetir. |
| op6 histórico | [informe/expediente](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_intento_one_op6_b6e99a25_20261001.md), revisión token posterior | READ_DENIED observado; comportamiento/atribución UNKNOWN por atestación insuficiente. No es PASS del minifilter ni de Standard. |
| Token attestation v1/v2 | [auditoría](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_auditoria_token_op6_offline_20261001.md:1), [authority v2](C:/NovaS4SandboxieLab/free_20260930_f01/controller/op6_windows_authority_v2.cs:132) | Tres linajes separados, TokenStatistics, tipo/nivel/restricted/MIC y comparación. Root cause de THREAD_IMPERSONATION+Primary **UNKNOWN**, no se encontró explicación trivial probada. v2 offline no revalida aquel run. |
| F02 | [fuente v3](C:/NovaS4SandboxieLab/free_20260930_f01/controller/nova_s4_op6_causal_probe_f02_v3.c), [manifest v3](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/f02_causal_probe_offline_manifest_v3.json), [decoder](C:/NovaS4SandboxieLab/free_20260930_f01/controller/f02_host_decoder_gate_v3.cs) | Probe separado, A/B/C, ARM/EXEC one-shot, wire v2, decoder offset explícito, equivalencia semántica. Instrumentación offline, **no F02 causal ejecutado**. |
| F02 R0/R1 | [R0 offline](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_f02_r0_runner_offline_20261001.md), [cierre v3](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_f02_v3_stop_fail_closed_offline_20261001.md) | R0 READY→STOP antes ARM, R1 A→STOP antes EXEC; specs/suites. No ensayo live cerrado de R0/R1, no evidencia de syscall F02 real. |
| Watchdog / JSON-safe | [persistencia](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_f02_r0_persistencia_offline_v2_20261001.md), [watchdog](C:/NovaS4SandboxieLab/free_20260930_f01/controller/f02_r0_preflight_watchdog_v2.ps1) | DTO acotados, rechazo objetos .NET, snapshots/streams/one-child/timeout UNKNOWN. Reproducer ServiceController sólo explica su reproducción, no el attempt original. |
| Pipe observer v1/v2 | [informe v2](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_f02_r0_pipe_observer_v2_offline_20261002.md:1), [v2](C:/NovaS4SandboxieLab/free_20260930_f01/controller/f02_r0_preflight_pipe_probe_v2.cs) | Raw completion/cancel/correlation mejorados. Cancel confirmada no sella una apertura posterior hasta CloseHandle; no gate total de ausencia de cliente listo. |
| G-T / G-H | [decisión B](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_decision_almacenamiento.md), [B2](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_especificacion_b2.md:9) | G-T todos recursos T con cota preventiva física; G-H recursos globales/compartidos. Ambos sin certificar. Monitoring/CopyLimit/sparse no acreditan cuota total. |
| Host TCB / raw monitor | [cierre op6](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_cierre_prerrequisitos_op6_20261001.md), replays/dominios H4 | HOST_CANDIDATE no promovidos por nombre/parent/timing. MonitorGet2 consume buffer por sesión y compite con SandMan; RAW_MONITOR_ACQUISITION=UNKNOWN. |

Estos archivos tienen valor de continuidad, no son el futuro harness productivo. Extraer patrones pequeños de launch/identity/lifecycle/reader/DTO es distinto de incorporar el controlador diagnóstico completo y su árbol de dependencias.

### 5.3 Expedientes que no deben reinterpretarse

| Identificador / línea | Estado a conservar |
|---|---|
| PIDs históricos 31024 y 18876 | `UNKNOWN_HELPER_HISTORICAL`. No identificar retrospectivamente como RpcSs/DcomLaunch. |
| `4a2327e0-b663-4792-8912-3e3bd748a8d9` | Reprocesamiento de 48 muestras: `boxLifecyclePass=true`, R1 PID17576 y RpcSs11008/DcomLaunch5512 identificados; global `H4_INCONCLUSIVE_HOST_TCB`. Host24464/27396 siguen `HOST_CANDIDATE / LIFECYCLE_UNKNOWN`. |
| `2b19caed-17b0-4c82-90de-85c2c39230a0` | `HISTORICAL_OWN_EXIT_25 / INCONCLUSIVE_PROTOCOL_PACING`; no se sustituye por la reproducción posterior exit0. |
| `13005c81-c848-466c-8d6f-64c731251462` | op1 `PASS / PASS_BOX_LIFECYCLE / HOST_TCB UNKNOWN`. Contabilidad reparada mediante derivados offline, no JSON bruto. |
| `1f379650-3c10-42df-8722-cb9f24089a7c` y `559876ff-f019-4ad7-b723-f03ec46b74f0` | op3 `NO_LAUNCH / NOT_EXECUTED`; no evidencia contra op3. Segundo detectó drift de Sandboxie.ini. |
| `7a64df79-8e44-4357-8086-f669f01149bd` | op3 `PASS / PASS_BOX_LIFECYCLE / HOST_TCB UNKNOWN`; copia preservada. |
| `99535966-1732-4aba-8472-c8e741616a0f` | Primer control host `UNKNOWN` por persistencia; no sobrescribir. |
| `38ac23ae-63c8-40c2-aea0-7fae854af0a8` | Control host `HOST_CONTROL_READ=ALLOW`, independiente de op6 sandboxed. |
| `b6e99a25-9f25-4a87-a1c5-26ca6b0c9d64` | `READ_DENIED`; `FOCAL_POLICY_BEHAVIOR_RESULT=UNKNOWN`; `DENIAL_CAUSAL_ATTRIBUTION=UNKNOWN`; `EXECUTION_LIFECYCLE_GATE=PASS_BOX_LIFECYCLE`. |
| `b0bfda2f-8d41-4a6e-be17-205f6ea40952` | Preflight consumido `UNKNOWN`. Explicación del reproducer de serialización no cambia ese estado. |
| `65c60a26-2d19-46dc-8a6f-d57d5aa33918` | `UNKNOWN / WATCHDOG NOT_STARTED / BLOCKED_EXTERNAL_WATCHDOG_NOT_IMPLEMENTED`. |
| `957d481d-dedb-4e13-b056-70a6d4b1aecc` | `F02_R0_PRELAUNCH=UNKNOWN`, watchdog COMPLETED, pipe UNKNOWN, config post-cierre NOT_EVALUATED, `CONNECTION_OBSERVER_ERROR:109`, cero worker/launch/ARM/EXEC. Root cause UNKNOWN. |

La auditoría de tokens v1 siguió el handle correcto de OpenThreadToken, constante TokenType=8 y lectura de int compatibles; no pudo demostrar por qué se observó Primary=1. **No se registra un bug de constante/marshalling como causa demostrada.** La v2 añade comprobaciones necesarias, pero no promueve op6 histórico a PASS.

La suite STOP-only funcional versionada conserva PASS 38/38; la suite temporal original conserva su FAIL y `KNOWN_FLAKY`. No se presentan como el mismo test aprobado.

### 5.4 Último punto material de laboratorio

El [delivery manifest](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/f02_pipe_v2_review_20261002/delivery_manifest.json) enumera **1437 archivos en 15 shards**, y 160 comprobaciones de preservación históricas. Esta auditoría volvió a verificar los **1437 hashes/tamaños y los 15 shards: cero diferencias**. Es el inventario de aquella entrega, no una afirmación de que contiene todos los archivos desde el primer laboratorio: la raíz actual contiene 5384 archivos, 381 en controller y 39 informes .md en evidence.

El [manifest R0 v11](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/f02_r0_manifest_offline_v11.json:1), hash `C0D9C2E437C899C45F46FB6BDDB774C6310A60055F323FF6CD370D9737DF4901`, declara:

~~~text
executionReady=false
realPreflightEligible=false
runnerRuntimeBlocked=true
watchdogReleaseBinding=NOT_PREPARED
runtimeGateDerivation=DEFERRED_FULL_ACCEPTANCE_TAIL_UNSEALED
~~~

El observer v2 tuvo 81 observaciones nativas sintéticas archivadas, no nuevos preflights. Reprodujo 109 cerrando una aceptación pendiente sin cliente sintético, pero también mostró la cola cancelación→cierre donde un cliente aún puede abrir. Ninguno de esos hechos reconstruye el 109 histórico ni acredita `NO_CLIENT_BOUNDED` global.

**Ese es el punto de pausa Hardened.** No debe ser prerequisite del producto Standard resolver la ausencia universal de cliente durante ese preflight diagnóstico. Tampoco se debe liberar el runner v11 ni falsificar su gate como parte de la transición.


## 6. Dependencias con Nova Core y desviaciones concretas

| Frontera Core | Comprobación actual | Consecuencia |
|---|---|---|
| AgentRuntime sin concreciones SECURITY | [AgentRuntimePort](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/runtime.py:24), [LegacyAgentRuntime](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/legacy_runtime.py:13) y AgentLoop no introducen import de GrantIssuer/PolicyEngine/SandboxBroker concreto. AST y test Core de arquitectura pasaron. | No reescribir loop ni Core. Mantener adapter de compatibilidad que suministra tools ya mediadas. |
| ToolExecutionPort | [contracts.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/contracts.py:607), ToolRuntime y LegacyToolAdapter | Puerto se conserva. El camino normal de Application entrega adapters; llamar una tool legacy aislada desde código externo no es la composición segura de producto. |
| ExecutionContext | [contracts.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/contracts.py:230) | Workspace/cwd/env/IDs/cancel/deadline/capability snapshot viajan sin `os.chdir` global. Snapshot de disponibilidad no concede autoridad: grants son otro contrato. |
| Turn / Generation / Operation | Application coordina y ToolRuntime emite terminales/outcomes; Core conserva tipos | No duplicar lifecycle en SandboxieAdapter. Puede haber efectos parciales/UNKNOWN: conservar esa honestidad. |
| EventSink | [contracts.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/contracts.py:611), [SessionEventStream](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/events.py:74) | Eventos comunes; stream es RAM con gaps/replay, no una evidencia durable SecurityAudit. |
| Application API | [commands](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/commands.py), [session](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/session.py) | CLI y Desktop siguen una coordinación común; no se introdujo un harness SECURITY paralelo. |
| ProviderManager | [providers.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/providers.py:163) | Sin delta SECURITY observado contra HEAD. Proveedores host no deben confundirse con red libre del worker ni introducir credenciales en éste. |
| ContextManager | [core/context.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/context.py:156), [application/context.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/context.py) | Context budget ≠ cuotas G-T/G-H. Sin cambios SECURITY observados que exijan rehacerlo. |
| RAGService | [application/rag.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/rag.py:47), puertos Core e implementación Infrastructure | Conservado; retrieval host no convierte datos en autoridad ni debe pasar al renderer como raíz de confianza. |
| Subagents | Delegación FS en tool `agent` y comando `StartSubAgent` | Conserva IDs/cancellation/provider/FS scopes. Falta herencia del futuro perfil de proceso y no ampliar autoridad shell/red. |

Hay una deuda localizada: [build_session_filesystem_authority](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/filesystem_authority.py:48) **importa y construye WindowsFilesystemBroker concreto dentro de Application**, y el mismo módulo hace imports de infraestructura para capabilities/perfil. El contrato Core sigue limpio. La dirección objetivo de [SECURITY §6](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md:101) reserva el enlace de implementaciones al composition root; conviene extraer una factory/puerto inyectado en una revisión menor. No es evidencia de que todo Core esté roto ni justifica descartar S3.

También persisten adapters legacy de tools/agente para compatibilidad. Su presencia no significa un segundo Agent Loop activo en la composición normal, pero V1.1 debe probar que una ruta de proceso declarada Standard no puede esquivar SandboxPort mediante ellos. Esa es una prueba de integración, no una migración general de Core.

El límite host/UI permanece relevante: file explorer, Git/updater y administración de modelos son servicios host; su actividad no demuestra authority del worker ni queda mágicamente protegida por Sandboxie. La arquitectura Core permite preview UI de sólo lectura separado del agente; cualquier contenido usado para decisiones/efectos agentic debe conservar la mediación declarada.

## 7. Matriz de reutilización S1–S4

| Pieza | Clasificación | Justificación y acción futura |
|---|---|---|
| Permission / ResourceScope / Capability | **KEEP_AS_IS** | Tipos y separación read/write válidos en cualquier perfil. |
| GrantSubject / GrantLifetime | **KEEP_AS_IS** | IDs/lifetime/parent bindings no dependen de certificación absoluta. |
| AuthorityCeiling | **KEEP_WITH_MINOR_CHANGE** | Conservar máxima autoridad delegable; expresar por separado configuración/strength física del backend. |
| CapabilityGrant y registro | **KEEP_AS_IS** | Inmutabilidad, identidad registrada y one-shot impiden ampliación lógica/replay. |
| GrantIssuer, chain/revoke | **KEEP_WITH_MINOR_CHANGE** | Mantener invariantes; ajustar sólo comparación/binding de perfiles si cambia representación. |
| requestDigest / revisions | **KEEP_WITH_MINOR_CHANGE** | Nuevo contrato de perfiles exige versión explícita y tests, sin convertir requests viejas en vigentes. |
| PolicyEngineV2 tipos/estructura | **KEEP_AS_IS** | ALLOW/APPROVAL/DENY y intent siguen siendo necesarios. |
| PolicyEngineV2 reglas legacy | **KEEP_WITH_MINOR_CHANGE** | Reglas de perfil y backend admitido faltan; no son una implementación completa de autoridad V1. |
| ApprovalGate y binding approval↔grant | **KEEP_AS_IS** | No depende de G-T/G-H ni de evidencia causal de minifilter. |
| Electron host/IPC/CLI TTY | **KEEP_AS_IS** | Frontera actor/renderer válida; no diseñar una nueva UX en esta transición. |
| ToolRuntime / LegacyToolAdapter | **KEEP_WITH_MINOR_CHANGE** | Introducir ruta process→SandboxPort preservando idempotencia/events/errores. |
| FilesystemAuthority / delegación | **KEEP_WITH_MINOR_CHANGE** | Mantener scopes/grants; desacoplar factory de infraestructura y revisar profile composition. |
| WindowsFilesystemBroker / handles | **KEEP_AS_IS** | Enforcement concreto de cinco tools S3 sigue siendo útil. No degradarlo a protección sólo configurada por cambiar shell. |
| S3 alcance/claims | **RECLASSIFY** | Declarar protección de adapters, no de todos los accesos del proceso Nova o comandos shell. Esa distinción ya existe en metadata. |
| SandboxPort / SandboxRequest | **KEEP_WITH_MINOR_CHANGE** | Extensión acotada para contrato Standard: precondiciones, lifecycle, cancel/timeout, observación de backend y outcomes. |
| GuaranteeEvidence / covers / requiredGuarantees | **KEEP_WITH_MINOR_CHANGE** | El algoritmo actual requiere ENFORCED. Standard necesita otro gate por requisitos/estado; no basta renombrar ENFORCED ni vaciar todos los requisitos. |
| Shell legacy | **RECLASSIFY** | Backend explícito Legacy, no Standard ni fallback. Correcciones comunes como stdin/handles pueden seguir necesarias en adapters futuros. |
| SandboxBroker/SandboxieAdapter | **UNKNOWN / NOT_IMPLEMENTED** | No hay pieza productiva que “conservar”; falta implementar después de arquitectura aprobada. |
| Launch/identity/lifecycle diagnósticos | **RECLASSIFY** | Fuente de patrones/tests; seleccionar componentes pequeños, no copiar todo el harness de laboratorio. |
| AppContainer/LPAC/Restricted/VM | **DEFER_TO_HARDENED** | Conservar resultados y límites; no reabrir por preferencia de tecnología. |
| F01 op1/op3 y host control | **RECLASSIFY** | Evidencia concreta de propiedades y fixtures, no suite del adapter Standard ni certificación general. |
| op6 / tokens v2 / A-B-C / F02 | **DEFER_TO_HARDENED** | No requisitos productivos Standard. Históricos UNKNOWN conservados. |
| Raw monitor / host TCB / full pipe absence | **DEFER_TO_HARDENED** | No eliminar; no bloquear por sí solos el camino Standard si no afectan precondiciones exigidas de éste. |
| G-T/G-H/B/B2/cuotas físicas totales | **DEFER_TO_HARDENED** | Permanecen sin certificar y la alternativa B provisional; dejan de ser gate obligatorio sólo tras enmienda V1.1. |
| Claims absolutos de perfil seguro certificado | **REMOVE del claim productivo futuro** | Eliminar la afirmación, no borrar código, tests ni evidencia que documentan el objetivo fuerte. |
| Audit Core/outcomes | **KEEP_WITH_MINOR_CHANGE** | Añadir trazabilidad mínima backend/box/versión/cleanup sin fabricar certificación S7 completa. |
| Tests S0/S1/S2/S3 | **KEEP_AS_IS**, luego adiciones puntuales | Son activos contra regresión. Retener caracterización legacy y pruebas de UNKNOWN; no sustituirlas todas por smoke Sandboxie. |

**No se encontró una causa técnica que obligue a rehacer S1, S2 o S3 desde cero.** Las dependencias muestran contratos lógicos y broker FS ya desacoplados de un launcher sandbox universal. Los cambios transversales previsibles se concentran en significado de perfil/evidencia, digest/dominancia, policy composition y conexión de la shell.

## 8. Compatibilidad conceptual de los tres perfiles

Esta tabla no es código implementado ni diseño de UI. Actualmente el único selector relacionado es `filesystem_profile`; no debe interpretarse como uno de los tres perfiles globales propuestos.

| Dimensión | LEGACY_UNISOLATED | SANDBOXED_STANDARD | HARDENED_EXPERIMENTAL |
|---|---|---|---|
| Selección | Usuario explícito; sin claim de sandbox. | Opción normal de producto seleccionable por usuario; activación exige backend disponible. | Sólo configuración interna/investigación; **no opción normal UX/UI**. |
| Backend shell/proceso | Ejecución host con autoridad del usuario, claramente etiquetada. | Adapter Sandboxie Windows y configuración de Nova conocida. **Falta implementar**. | Adapter/instrumentación experimental que pueda satisfacer sus requisitos específicos; ningún backend fuerte seleccionado automáticamente. |
| Tools afectadas | Se debe declarar cobertura FS/host y mantener Policy/Approval/grants aplicables. | Toda shell/proceso agentic, incluyendo shell de subagente, pasa por SandboxPort; read/write/edit/glob/grep conservan S3. Tools sin efecto OS siguen ToolRuntime. | Mismas rutas más requisitos rigurosos por propiedad; operaciones unsupported no se simulan seguras. |
| Garantías requeridas | Ruta explícita, approvals/policy, límites de operación/auditoría honesta; **ninguna promesa OS sandbox**. | Identidad boxed, backend/config conocida, herencia de hijos probada en casos definidos, lifecycle/timeout/cancel, canal/handles controlados, no fallback, audit mínimo. | Perfil fuerte: garantías required ENFORCED, ceiling comprobado, storage/recursos/TCB/evidencia exigida según investigación. |
| Garantías opcionales/no claim | Supervisión host best effort, límites operativos. | G-T/G-H estrictos, proofs exhaustivos, raw monitor, causalidad A/B/C no son gates obligatorios. Riesgos documentados. | Ninguna propiedad required puede sustituirse por un nombre o monitor reactivo; incompleto puede durar indefinidamente. |
| Backend unavailable / versión incompatible | Sólo si este perfil ya fue seleccionado explícitamente puede ejecutarse host. | Error/unsupported/deshabilitar ejecución de proceso; chat/Core y otras capacidades compatibles pueden seguir. **No host fallback**. | NO_EXECUTE/UNKNOWN/UNSUPPORTED según evidencia; nunca pasar automáticamente a Standard/Legacy. |
| Cambio de perfil | Acción explícita de host/usuario; no acto del LLM ni renderer autoridad. | Una operación conserva perfil/binding desde decisión hasta efecto. Cambio requiere nueva decisión/grant. | Cambio sólo interno explícito, grants/cadena/revisión no reutilizables entre perfiles. |
| Auditoría | Indicar host/unisolated y outcome, sin `sandboxed=true` ambiguo. | Backend/versión/box/config-id, operation/grant, identity check, exit/cancel/timeout/cleanup/outcome. | Además raw evidence, token/causal/storage matrices y manifests de experimentación. |
| Subagentes | No aumentan autoridad lógica; host execution conserva riesgo explícito. | Heredan perfil/scopes y ceiling ≤ padre; ninguno puede elegir Legacy ni abrir una box más permisiva por compatibilidad. | Atenuación y requisitos rigurosos del padre, no downgrade por child ni tolerancia al UNKNOWN requerido. |

Sandboxie instalado no debe ser condición de poder usar todo Nova. Si no está presente, Standard no puede ejecutar shell; Legacy requiere selección explícita. No se debe auto-seleccionar Legacy al arrancar o tras un fallo para “mantener compatibilidad”. El Core conversacional no necesita esa dependencia privilegiada.

### 8.1 Decisiones de compatibilidad que V1.1 debe resolver explícitamente

1. **Perfil global frente a subperfil FS.** `BROKERED_FILESYSTEM_S3` protege adapters y tiene requiredGuarantees vacías porque no es process sandbox. Standard debe componer esa protección con proceso Sandboxie, no borrar S3 ni renombrarlo como si fuera global.
2. **AuthorityCeiling lógico frente a alcance práctico de worker.** Grants siguen impidiendo ampliación por API/broker. Un worker general bajo Sandboxie puede usar recursos de runtime/config que no equivalen a cada microgrant. Documentar esa diferencia; no afirmar correspondencia física universal.
3. **Dominancia de perfiles.** La inclusión de requiredGuarantees no describe aún configuraciones y evidencias CONFIGURED/BEST_EFFORT. Definir política explícita de child/profile binding, para que una menor fuerza no autorice Legacy por conjuntos vacíos.
4. **Aprobación ≠ configuración.** Mantener approvals exactas y grant issuer aunque se reduzca la certificación. No extender approval a toda una box persistente sin binding por operación.
5. **Cobertura de host tools.** `web_fetch` hoy ejecuta urllib en el host, incluyendo paths/schemes relevantes; shell Sandboxie no lo protege. No hace falta iniciar S5 para reconocer el hueco: V1.1 debe declarar qué se deniega/deshabilita temporalmente o queda fuera del claim. No anunciar protección general contra exfiltración por prompt injection mientras esas rutas estén libres.
6. **Resultados al proyecto.** La copia Sandboxie de op3 no demuestra un SandboxBroker productivo de importación. Definir cómo Nova acepta/aplica resultados por broker/grant, o si una configuración Standard autoriza escrituras directas particulares y las declara. Una nueva decisión explícita puede reducir el claim, pero no dejar rutas host accidentales.
7. **Versiones y mantenimiento.** Necesaria compatibilidad práctica de versión instalada y condiciones que invaliden el perfil. No es necesario certificar todas las builds/kernel callbacks; tampoco se pueden ignorar degradaciones conocidas que desactiven aislamiento básico.
8. **Dependencia/licencia.** La auditoría Sandboxie/Isolate distingue núcleo/Plus/componentes y certificación comercial. Una futura integración requiere revisión de forma de distribución y configuración gratuita; no hereda autorización jurídica ni exige UseRuleSpecificity por defecto. No se aprobó certificado ni compra.

## 9. Qué debe salir del camino crítico de producto

| Trabajo | Standard | Hardened / preservación |
|---|---|---|
| G-T físico total por tarea | No gate obligatorio de cierre S4 Standard. | Mantener inventario T, B/B2, rutas/residuos y experimentos. |
| G-H estricto/global | No gate obligatorio; declarar riesgo de disponibilidad/recursos. | Mantener gate, admisión/prevención/reacción diferenciadas; no declarar certificado. |
| Cuotas preventivas estrictas de todo storage/RAM/pagefile/servicios | No condición universal; límites operativos y timeout siguen útiles si se describen honestamente. | Investigación pendiente. Monitoring no se convierte en cuota preventiva. |
| Formal host TCB y causalidad de SbieSvc/conhost | No proof formal requerido para producto. Backend instalado sigue siendo confianza/TCB declarado. | `SANDBOXIE_HOST_TCB_EVALUATION=UNKNOWN`, actores host no promovidos. |
| Raw monitor obligatorio | No exigencia del smoke Standard. | `RAW_MONITOR_ACQUISITION=UNKNOWN` y hallazgo de consumo destructivo preservados. |
| Causalidad exhaustiva minifilter / syscall | No gate de reducción práctica de riesgo. | op6 UNKNOWN, AccessCheck/token y F02 permanecen diagnóstico. |
| Snapshots A/B/C y equivalencia temporal | No instrumentación productiva requerida. | BOUNDED_STRONG posible futura, nunca prueba matemática del subject context. |
| Ausencia absoluta de cliente/carreras IPC | No gate universal de preflight Standard. Transporte de producto sí necesita framing/correlación/cierre correctos y tests de fallos definidos. | Observer v1/v2 y acceptance tail UNKNOWN se conservan. |
| Certificación exhaustiva por versión/build/superficie | No promesa productiva. | Matrices y soporte fuerte pendientes por host real. |
| Proof de AuthorityCeiling perfecto / ausencia de todo escape | No claim Standard. | Objetivo Hardened incompleto; no falsear ENFORCED. |

**“Deja de ser requisito productivo” no significa “debe eliminarse”.** Los controladores diagnósticos pueden seguir archivados y bloqueados; sus tests no tienen que ejecutarse en cada build Standard. Conviene separar documentalmente gate release de gate investigador, sin editar resultados ni abandonar checks lógicos de seguridad básicos.

Tampoco hay permiso para eliminar cancelación, deadlines, cierre de procesos, límites razonables de salida, separación de control/secretos, aprobación o no-fallback. La supervisión de recursos continúa siendo operativa y puede clasificarse BEST_EFFORT; no debe describirse como límite físico G-H.

## 10. Gate mínimo propuesto para S4 Standard

**Hoy no puede ejecutarse como gate de producto**, porque falta el adapter/broker de proceso. Es una propuesta de cierre para esa futura implementación, no una solicitud de lanzar el laboratorio actual ni una lista nueva de pruebas de escape.

Precondiciones de release: perfil y backend seleccionados explícitamente por composición host; box/config Nova identificable; SandboxPort real conectado a shell/subagent; ausencia de ruta host alternativa desde ese perfil; audit mínimo; política de aplicación de resultados y env/handles declarada. Un estado UNKNOWN de esas precondiciones detiene la operación. Una propiedad Hardened no requerida no se presenta falsamente como satisfecha.

Se propone **10 casos host-real reproducibles**, con datos artificiales y una instalación aprobada, tras revisión de arquitectura e implementación:

| Caso | Por qué deriva del código actual | Criterio de producto, sin claim fuerte |
|---|---|---|
| STD-01 worker básico | `SandboxPort` es Protocol y shell aún llama Popen host. | ToolRuntime→SandboxPort real; PID/imagen/box/config esperados, API backend confirma worker sandboxed, salida propia conocida y audit correlacionado. |
| STD-02 backend unavailable / identity/config inválida | S3 ya falla cerrado si falta broker; shell aún no tiene ruta semejante. | No crea proceso host ni efecto; error tipado y profile/operation registrados. Sin retry privilegiado ni silent fallback. |
| STD-03 lectura/config externa elegida | op1 positivo y op6 UNKNOWN no acreditan una suite del adapter. | Lectura concedida funciona; objeto externo artificial elegido se bloquea según configuración. Se declara comportamiento observado, **no prueba causal exhaustiva minifilter**. |
| STD-04 escritura/resultado autorizado | op3 probó una copia de laboratorio, no el flujo productivo. | Escritura en superficie declarada, copy/host effect conforme al contrato; aplicación a proyecto sólo por mecanismo autorizado. No exige G-T. |
| STD-05 hijo de intérprete | Shell legacy tiene tree termination best effort; S4 investigó herencia. | Un hijo benigno del intérprete anunciado pertenece a la misma box/config; PowerShell obligatorio en Windows si es ruta soportada. Python/Node sólo si se anuncian/instalan, como variantes del mismo caso, sin excepciones silenciosas. |
| STD-06 timeout | ExecutionContext y shell executor ya tienen deadlines. | Se solicita cierre de la operación/box, se observa root/hijos conocidos y se registra cleanup; si queda vivo o no consultable, outcome/cleanup UNKNOWN/FAILED, no PASS inventado ni siguiente ejecución acumulando autoridad. |
| STD-07 cancel | Application ya coordina cancellation y subagent children. | Cancelación desde Application alcanza backend; terminal único, árbol observado, no un segundo launch/efecto por recuperación. |
| STD-08 stdin/control/handles | Popen actual hereda stdin; prototipo S4 usa NUL/handle-list. | Dummy del canal host no llega al worker; sólo transporte necesario y handles deliberados. No investigación universal de todos los IPC Windows. |
| STD-09 aprobación/grant/subagent | S1/S2/S3 ya tienen bindings y delegación. | Approval requerida no permite launch antes de resolver; request stale/cancel se deniega; child conserva perfil/scopes ≤ padre y no puede seleccionar Legacy por error. Reusar tests offline para combinatoria. |
| STD-10 audit/cierre/limitaciones | Audit backend completo no existe hoy. | Registra backend/versión/box/config-id/operation/grant, exit/outcome y cleanup; fixtures/config intactos según caso, no secretos/control credential. Repetición de suite reproducible sin afirmar ausencia absoluta de residuos. |

Las variantes backend/config/approval negativas combinatorias corresponden a tests offline de adapters, no a decenas de launches de un laboratorio investigador. Puede consolidarse STD-06/07 si el backend comparte código, conservando ambas señales de Application.

`PASS_STANDARD` futuro significaría **validación del contrato productivo y de estos escenarios en el host/versión anunciados**, no NOVA SECURITY V1 STABLE bajo el gate antiguo. `UNKNOWN` requerido bloquea; cleanup incierto no se oculta porque el comando haya devuelto exit0. Debe quedar claro qué proceso/hijos se observaron, no “todos posibles” sin evidencia.

No se requiere raw MonitorGet2, token A/B/C, Watchdog F02 ni resolver el 109 histórico para estas pruebas. Sí se requiere un transporte productivo fiable y correlacionado. Los fixes de reader dedicado, bounds, estados one-shot y DTO JSON-safe son patrones útiles, sin incorporar necesariamente el ABI F02.

## 11. Nomenclatura que V1.1 deberá redefinir

No se cambió ninguno de estos lugares. La revisión futura debe diferenciar contratos, guarantees por perfil y claims. Los términos en evidencias históricas se conservan con su fecha/contexto, no se corrigen retroactivamente.

| Lugar verificable | Término / conflicto | Revisión futura necesaria |
|---|---|---|
| [authority.py:179](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/authority.py:179) | `SandboxGuarantee` mezcla identidad/FS/árbol/red/env/stdin/resources. | Definir qué condiciones son requeridas/opcionales por perfil y cuál es su scope. |
| [authority.py:189](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/authority.py:189) | `ENFORCED / UNSUPPORTED / UNKNOWN / FAILED` | CONFIGURED/BEST_EFFORT no existen. No mapearlos silenciosamente a ENFORCED; decidir relación estado de evidencia vs outcome FAILED. |
| [authority.py:197](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/authority.py:197) | `SecurityProfile.required_guarantees`; `LEGACY_UNISOLATED` especial | Crear significado explícito de los tres perfiles; mantener Legacy sin claims OS. |
| [authority.py:288](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/authority.py:288) y [covers:326](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/authority.py:326) | `GuaranteeEvidence.ENFORCED` y cobertura sólo por ENFORCED | Gate Standard distinto de proofs Hardened; referencia textual no prueba OS. |
| [grants.py:44](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/grants.py:44), [138](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/grants.py:138), [207](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/grants.py:207) | `requiredGuarantees` en digest y relación ceiling/parent | Binding/versionado y orden de fuerza/perfil explícito; no resolver por sets vacíos. |
| [grants.py:261](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/grants.py:261) | `require_attestation` / required ENFORCED | Preservar validación lógica, nueva aceptación según profile contract. |
| [config.py:17](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/config.py:17), [262](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/config.py:262), [filesystem_authority.py:28](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/filesystem_authority.py:28) | `BROKERED_FILESYSTEM_S3 / LEGACY_UNISOLATED` como filesystem_profile | No confundir selector FS existente con perfil global Standard/Legacy. |
| [broker.py:29](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/windows_filesystem_broker.py:29), [94](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/windows_filesystem_broker.py:94) | Perfil sin garantías de proceso; `osProcessSandbox=false` | Conservar declaración precisa. No reemplazar por booleano global “secure”. |
| [session.py:390](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/session.py:390), [ToolRuntime:267](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/tool_runtime.py:267) | `fail-closed` broker unavailable | Sigue válido para esa ruta. No implica que la shell actual falle cerrada como sandboxed. |
| [test_s1_sandbox_contract.py:16](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s1_sandbox_contract.py:16), [104](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s1_sandbox_contract.py:104), [s1_support.py:27](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/s1_support.py:27) | ENFORCED fake, `sandboxed=true` rechazado | Retener como pruebas de contrato. No usar ese booleano ni fake como atestación productiva. |
| [SECURITY §§3–4](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md:30), [§12](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md:194), [§§13–16](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md:220) | Sandbox fuerte, required garantías, ceiling de worker y quotas | Separar objetivo fuerte Hardened del riesgo práctico Standard; mantener autoridad lógica/policy/broker. |
| [SECURITY tabla fases](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md:409), [gate STABLE](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md:420) | `NOVA SECURITY V1 STABLE` / perfil seguro certificado | Definir cierre V1.1 por perfil, sin decir que el gate antiguo se cumplió. |
| [SECURITY ODs](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md:447) | SEC-OD-01 AppContainer selección parcial, SEC-OD-02 plataforma, SEC-OD-08 quotas | Preservar historia, abrir decisión V1.1 sobre backend Standard/gates y scope de OD; no cerrar por nombre Sandboxie. |
| [Core §§19,24,25](C:/Users/joseh/Downloads/nova-local-cli/NOVA_CORE_ARQUITECTURA_V1.md:439) | Puerto de sandbox fuerte / seguridad transversal / extensiones | Revisar referencias al contrato SECURITY sin reescribir lifecycle/AgentLoop. |
| [S0 baseline](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s0_baseline.md), [S1 contratos](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s1_contratos.md), [S1–S3 resultados](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s3_resultados.md:44) | Legacy, fuerte, stable, certified | Entregas históricas con su alcance. Añadir índice de transición/enmienda futura; no borrar advertencias ni resultados. |
| [S4 laboratorio](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_laboratorio.md), [propuesta VM](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_propuesta_windows_sandbox.md), [B/B2](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_especificacion_b2.md:48), [plan Hyper-V](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_plan_validacion_hyperv.md) | G-T/G-H/G-STORE-API, cuotas físicas, ENFORCED | Reclasificar requisitos como Hardened en futuro documento; mantener diagnósticos y provisionalidad B. |
| [Auditoría Sandboxie/Isolate](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_auditoria_sandboxie_isolate.md), [lab Sandboxie](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_laboratorio_sandboxie.md) | “no satisface” el modelo fuerte / free rules / profile estricto | Sigue verdadero para aquel modelo; no concluir que es inviable para el claim reducido por una frase histórica. |
| [Lab manifests/controllers](C:/NovaS4SandboxieLab/free_20260930_f01/controller), [delivery index](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/f02_pipe_v2_review_20261002/delivery_manifest.json) | `executionReady`, `required`, ENFORCED, fail-closed, minifilter, G-T/G-H | Son gates experimentales independientes. No editar para liberar producto ni tratar `executionReady=false` como un flag global de Nova. |

No se encontró un `sandboxed=true` productivo que ateste la shell, ni una definición productiva de los nombres `SANDBOXED_STANDARD` y `HARDENED_EXPERIMENTAL`. Los textos “strong” no relacionados con seguridad, como detección de binario por null bytes en RAG, no necesitan una migración semántica SECURITY.

“Fail-closed razonable” debe significar una acción concreta ante backend/identity/config requerida desconocida: no crear worker, no habilitar efecto o reportar incertidumbre del efecto ya iniciado. No puede significar que cualquier fallo anterior se interpreta como ausencia de efecto. “Cleanup intentado” no equivale a “árbol completamente revocado”.

## 12. Riesgo de estrategias de transición

| Opción | Trabajo que se perdería / regresión | Deuda y coherencia | Coste relativo y recomendación |
|---|---|---|---|
| **A. Rehacer S1→S4 desde cero** | Registro/grants/digest, tests one-shot/attenuation, ApprovalGate/host/TTY, broker handle-based y composición S3 ya probados. Mayor riesgo de reintroducir bypasses de paths/approval/child/cancel. | No hay dependencia real que obligue a ello. Un nuevo diseño tendería a repetir invariantes útiles y retrasar la integración ausente. | **Más alto**, sin beneficio técnico demostrado. No recomendada. |
| **B. Conservar S1–S3, revisar compatibilidad, rehacer contrato/gate S4** | Preserva código/tests; cambios acotados en perfil/digest/dominancia/policy/composición, con regresión focal. | Coherente con puertos existentes y S3 independiente. No debe suponerse que sólo cambiar documentos implemente shell Sandboxie. | **Menor**, recomendado como dirección, sujeto a aprobación de V1.1. |
| **C. B + capa de compatibilidad explícita de perfiles y coverage** | Preserva lo de B; añade mapa de garantías/backend/tool y migración versionada de attestation para evitar mezclar FS subperfil con process perfil. | Es una forma concreta de B para resolver deuda encontrada: requiredGuarantees, factory S3, host tools, child y audit. No otro harness ni Core nuevo. | **Intermedio frente a B documental, muy inferior a A**. Recomendación técnica para ejecutar B sin inconsistencias. |

No se ofrecen horas: el coste relativo deriva del volumen de código probado que A descartaría y de que el mayor trabajo pendiente, el adapter/broker de proceso, existe igual bajo cualquier estrategia.

La pausa de Hardened no elimina su deuda; la hace explícita y fuera del camino crítico. Standard todavía tiene deuda productiva independiente: mapping de scopes/config, child/lifecycle, canal/handles, resultado→proyecto, auditoría y coverage de tools host. Esa deuda no se resuelve eligiendo una etiqueta menos fuerte.

## 13. Perspectiva del proyecto después de aprobar V1.1

| Área | Estado actual verificable | Estado conceptual bajo V1.1 | Acción |
|---|---|---|---|
| Core | Implementación local Windows validada; gate global otras plataformas pendiente | Conservado | Mantener contratos/API/lifecycle; regression guard, no reescritura. |
| S0 | Baseline/threat model/test characterization validados | Base histórica reutilizada | Nuevo release pin sin borrar S0. |
| S1 | Contratos/issuer/bindings/attenuation validados | Reutilizados con profile compatibility menor | Precisar strength vs logical authority/digest. |
| S2 | Actor/binding/decisiones validados; rules legacy parciales | Reutilizado | Policy composition y grant de proceso; preservar aprobación. |
| S3 | Cinco adapters Windows brokered validados | Conservado, separado de shell profile | Factory injection menor, claims exactos, ampliar sólo requisitos elegidos. |
| S4 Standard | Backend productivo no implementado | Nuevo gate práctico por perfil | Completar conexión SandboxPort/broker/adapter y 10 smokes propuestos. |
| S4 Hardened | Investigación extensa; gates sin certificar | Interno, no UI normal, pausado | Archivar/indexar F01/F02/G-T/G-H/TCB; no reanudar automáticamente. |
| S5 | Nueva fase no iniciada; web_fetch legacy con riesgos | Sigue pendiente | Declarar coverage/unsupported mientras se decide network; no implementado aquí. |
| S6 | Saneamiento legacy parcial; worker allowlist experimental | Sigue pendiente | Diseño/validación posterior de env/secrets; Standard básico no debe entregar deliberadamente credenciales/control. |
| S7 | Logs y events existentes, SecurityAudit incompleto | Sigue pendiente en versión completa | Audit básico S4 no sustituye durabilidad/retención/redacción S7. |
| S8 | No gate integrado SECURITY completo | Release gate por claims/perfil/plataforma | Reutilizar tests existentes y separar smoke Standard de adversarial Hardened. |
| Memory | No Long-Term/Personal Memory en este Core; transcript/context no son memory | No cambia por revisión SECURITY | Trabajo posterior; estado de planes externos UNKNOWN. |
| Knowledge Inputs | KnowledgeStore y RAG existentes; ingestion general adjuntos/PDF/visión no implementada como extensión V1 | Preservar servicios; futura ampliación separada | No confundir store/skills/RAG con pipeline de inputs ya terminado. |
| Active Web | WebFetchTool y monitor legado; no browser/search agentic avanzado implementado | Roadmap separado | No asumir que la sandbox shell protege fetch host; límites declarados. |
| Desktop | Cliente React/Electron/Application y actor aprobación existentes | Conservado; perfiles futuros sin implementar UI | No tocar GUI ahora; Hardened no opción normal futura. |
| Voice | STT/TTS/voice adapter no implementados en el repositorio Core auditado | Extensión futura fuera de esta tarea | Otro directorio/proyecto no prueba integración; usar Application API cuando corresponda. |

Referencias de alcance futuro: [Core §1](C:/Users/joseh/Downloads/nova-local-cli/NOVA_CORE_ARQUITECTURA_V1.md:17), [§25](C:/Users/joseh/Downloads/nova-local-cli/NOVA_CORE_ARQUITECTURA_V1.md:528) y [persistencia≠memory](C:/Users/joseh/Downloads/nova-local-cli/NOVA_CORE_ARQUITECTURA_V1.md:489). No se infirió un orden de desarrollo Memory/Knowledge/Web/Voice no documentado.

## 14. Preservación y handoff material

### 14.1 Qué consultar primero al retomar

1. Arquitectura [Core V1](C:/Users/joseh/Downloads/nova-local-cli/NOVA_CORE_ARQUITECTURA_V1.md) y [SECURITY V1 vigente](C:/Users/joseh/Downloads/nova-local-cli/NOVA_SECURITY_ARQUITECTURA_V1.md), distinguiendo objetivo de código.
2. [S1 contratos](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s1_contratos.md), [S2 resultados](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s2_resultados.md), [S3 resultados](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s3_resultados.md) junto con fuentes citadas, no sólo sus diagramas.
3. [S4 laboratorio general](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_laboratorio.md), [auditoría OpenCode/OI](C:/Users/joseh/Downloads/auditoria_comparativa_seguridad_opencode_openinterpreter.md), [Sandboxie/Isolate](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_auditoria_sandboxie_isolate.md), [B2](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_especificacion_b2.md).
4. [Auditoría tokens op6](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_auditoria_token_op6_offline_20261001.md), [op3 PASS](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_one_op3_ejecucion_7a64df79_20261001.md), [observer v2 offline](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_f02_r0_pipe_observer_v2_offline_20261002.md) y [delivery index](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/f02_pipe_v2_review_20261002/delivery_manifest.json).
5. [Continuidad anterior](C:/Users/joseh/Downloads/informe_continuidad_nova_security_s4_sandboxie_2026-10-02.md) como orientación histórica, contrastándola con código/manifest. No usar su representación conceptual como prueba de adapter productivo.

### 14.2 Estado material de fixtures y manifests

Los cinco objetos del baseline artificial conservan sus hashes. El quinto es `granted_read\probe.ps1`, no un canario en staging; staging host no contiene el archivo creado por op3.

| Objeto de laboratorio | Bytes | SHA-256 verificado en lectura |
|---|---:|---|
| `granted_read\canary.txt` | 53 | `1C4BA3162B82CE3564D799C5C3144CB0A54DFC1EEE03CAD06141E50828896ABD` |
| `granted_read\probe.ps1` | 249 | `B5CA106DD8E5625E80EB5CD1B751FCCD0BF6BD624528E0595B4CF2759FEE679C` |
| `outside_normal\canary.txt` | 55 | `555CE4B379DB76EF0E0B718C3B49523C9ECB1B117182025FDE7BAB2612DA30AE` |
| `outside_permissive\canary.txt` | 59 | `B16C67A04DE5DE6AFE123D02971BCC77B1E84AB991C4FEC70BC67738DD2838C6` |
| `outside_permissive\dir\canary.txt` | 69 | `255F2F073A1D8D7E3741F638BE33B8CE565AB235BE23A80AC72F7C0A6ADED2CC` |
| Copia op3, [objeto preservado](C:/NovaS4SandboxieLab/free_20260930_f01/box/drive/C/NovaS4SandboxieLab/free_20260930_f01/staging/probe_20261001_a1.txt) | 14 | `FD396CA73B61969076D7FE7386CA129A6C2081DB66A34EF6E55F664E56D69E1B` |

Identidad op3 histórica: `7E23ED4B:00140000000E757E`. Identidad outside_permissive histórica: `7E23ED4B:0016000000074770`. No se ha realizado una nueva operación del probe para comprobarlas. Las mediciones de objeto mediante handle de los expedientes siguen siendo históricas; el hash read-only actual no sustituye sus timings/identidad ni re-certifica aquella operación.

RegHive se mantiene como evidencia T. Último baseline archivado: 16384 bytes, SHA-256 `2917BAC6D16F18E325AA02C74CA409784BEB002DEDADC4D74746C86DC4591CDC`. No se borró, desmontó ni modificó. No se ejecutó un inventario experimental nuevo ni se acredita G-T.

El rebaseline Sandboxie.ini conserva:

~~~text
old = 2437806B7BF3BA03AE7C8C19E2EE313C7935BE650DB1D5C541EE65C1C1E491C2
new = BE5EA0B65F42C630050A05E225CE5EAB25AFDCF8CEF634979009F2508522742C
BYTE_HASH_DRIFT=true
classification=SEMANTIC_NONSECURITY_DRIFT
EFFECTIVE_PROFILE_DRIFT=false (comparación aprobada de aquel rebaseline)
writerActor=UNKNOWN
~~~

[Informe de drift](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_drift_sandboxie_ini_20261001.md) y [rebaseline v2](C:/NovaS4SandboxieLab/free_20260930_f01/evidence/informe_rebaseline_one_op3_v2_20261001.md) conservan diff/procedencia. El hash actual coincide con “new”; eso no equivale a ejecutar ahora un nuevo gate expandido de Sandboxie. No se ha vuelto a consultar perfil live ni aceptado un baseline diferente.

Pins para distinguir versiones históricas/offline:

| Artefacto | SHA-256 |
|---|---|
| Observer v1 histórico | `0066AA89997412C52A7EE71BE5A012D09E4E6E96AC58F4709AC172EF72B8E736` |
| Observer v2 offline | `C45F5C3CC578F2C083FA097D898F2FD6FE5073E2BB9009626A92A8FC003DE04A` |
| Runner R0 v4 histórico | `96289A2EC25AB3D165D8B47BD92E9CD6425163D20925A856E30286821AE3D085` |
| Runner R0 v5 bloqueado | `08DDAE30647D97E0BCB5391CA63FE7CC3CCE2CD9691D7484C12326A55FE41056` |
| Manifest R0 v10 histórico | `9E7614DC7F1B76C93A3AAA36A8BAD3DDB1FB3881F6007EA2E54D02E77FA2A3B6` |
| Manifest R0 v11 offline | `C0D9C2E437C899C45F46FB6BDDB774C6310A60055F323FF6CD370D9737DF4901` |
| Probe F02 v2 anterior/no elegible | `090A0CD41F7E9D700F493E16582E5A40FE2A9E11533FCE9B890D72AA573B3908` |
| Probe F02 v3 | `F4B1E293B871D23BE4741CE48E78837CB99548543F5401D6B535E183FF3E3BF9` |
| Delivery manifest | `A8DF75EA108D78D1DF51ACCCCA54D022F7DC3676CF0B09A79AE09C19FC54EF38` |

Ninguno de esos hashes habilita ejecución. Los paquetes declaran `executionReady=false`, y v11 además bloqueo runtime. El cambio de producto no debe usarse como atajo para un nuevo attempt Hardened.

### 14.3 Riesgos de continuidad

- SECURITY y tests están en archivos modificados/untracked: copiar sólo HEAD **perdería implementación S1–S3 y documentos S4**. Un futuro arquitecto necesita este working tree completo y el laboratorio externo, no sólo el tag Core.
- Arquitecturas y auditorías clave están fuera de Git root; sus paths absolutos pueden romperse al mover el proyecto. Preservarlas con sus hashes/procedencia sin normalizar sus contenidos históricos.
- La gran cantidad de artefactos de prueba incluye versiones sucesivas y outputs sintéticos. Elegibilidad depende de manifest/estado, no del archivo con nombre más reciente o un PASS aislado.
- La entrega v11 inventaría un subconjunto de la raíz lab; no garantiza backup completo de los 5384 archivos. Este informe no movió ni creó un backup.
- No convertir de forma retroactiva pruebas complejas fallidas en “innecesarias, por tanto PASS”. Pueden dejar de bloquear Standard y conservar UNKNOWN en Hardened.
- S3 y approvals son enforcement lógico/concreto útil, pero no hacen segura toda tool host ni todas las superficies del usuario. Los claims deben tener coverage por tool/backend.
- La implementación Standard podrá ser más pequeña que F02; debe evitar heredar sus fixtures, protocol IDs y rutas absolutas como configuración productiva.
- Packaging, instalación de driver, derechos administrativos, actualización y licencias siguen decisiones de distribución. Ninguna fue autorizada por esta auditoría.

## 15. Anexo de estado exacto del working tree

Estado previo a este informe: 24 tracked modificados, 49 untracked, ningún borrado registrado. El diff tracked es 403 inserciones/128 eliminaciones; no incluye contenido de archivos nuevos. Las siguientes rutas son las entradas exactas de Git, expandidas a la raíz actual.


~~~text
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/electron/application_client.ts
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/electron/main.ts
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/src/App.tsx
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/tests/application_client.test.cjs
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/__main__.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/interactions.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/session.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/tool_runtime.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/bootstrap_cli.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/bootstrap_server.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/cli.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/config.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/interfaces/cli_application.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/interfaces/jsonl_application.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/server.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/sub_agent.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/tools/agent_tool.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/test_main.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/test_nova_core_phase11_adapter.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/test_nova_core_phase14_platform.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/test_nova_core_phase3_cwd.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/test_nova_core_phase7_server_legacy.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/test_nova_core_phase7_session.py
 M  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/test_security_gates.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/electron/host_approval.ts
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/electron/ipc_origin.ts
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s0_baseline.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s0_manifest.json
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s0_resultados.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s1_contratos.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s1_resultados.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s2_resultados.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s3_resultados.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_auditoria_sandboxie_isolate.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_decision_almacenamiento.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_especificacion_b2.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_laboratorio.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_laboratorio_sandboxie.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_plan_validacion_hyperv.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/docs/nova_security_s4_propuesta_windows_sandbox.md
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/filesystem_authority.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/grants.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/policy_engine.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/authority.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/windows_filesystem_broker.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/windows_fs_handles.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/__init__.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/conftest.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/run_s0.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/run_s1.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/s1_support.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/s4_windows_lab.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s0_approvals.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s0_authority.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s0_source_evidence.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s0_windows_host.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s1_authority_contracts.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s1_grants.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s1_legacy_characterization.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s1_sandbox_contract.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s2_approval_grant_binding.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s2_cli_approval.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s2_host_approval.mjs
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s2_ipc_origin.mjs
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s2_ipc_source.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s2_jsonl_approval_channel.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s2_policy_characterization.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s2_policy_engine.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s3_composition.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s3_legacy_filesystem.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s3_windows_broker.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s4_prototypes.py
??  C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/tests/security/test_s4_restricting_tokens.py
~~~

### Pins de código SECURITY/producto del working tree

Estos hashes fijan lo inspeccionado; no son un manifest de ejecución ni un release certificado.

| Archivo | SHA-256 |
|---|---|
| [desktop/electron/host_approval.ts](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/electron/host_approval.ts) | `8B908699707FF326A85A9474C68F3ADAC0EE55468C04256513E508CEE3AF32CF` |
| [desktop/electron/ipc_origin.ts](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/electron/ipc_origin.ts) | `A3FA087A8F966344C1D1DB23EC2FB32D073CE9B858C4FC4108E1C9A1CC44D989` |
| [local_cli/application/filesystem_authority.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/filesystem_authority.py) | `E76F39582EC9C0D55321864529FD46625AE31E161E2A1F42E5534C55D70BEA7E` |
| [local_cli/application/grants.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/grants.py) | `EB9AC370F77766013C2A7F6A9A8A09E791ADC7158924BA14698BC4A9F4F15617` |
| [local_cli/application/policy_engine.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/policy_engine.py) | `841CAA3677845D8D1657FB82DBE1BF23CE5E21D0913997927EDEF8F3330DA58F` |
| [local_cli/core/authority.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/core/authority.py) | `3E9995312F47EF8ED5F2365D75D20A3D7135BB6E23A8AAB0B4FA4897E092DC9B` |
| [local_cli/infrastructure/windows_filesystem_broker.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/windows_filesystem_broker.py) | `6DD42706522574B26DE92E92B1222CFBF9BEDA7CFFD79A7CA2F5063B354CA483` |
| [local_cli/infrastructure/windows_fs_handles.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/infrastructure/windows_fs_handles.py) | `0B397995A7E6A534E69FEEA4508DB033C49B0FF2E82107F9ABFEF61F139698F6` |
| [desktop/electron/application_client.ts](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/electron/application_client.ts) | `EDAFB4E67CA3DAD832B1B12815735555027589541D8493BEB8AE764727DF51CD` |
| [desktop/electron/main.ts](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/electron/main.ts) | `213D661AEC884F8FB36326F19B0B342B5E984869352CB8660581BE0CEDA60A67` |
| [desktop/src/App.tsx](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/desktop/src/App.tsx) | `69058480A454C1887D9E6EAC9ACCF7384855A204913A56A0D46765063E8123BE` |
| [local_cli/__main__.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/__main__.py) | `062DD41B5AF2FAA212FB90FA854AB5F5B871004002C755A1601FEE097C3BDCBE` |
| [local_cli/application/interactions.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/interactions.py) | `95AD918A1231882C6FCF0514C5ECA69AE63542A3EFF6CDDBAD3AEDA18EEC2005` |
| [local_cli/application/session.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/session.py) | `709123B2EB0DFDADDB0267159665BF4903FE78D4FE15E336EBD7AE107775F31E` |
| [local_cli/application/tool_runtime.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/application/tool_runtime.py) | `3CD05956BDF8FCFD88624DE5FB2B63A2B82CE478BE82EB660F5EDACF66EC7F0D` |
| [local_cli/bootstrap_cli.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/bootstrap_cli.py) | `D371E7EA969E7EBBF7A5E2F4872D3B8BAFF0EBE145EA11E561C4067E548BC8AD` |
| [local_cli/bootstrap_server.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/bootstrap_server.py) | `78EA3058D6ABD32668FF90A61D8E1C209ACA108FBCECFFE16B25CB8EAA31E3B4` |
| [local_cli/cli.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/cli.py) | `4F3AAC4DCDEBEDDD0983A7E00333FA2AE54C05AF4D8C4A0D8C470D483DD7953D` |
| [local_cli/config.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/config.py) | `2E8579FB8E51BD7ED6698842885B8FFFFE6BFFF1FE65F3EF1ECE65E84C84AACB` |
| [local_cli/interfaces/cli_application.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/interfaces/cli_application.py) | `0AC5FAA7BD24D7BD16F8BE2411111E90B157F957BF1F2471FCE91B1F3DC54029` |
| [local_cli/interfaces/jsonl_application.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/interfaces/jsonl_application.py) | `73A7B5FA90B378ABE2371FDB8F969D8218DFBCADD3E45E545D8E59473E482A97` |
| [local_cli/server.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/server.py) | `1F1FE2F7F16DAC48C47B3F624AB9AAD2AA22BFC7937B7DFAA345196075DD0CFE` |
| [local_cli/sub_agent.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/sub_agent.py) | `C31C1026B363D459CB448312A95A66A6BAB4178C4070F57A4717A7AB379FB331` |
| [local_cli/tools/agent_tool.py](C:/Users/joseh/Downloads/nova-local-cli/local-cli-main/local_cli/tools/agent_tool.py) | `CC8FCCD8C179BC3F4C17BD63B923BFA2FF4AFC23B0834101020F81B4D7307157` |

## 16. Comprobaciones de entrega y límites del informe

La auditoría no reejecutó toda la matriz ni interpretó de nuevo cada evento de las miles de capturas. Consolidó el inventario completo disponible, contrastó componentes y resultados principales con código/expedientes, verificó el inventario hash de la última entrega y preservó explícitamente huecos/UNKNOWN. No se afirma una nueva certificación host-real por leer esos archivos.

En particular, el JSON bruto op1 todavía contiene `focalOperations=0`, aunque operaciones y RESULT muestran op1. El derivado v2 corrige la contabilidad sin sobrescribirlo. El JSON bruto op6 conserva el outcome/contabilidad escritos por el runner antiguo; la clasificación revisada congelada **UNKNOWN** se toma de su revisión posterior y de la instrucción explícita del usuario. No se edita el bruto para hacerlo coincidir con ella.

La comprobación de integridad final de esta entrega se registra como **PASS: los 333 archivos previos del checkout conservan sus hashes; los 1437 archivos y 15 shards del inventario experimental verificado no presentan diferencias; canarios/copia op3 y pins de configuración coinciden. El único cambio de esta entrega es este informe nuevo**. Los tests de esta tarea sólo ejecutaron los contratos/units descritos en §2.2; no tocaron los attempts, configuración, canarios ni copia op3.

Estados preservados:

~~~text
SANDBOXIE_HOST_TCB_EVALUATION=UNKNOWN
RAW_MONITOR_ACQUISITION=UNKNOWN
SEC-OD-01=OPEN
SECURITY S4=NOT_CERTIFIED
G-T=NOT_CERTIFIED
G-H=NOT_CERTIFIED

F02/R0 package executionReady=false
F02_R0_PROTOCOL_RESULT=NOT_EXECUTED
TOKEN_TEMPORAL_EVIDENCE=NOT_OBSERVED (F02 real)
~~~

V1.1 puede cambiar el criterio productivo futuro; este informe **no cambia esos estados históricos ni habilita ejecución**.

## A. QUÉ YA TENEMOS

Tenemos Core por puertos y Application compartida; ToolRuntime, contratos Permission/Capability/ResourceScope/Ceiling/Grant, GrantIssuer con bindings y atenuación, PolicyEngineV2 estructurado, ApprovalGate one-shot, actor Electron host/CLI TTY, cinco adapters FS integrados y broker Windows de objetos/handles. Hay tests de contrato, composición, negativas y un alcance S3 host-real documentado. Son componentes reutilizables, con los límites identificados.

No tenemos todavía la shell Standard Sandboxie: el producto sigue ejecutando procesos por la ruta legacy. SandboxPort existe como contrato; SandboxBroker/adapter de proceso y audit de backend todavía faltan.

## B. QUÉ ESTÁ SÓLO INVESTIGADO

AppContainer/LPAC/Restricted/Jobs, Windows Sandbox/Hyper-V/B2, comparación OpenCode/Open Interpreter y Sandboxie/Isolate; F01/R1–R4/transportes, op1/op3/host control/op6; token attestation v2, F02 A/B/C/decoder, R0/R1, JSON-safe/watchdog y observers de pipe; G-T/G-H, raw monitor y host TCB.

Los PASS op1/op3 prueban sus operaciones de fixture y configuración, no el backend de Nova. Op6 sigue READ_DENIED con comportamiento/causalidad UNKNOWN. F02 no tiene ejecución causal ni R0/R1 live validada. El último preflight consumido y el 109 conservan UNKNOWN; observer v2 no resuelve la acceptance tail. Esta línea debe preservarse como HARDENED_EXPERIMENTAL, no liberarse para producto por reducir el claim.

## C. QUÉ DEBEMOS CAMBIAR PARA SECURITY V1.1

Tras aprobar una enmienda arquitectónica:

1. Definir los tres perfiles, selección explícita y cobertura real por tool/backend; Hardened sólo interno.
2. Separar autoridad lógica de fuerza/evidencia del backend, precisar ENFORCED/CONFIGURED/BEST_EFFORT/UNSUPPORTED/UNKNOWN y requisitos que detienen Standard.
3. Revisar `requiredGuarantees`, digest y dominancia/atenuación entre perfiles con versionado y tests; mantener grants/approvals inmutables y exactos.
4. Revisar sólo el contrato S4 necesario para integración de shell/subagentes, lifecycle/timeout/cancel, stdin/handles, no-fallback y audit mínimo.
5. Precisar mapping gratuito/config de Sandboxie, resultados→broker/proyecto, responsabilidades privilegiadas/licencia/distribución y rutas host que quedan fuera del claim.
6. Separar gate productivo Standard de investigación Hardened: G-T/G-H y proofs exhaustivos dejan de ser requisitos Standard, sin borrar evidencias.
7. Limitar la corrección de dependencias S3 a composición/factory si se adopta; no mover decisiones al renderer ni duplicar el harness.

Ninguno de esos cambios se ha implementado ni aplicado a la arquitectura canónica en esta tarea.

## D. QUÉ NO HAY QUE REPETIR

No rehacer baseline/threat model S0, álgebra/issuer/binding S1, ApprovalGate/actor/CLI/IPC S2, ni broker handle-based/adapters S3. No repetir op1, op3, host control ALLOW, bisección R1–R4 o reproducciones STOP-only cerradas para obtener otro PASS. No reabrir AppContainer/LPAC/Restricted/VM porque otra herramienta use la misma tecnología.

No exigir al camino Standard resolver raw monitor, formal TCB, cuota total G-T/G-H, causalidad minifilter, A/B/C o ausencia universal de clientes del observer diagnóstico. Conservarlos como trabajo pendiente Hardened. Los tests de producto que se añadan para un adapter nuevo serán validación de integración nueva, no reinterpretación de aquellos experimentos.

## E. PUNTO EXACTO DE REANUDACIÓN

**Antes de desarrollar:** revisar/aprobar Arquitectura SECURITY V1.1 a partir de este informe, con matriz de perfiles/claims/requisitos, ratificación normativa de la dirección Sandboxie para Standard y decisión explícita sobre coverage. El documento vigente no queda sustituido por esta entrega.

**Después de aprobarla:** retomar **S4 arquitectura/producto, subfase de contrato/composición de proceso Standard**, no S1 y no el preflight Hardened. Primero resolver profile compatibility/digest y el enlace `ToolRuntime → SandboxPort → SandboxBroker/adapter`, conservando S3 y approvals. Luego implementar la mínima integración de backend/lifecycle/canales/audit permitida por esa arquitectura y validar una suite host-real de producto pequeña como §10, con autorización propia para acciones sobre el host.

**Hardened queda detenido** en R0 v11/observer v2 offline, `executionReady=false`, acceptance tail sin resolver y attempts UNKNOWN inmutables. No hay autorización implícita para otro preflight, R0/R1/F02, ARM/EXEC/GO o control host.

S5, GUI, los tres perfiles en código, modificaciones de Sandboxie, commit y push quedan fuera de esta entrega. La siguiente fase no se implementó.

