# Cierre Git, CI y versionado — propuesta para aprobación humana

`KNOWLEDGE_CORE=READY`
`NOVA_KNOWLEDGE_INPUTS_V1_READY`

El cierre normativo aceptado no se reabre. Esta revisión no ejecutó pruebas de producto, inferencia, retrieval, admission, benchmarks, campañas ni scorers. No staging, commit, push, tag ni workflows remotos.

## Estado y alcance exacto

Branch `main`; HEAD `717a24218dea7fb60d8b630896d653e39091bc7b` (sin cambios); staging vacío.
Entrada: 36 tracked modificados, 494 untracked y siete logs Knowledge documentales ocultos por `*.log`. Tras rescatar esos logs y añadir higiene: 38 tracked modificados y 510 untracked, incluyendo estos ocho documentos de revisión.

[commit_files.txt](commit_files.txt) enumera **546 archivos incondicionales**, uno por línea.
[commit_scope.json](commit_scope.json) añade por separado los **dos archivos condicionados** a aprobación por ser entradas normativas preexistentes del usuario: total **548** si se aprueban. No se propone un `git add -A`.

[worktree_inventory.json](worktree_inventory.json) clasifica cada archivo candidato y todos los grupos ignorados:
INCLUDE_IN_KNOWLEDGE_CLOSURE; INCLUDE_CI_GIT_HYGIENE; KEEP_OUT_USER_PREEXISTING; IGNORE_GENERATED_LOCAL; REQUIRES_HUMAN_DECISION.

La atribución usa el baseline K0: sólo los dos documentos de arquitectura ya existían como cambios del usuario. Los diffs Core y MEMORY pertenecen a integración Knowledge y a la reconciliación CI K0 documentada; no se añaden cambios personales por semejanza de nombres.

## Cambios aplicados únicamente a higiene

- `.github/workflows/nova_core_v1.yml`: ambos checkout usan configuración de proceso `core.autocrlf=false`, como MEMORY. Triggers, matrices, comandos y exclusiones heredadas permanecen semánticamente idénticos.
- `.gitignore`: siete excepciones exactas para logs archivados SHA-referenciados. Ninguna nueva exclusión ni regla genérica sobre docs, manifests, tests o fixtures.
- `.gitattributes`: `-text` sólo para docs/tests Knowledge y los tres documentos de arquitectura Knowledge. No renormalización. La simulación readonly con `git hash-object`, sin `-w`, pasó de **36/539** blobs que se modificarían a **0/540** con autocrlf activo.

Los archivos READY/matrices/manifests y todos los corpus/gold/freezes/fixtures quedan en la lista versionable. Las reglas existentes ya cubren venv, caches, bytecode, Node, builds, editor/OS, .env, estado local y locks de MEMORY. No se añaden exclusiones amplias hipotéticas. `desktop/build/` conserva sus iconos fuente.

## CI: sintaxis válida, alcance portable aún pendiente

[ci_audit.json](ci_audit.json) contiene los dos workflows completos en forma estructurada y la revisión de triggers, Python/Node, dependencias, cwd/rutas, env, if, matrices, caches, artefactos, timeouts, exit codes y filtros.

YAML 1.2/estructura: PASS con js-yaml 4.1.1 instalado; claves duplicadas rechazadas. Bash: parseo `bash -n` PASS. Todas las rutas explícitas de suites referenciadas existen. No se ejecutó pytest ni Node test. actionlint no está instalado: esto no afirma validación completa de expresiones GitHub ni un PASS remoto.

Problemas concretos **no ocultados mediante filtros**:

1. Core todavía usa `pytest tests`. Descubre los dos scorers K8 que el manifest vigente clasifica como históricos: `test_k8_quality.py` y `test_k8_post_cert_conflict.py`. Versionarlos no los convierte en certificaciones actuales.
2. Cuatro archivos contienen comprobaciones que requieren archivos históricos externos/locales:
   - `test_context_capability_profiles.py`: JSON históricos 4K/8K.
   - `test_k8_applicability_contracts.py::test_historical_head_skip_baseline_remains_eleven`: XML histórico.
   - `test_k8_execution.py::test_complete_product_identity_not_eleven_file_allowlist`: preflight V6 externo.
   - `test_k8_repair6_quality.py`: prueba de identidad externa de 241 pins en `test_prospective_structure_and_frozen_artifacts`, `test_current_post_cert_identity_is_separate_from_historical_v6` y `test_frozen_v6_quality` a través de `measure()`.
   La lista de 210 tests del HEAD aceptado es evidencia local vigente, **no** una garantía de portabilidad de todos sus checks. No se deben descartar los demás contratos activos de esos mismos archivos.
3. No existe instalación Node/npm en CI ni ejecución de los dos contratos JS Knowledge. El wrapper Python Desktop tiene un skip preexistente por ausencia de devdeps. Propuesta: job de contratos Desktop con Node 24.19.0, `npm ci`, las siete suites `.test.cjs` explícitas y `--experimental-transform-types`, más `tsc --noEmit`; sin Electron GUI, Ollama, packaging ni publicación.
4. MEMORY m0/m4 propagan el código de pytest y escriben reportes fuera del checkout. Core/MEMORY no descargan ni necesitan un modelo real para su regresión ordinaria. Los gates Electron/Ollama explícitos y el verificador de archivos externos no pertenecen al CI general.
5. No caches/uploads/timeout explícito actuales. Sus posibles mejoras son propuestas, no un nuevo requisito READY ni cambios aplicados.

**Decisión requerida**: autorizar una selección positiva, auditable y portable de contratos vigentes, separando verificación de archivos históricos y respetando la cobertura activa. No se ha añadido ningún ignore/skip/xfail para conseguir verde. No puedo afirmar todavía que el CI general vigente verificará íntegramente el nuevo estado.

## Fuera del commit y archivos locales

Quedan fuera hasta decisión humana:
- `docs/architecture/AUDITORIA_KNOWLEDGE_INPUTS_NOVA_V1.md`;
- `docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md`.

Son necesarios para un cierre documental completo y permanecen byte-idénticos. Solicito aprobación explícita de versionarlos; no los mezclo automáticamente con archivos creados por el agente.

No hay otros dirty tracked o untracked ajenos identificados al comparar el baseline K0 con los manifests. Los logs anteriores Core/Memory/Security ya ignorados quedan fuera; no se borran ni se incorporan. [ignore_inventory.json](ignore_inventory.json) enumera los grupos: node_modules, caches, dist/dist-electron y estado privado de fixtures MEMORY. Estos grupos no son los siete logs archivados Knowledge rescatados.

No hay archivos actualmente tracked que coincidan con reglas efectivas de ignore y deban quitarse del índice. Los 15 logs Security ya versionados tienen excepciones locales de archivo; los dos PEM de TLS son fixtures sintéticos versionados, no credenciales personales recién descubiertas. Nada fue unindexed.

La evidencia cruda externa permanece en sus ubicaciones originales y se referencia por SHA en los manifests. No se copió silenciosamente al checkout. Hace falta decisión de retención/publicación durable de esos archivos para auditoría fuera de esta máquina; **el CI ordinario no debe depender de su presencia local**. No se afirma que el commit por sí solo contenga todos los raw archives externos.

## Integridad y preservación

[preservation_receipt.json](preservation_receipt.json) conserva el resultado bruto:
- 537 artefactos existentes Knowledge: hash antes/después idéntico.
- Verificación readonly de 3.091 archivos: todos los grupos de producto, freezes, ledgers, intentos y cierre READY sin diferencias.
- El verificador histórico de snapshot amplio reporta **BLOCKED**, únicamente por los dos cambios CI/.gitignore autorizados de esta etapa. No se cambia ese verificador, su receipt anterior, el preservation map ni sus pins. El delta autorizado se documenta aditivamente; no se presenta como un PASS bruto.

Manifest READY SHA: `2883164d13bb08e80b4d9b41674fc8d93ef4f432b5caf7bb5c1166d5d0c4f2cc`.
Evidence index READY SHA: `85ef997d44975d4a65a7419aa9f7a8007c60632171579b087a0813cce6857ace`.

Los nueve archivos de `ready_closure/`, su matriz 40 SATISFIED / 0 NOT_EVIDENCED / 0 BLOCKED y sus manifests están en la propuesta. Ningún histórico, freeze, ledger o certificación fue reescrito. HEAD/tags históricos sin cambios.

- `K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14`
- `K8 POST-CERT REMEDIATION PARTIAL`
- `4K historical quality = 10/15`
- `KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS`
- `K8 CERTIFICATION V2 FAIL`
- `SOURCE_CONFLICT_FOCAL_E2E = FAIL`
- `SOURCE_CONFLICT_FOCAL_R2_E2E = FAIL`

## Commit/versionado propuestos, no ejecutados

Mensaje: `feat(knowledge): close Knowledge Inputs V1 READY and preserve certification history`.
Tag opcional: `nova-knowledge-inputs-v1-ready` (no existe; no creado).
Versión Python/Desktop permanece `0.12.6`. No se propone bump de producto en este cierre.

Pendientes de aprobación: los dos documentos previos del usuario, alcance portable/contratos Desktop de CI y retención durable de raw archives externos. Detenido antes de staging y publicación.
