# NOVA SECURITY V1.2 — cierre READY

`NOVA_SECURITY_V1_2_READY = true`

**Resultado: PASS de los 20 criterios de SECURITY V1.2 §30**, revisados uno por
uno contra la evidencia final S0–S8 y el código fijado por sus hashes.
Evaluación autorizada expresamente por el usuario el 2026-10-04.
Fecha UTC de la revisión: 2026-10-05T03:45:38.1950601Z.

Este es un **gate de calidad de producto**, no una certificación externa de
seguridad ni una declaración universal de que Nova sea segura.

## Alcance exacto

**Windows 11 + NTFS local + HOST_UNISOLATED.**

- No existe sandbox ni process isolation. Shell y sus descendientes usan los
  permisos normales de la cuenta y pueden acceder a recursos que esa cuenta
  permite; cwd, policy, approval y grants no son barreras físicas.
- S3 conserva el claim BROKER_ENFORCED sólo para read/write/edit/glob/grep sobre
  las superficies soportadas de NTFS local. No media las syscalls de shell.
  UNC/ADS, volúmenes no NTFS y traversal reparse/alias especiales no soportados
  permanecen fail-closed; no se añade soporte mediante esta declaración.
- web_fetch media su cliente HTTP(S) PUBLIC_ONLY, cada DNS/redirect y sus límites.
  Red shell/Git y red provider/Ollama son autoridad host separada, no firewall.
- Control de procesos/Job Objects y cleanup de árbol son lifecycle BEST_EFFORT,
  no aislamiento, cuotas preventivas OS ni prueba universal de ausencia de hijos.
- **Linux y macOS: no certificados.** Unit/contratos POSIX no equivalen a host-real
  de esas plataformas. No se declara un READY Core multiplataforma.
- El alcance es el checkout evaluado, branch main, HEAD
  `158b60effa484cd34a58b991f3ee4ca3f808d924`, **con cambios locales sin commit** fijados en el manifest.
  El commit por sí solo no identifica la implementación SECURITY evaluada.

## Revisión individual del gate §30

| Nº | Criterio normativo | Resultado | Respaldo final |
|---|---|---|---|
| 1 | S0–S8 requeridos están cerrados. | PASS | Cierres y corridas finales S0–S8; S8: 28/28 familias PASS |
| 2 | Toda tool agentic pasa por ToolRuntime. | PASS | S2 runtime; S4 backend y ambos caminos nativos de hijos |
| 3 | Permission/Capability/Grant bindings están implementados. | PASS | S1 contracts/issuer repetidos en regresión S8 |
| 4 | approvals son exactas/one-shot. | PASS | S2 approval/runtime; S1 one-shot; Node host approval (10 PASS) |
| 5 | renderer no emite autoridad. | PASS | S2 contratos host; spoof JSONL nativo S8; Node approval |
| 6 | S3 brokered FS pasa pruebas host-real para las superficies anunciadas. | PASS | S3 Windows nativo (25 PASS), incluidos ambos symlinks |
| 7 | S4 `HOST_UNISOLATED` cumple lifecycle/canales/output/audit sin claims de aislamiento. | PASS | S4 procesos nativos (29 PASS); S7 durable/runtime |
| 8 | S5 `web_fetch` cumple su contrato mediado. | PASS | S5 contracts/runtime y HTTP/TLS/DNS nativos (28 PASS) |
| 9 | Shell network está documentado como host authority. | PASS | s8_limits.md; contratos de claims y frontera shell/S3 |
| 10 | S6 evita herencia deliberada de secretos Nova. | PASS | S6 environment/redacción/runtime; root/child nativos (4 PASS) |
| 11 | S7 conserva provenance y outcomes honestos. | PASS | S7: DTO, runtime, JSONL/crash nativo; segmento real S8 |
| 12 | subagentes no amplían autoridad lógica. | PASS | S1/S2 attenuation y linaje; S7 sujeto; S4 hijo nativo |
| 13 | `outcome_unknown` no se transforma en éxito/denied inocuo. | PASS | S4 unknown nativo; S7 durable/post-effect/crash |
| 14 | no hay retry automático de efectos inciertos. | PASS | S8 replay adversarial; S4 timeout; S7 fallos audit |
| 15 | CLI/Desktop comparten Application backend. | PASS | CLI/Ollama y Electron/backend reales; composiciones S7 |
| 16 | Ollama/local-first sigue operativo. | PASS | E2E local multi-tool causal, CLI y Desktop Ollama reales |
| 17 | el producto no necesita infraestructura externa de sandbox/contenedor/VM. | PASS | AST contratos/imports; inventario/claims S8 |
| 18 | la documentación/UX puede explicar que los procesos usan permisos normales del usuario. | PASS | Texto CLI/Desktop y límites publicados, comprobados por contract |
| 19 | regresión Core relevante pasa. | PASS | Regresión Core actual 694+10; 4 nativos; Node/tsc/build |
| 20 | las claims se publican por superficie, no como “Nova es segura/sandboxed” de forma global. | PASS | s8_limits.md: claims por superficie + contracts |

Criterios no respaldados o incumplidos: **ninguno**.
Los nueve manifests de fase están en PASS y sus corridas finales terminan
correctamente. Los XML históricos canónicos S0–S7 no presentan failures/errors;
sus skips originales conservan su significado y no se presentan como pruebas
nativas ejecutadas. La evidencia actual requerida S8 no tiene failures/errors.

El manifest READY contiene por criterio los archivos/JUnit/casos concretos,
análisis y límites de la evidencia. Se comprobaron los **677 pins** finales S8,
sin drift. La revisión inicial conserva hashes de **1326
archivos preexistentes** de código/contratos/tests/documentación/evidencia.
No se utiliza sólo el conteo de tests o un PASS del runner para inferir READY.

## Evidencia final que gobierna esta evaluación

- S8 regresión: **1.309 pruebas Python PASS + 10 subtests**, **28 Node PASS**,
  tsc y build PASS. Core relevante: 694 pruebas + 10 subtests; cuatro Core
  nativas PASS. No se suman otra vez baselines/repeticiones como casos únicos.
- S8 host-real manual: **93 PASS**, incluidos **25 S3** con file_symlink y
  directory_symlink creados realmente, sin skip, y ejecución del broker real.
  Fuente fijada y asserts que fallan si os.symlink no completa; fixtures ya
  limpiadas, no inspección de links inexistentes posterior al cleanup.
- S8 E2E definitivo: **5 PASS**. Multi-tool/Ollama, CLI/Ollama y Desktop/Ollama
  son inferencias locales reales. Spoof JSONL y Desktop lifecycle usan inferencia
  scripted **en casos separados**, declarados así; no sustituyen el multi-tool.
- Ollama qwen2.5:7b instalado: digest
  `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`.
  Backend normal, misma AgentSession, dos SubmitUserInput, cinco Generations.
  Read real en request 1 → ToolResult real en input request 4 → write exactamente
  ese contenido → read final real recibido en request 5. Archivo byte-identical,
  afterHash del broker coincidente y tres terminales/audit durable, sin gap.
- Un smoke Core legacy opt-in permanece skipped y tres pruebas GPU quedaron
  excluidas por instrucción previa del usuario. No son una evidencia positiva:
  el requisito local efectivo se respalda por el E2E real causal anterior.
- Approval positiva en varias suites usa actor humano/diálogo simulado.
  Node verifica el protocolo/correlación y el backend JSONL real rechaza spoof;
  no se afirma una certificación independiente del humano pulsando el diálogo.
- HTTP/TLS/DNS nativos usan fixtures locales; admisión/resolver de fixture cuando
  se declara. No se afirma una validación nativa de Internet público arbitrario.
- S7 comprueba JSONL/locks/fsync/retención/crash-reopen reales sobre estado privado
  y mantiene gaps/outcomes honestos. No audit tamper-proof, efectos internos
  universales del shell ni protección absoluta contra pérdida eléctrica.
- Redacción sólo de secretos conocidos; un pass explícito al root puede llegar a
  hijos OS. No detección universal de secretos en disco ni herencia impedida OS.

Rutas definitivas: `s8_evidence/closure_regression`,
`s8_evidence/after_symlink_permission`, `s8_evidence/closure_final_e2e`.
Cierres originales S0–S7 y sus corridas respectivas quedan fijados en el manifest.
Límites por superficie existentes: [s8_limits.md](s8_limits.md).

## Fallos históricos y limitación del modelo: conservados, no reinterpretados

El caso **single-Turn de qwen2.5:7b sigue siendo FAIL / MODEL_BEHAVIOR**.
En `s8_evidence/final_e2e` quedó 4 PASS/1 FAIL: el modelo emitió read/write/read
juntos y el write con `read(result.txt)` antes de recibir el primer ToolResult.
El resultado correcto llegó a la inferencia siguiente; no se encontró pérdida de
ToolResults en AgentLoop/provider/harness. La repetición diagnóstica original
`closure_diagnostic_original` también sigue FAIL, con otro contenido inventado.

Es una **limitación no bloqueante** de este READY acotado, conforme al alcance
autorizado: Core §§6/7/27 y SECURITY §30.16 no exigen copia dependiente en una
inferencia ni en un único Turn. El test antiguo tampoco exigía inferencia única;
sí agregaba un Turn. El E2E sustituto conserva modelo/efectos/ToolResults reales,
dependencia comprobada entre inferencias, verificación final exacta y audit.
No se declara éxito del prompt original ni alineamiento universal/determinista
del modelo; no se modifica producto para corregir batching o relatos falsos.

Las evidencias WinError 1314 de S3/S8 permanecen con sus fallos de creación.
Los cierres manuales exitosos son corridas **nuevas**, no ediciones de esos fallos.
S0 caracterizó límites del Core de entonces; no se reescribe como enforcement
que aún no existía. Manifests/reportes anteriores que dicen READY=false siguen
intactos como registros del momento en que faltaba evaluación o autorización.
**Este cierre y su manifest son la declaración posterior autorizada.**

## Cambios, verificación y decisiones

Sólo se crean este documento y [nova_security_v12_ready_manifest.json](nova_security_v12_ready_manifest.json).
**Cero cambios a funcionalidad, configuración, tests, normas o evidencia anterior.**
Sin nuevas ejecuciones funcionales: se revisaron logs/XML/JSON/hashes existentes.
No GPU probes/tuning, inferencia nueva, cloud, instalación, packaging, commit ni push.

SEC12-OD-01..05 conservan sus decisiones humanas. SEC12-OD-06 (Git dedicado futuro)
y SEC12-OD-07 (feature administrativa futura) permanecen fuera de alcance:
no se resuelven aquí ni se habilita elevación. No hay OPEN DECISION bloqueante
de §30 para el producto/alcance evaluado.

Limitaciones no bloqueantes adicionales preservadas: workspace/authority rebinding
fuera de las transiciones certificadas, perfiles/toolchains accesibles por permisos
de cuenta, ventana de asignación Job y cleanup de dimensiones observadas.
Una nueva superficie/tool, cambio de fuentes/política o plataforma necesita su
revisión correspondiente; este READY no certifica futuras modificaciones.
