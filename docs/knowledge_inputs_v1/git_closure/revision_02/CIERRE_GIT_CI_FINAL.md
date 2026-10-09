# Propuesta final Git/CI — revisión aditiva 02

Estado: pendiente de aprobación humana. Sin staging, commit, push, tag ni release.
No se reabre Knowledge, K8, SCF ni ninguna certificación.

`KNOWLEDGE_CORE=READY`
`NOVA_KNOWLEDGE_INPUTS_V1_READY`

§64 conserva 40 SATISFIED / 0 NOT_EVIDENCED / 0 BLOCKED. La versión permanece
0.12.6, tanto en Python como en Desktop.

## Alcance exacto

572 archivos: 39 tracked modificados y 533 nuevos. Clasificación del commit:
537 INCLUDE_IN_KNOWLEDGE_CLOSURE y 35 INCLUDE_CI_GIT_HYGIENE.
No queda dirty ajeno fuera, ni entrada sin decisión de pertenencia. Los dos
inputs normativos preexistentes están **expresamente aprobados**, no inferidos.

La lista exhaustiva es [commit_files.txt](commit_files.txt); su clasificación,
[worktree_inventory.json](worktree_inventory.json); requisitos de inclusión y
mensaje/tag, [commit_scope.json](commit_scope.json). El manifest final pinnea los
bytes de todos los candidatos salvo su propia referencia circular.
Los nueve documentos del cierre READY y todos sus manifests/matrices están incluidos.
Los 2.146 archivos del grafo READY dentro del checkout están tracked o incluidos.

Los ocho archivos de la propuesta anterior se conservan byte-inmutables.
Su manifest sigue siendo:
`31fb8b1a5a2f7e4dfd9624a8975b927e6292198cb4d56f5806a5c8725bbfe59f`.

### Dos inputs normativos aprobados

| Documento | SHA-256 normativo y actual |
|---|---|
| docs/architecture/AUDITORIA_KNOWLEDGE_INPUTS_NOVA_V1.md | `16671029e7584a37f0609b60825e7f7b3bd28d5cc0c421ba0c5bfe45f25b9888` |
| docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md | `417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432` |

Ambos coinciden con `k0_freeze.json: unchangedPins` y las referencias normativas
vigentes. No se reescribieron ni normalizaron.

## CI: selección positiva vigente

No hay `pytest tests` indiscriminado seguido de nuevos ignores. Se versionan
`ci/pytest_contracts.json`, `ci/contract_inventory.py`, `ci/run_contracts.py` y
`ci/README.md`. El manifest clasifica 3.795 contratos por función/node-id:

| Categoría | Contratos |
|---|---:|
| CURRENT_PORTABLE_CI | 3.632 |
| CURRENT_LOCAL_EVIDENCE_ONLY | 7 |
| HISTORICAL_CERTIFICATION_ARTIFACT | 89 |
| SPECIAL_INFRASTRUCTURE_ONLY | 67 |
| Sin clasificación | 0 |

Cada entrada enlaza motivo, job/plataforma, infraestructura y referencias
históricas/current-regression. Se seleccionan todas las instancias parametrizadas
de cada función; no se filtran resultados, parámetros ni tests mediante `-k/-m`.
La validación AST rechaza contratos nuevos/eliminados sin reconciliación explícita.
La colección rechaza cualquier selector ausente o de categoría/job incorrectos
antes del setup de fixtures; no deselecciona ni omite silenciosamente.

Las siete funciones local-only son explícitas en [ci_audit.json](ci_audit.json).
Sus archivos mixtos siguen aportando las demás funciones portables.
Los 29 contratos específicos del guard/scorer SCF son históricos, no nuevos gates.
Los contratos deterministas K8 reconocidos por el manifest **vigente** siguen siendo
regresión unitaria, no ejecución de campañas/scorers como certificación.
Los contratos focales actuales R1/R2 son independientes de SCF y del resultado V2.

### Responsabilidades y validación realizada

| Ámbito | Hosts CI | Contratos Windows | Instancias colectadas Windows |
|---|---|---:|---:|
| Core | Windows/Linux/macOS | 2.630 | 2.747 |
| Security actual | Windows/Linux/macOS | 274 | 615 |
| Memory | Windows/Linux/macOS | 326 | 791 |
| Knowledge | Windows | 335 | 1.015 |
| Security nativo especial | Windows, sólo manual opt-in | 59 | 89 |
| Desktop ordinario | Windows / Node 24.19.0 | siete suites + TypeScript | No ejecutado localmente |

Los 67 contratos de `test_model_selector.py` requieren el `curses` de stdlib.
Su módulo ya tenía SkipTest en Windows sin curses: quedan **positivamente cubiertos**
por Core Linux/macOS, sin nuevo skip ni edición de tests. Los 59 contratos Core
específicos de Windows quedan cubiertos por Core Windows. Core POSIX selecciona
2.638 contratos por host. La unión cubre los 3.632 contratos actuales, sin
duplicación accidental entre ámbitos sobre un mismo host.

Memory mantiene los 326 contratos antes cubiertos por m0. La redistribución
exhaustiva del alcance m4 consta en [positive_selection_validation.json](positive_selection_validation.json):
los contratos Core pasan al job Core, el wrapper Desktop a su suite JS directa,
GUI/modelos reales quedan explícitamente SPECIAL_INFRASTRUCTURE_ONLY.
SEMANTIC_PROFILE sigue NOT_CERTIFIED. No se modificó el runner Memory histórico.

El antiguo job Security host tenía flags opt-in no activados. Ahora su ejecución
es explícita y manual (`native_security=true`), con fixture privado y sin modelo;
no se afirma certificación host-real nueva en push/PR.

### Cambios YAML/YML

* `.github/workflows/nova_core_v1.yml`: Core y Security positivos separados;
  Security nativo manual; Node para el contrato Python/Node existente.
* `.github/workflows/nova_memory_v1.yml`: selección Memory positiva sin volver a
  duplicar el m4; conserva NumPy sintético y el scope no-semántico.
* `.github/workflows/nova_knowledge_v1.yml`: nuevo job Knowledge positivo con
  guard de colección; nuevo job Desktop ordinario.
* Los tres conservan push / pull_request / workflow_dispatch sin filtros de rutas.
  Python 3.14; checkout con core.autocrlf=false; timeouts 45 minutos (Desktop 20).
  No caches nuevos. Los jobs Python preservan logs, colección, selección y JUnit
  mediante upload-artifact, incluso ante fallo, sin tolerarlo.
* Desktop usa cwd `desktop/`, `npm ci`, Node 24.19.0,
  `node --experimental-transform-types --test` con las siete rutas solicitadas y
  `npx --no-install tsc --noEmit`. No GUI, build, packaging, publish ni Ollama.
* Los jobs ordinarios no requieren rutas personales, Temp histórico, AUTHORIZED,
  ledgers, modelos ni bundle externo. RUNNER_TEMP sólo aloja fixtures **actuales**
  privados y reportes nuevos fuera de cualquier checkout, no evidencia histórica.
* No nuevos skips, xfails, continue-on-error, `|| true`, ignores ni exclusiones
  silenciosas. Se propaga el código de salida real.

Diff exacto contra HEAD: [workflow_changes.patch](workflow_changes.patch).
`git apply --check --reverse` confirma que corresponde a los tres archivos actuales,
sin aplicar nada. YAML 1.2, rutas, estructura y 16 comandos Bash parse-only: PASS.
Referencias oficiales: [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[setup-node v4](https://github.com/actions/setup-node/blob/v4/action.yml),
[upload-artifact v4](https://github.com/actions/upload-artifact/blob/v4/action.yml).

La colección Windows de los cinco ámbitos fue PASS. No se ejecutó ninguna función
de test ni setup de fixture. Linux/macOS se validaron estáticamente por selección,
no mediante ejecución host. No se ejecutaron npm ci, suites JS ni TypeScript aquí.
No hay actionlint instalado; no se afirma ejecución remota ni CI verde.
Los incidentes de validación iniciales se conservaron fuera del checkout y se
explican en [collection_validation.json](collection_validation.json); no son intentos
de producto ni fueron transformados en resultados de calidad.

## .gitignore / .gitattributes

No hay reglas nuevas en esta revisión. `.gitignore` mantiene las siete excepciones
precisas de logs Knowledge SHA-referenciados, íntegramente listadas en
[ignore_inventory.json](ignore_inventory.json). Ningún candidato está ignorado.
No hay archivos actualmente tracked que coincidan con reglas efectivas de ignore;
los 15 logs Security versionados conservan sus excepciones locales.

641 entradas previamente ignoradas quedan fuera: caches, node_modules, builds,
bytecode, runtime/locks/DB locales y logs documentales antiguos **no Knowledge**.
Cada entrada está clasificada; no se borró ni retiró ninguna del índice.
No se ampliaron ignores de docs, fixtures, tests ni manifests.

Las cuatro reglas `-text` por subárbol Knowledge también abarcan futuros archivos
no congelados: son más amplias que una lista individual de los 36 archivos CRLF
detectados. Se informa expresamente esa amplitud **sin ampliar ni reducir las
reglas aprobadas**. Se mantienen para preservar la familia SHA-pinneada y sus
artefactos aditivos. Las otras tres reglas son documentos arquitectónicos exactos.
No se ejecutó renormalización ni se cambió configuración Git global.

## Retención externa preparada

[ci/build_ready_evidence_bundle.py](../../../../ci/build_ready_evidence_bundle.py)
archiva el grafo exacto del manifest/verificador READY; no hace barridos genéricos,
no ejecuta producto y no mueve originales. Su modo verify sólo necesita ZIP y SHA,
no las rutas originales ni backend.

Bundle fuera del checkout:
`C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/durable-archives/git-closure-r02-20261009/nova-knowledge-inputs-v1-ready-external-evidence.zip`

* 946 raw artifacts; 26.184.146 bytes originales; 2.714.439 bytes ZIP.
* Dos miembros adicionales de metadata: INDEX.json y README.md.
* Orígenes, tamaños, SHA y membresía normativa están en [bundle_manifest.json](bundle_manifest.json).
  Ese archivo es byte-idéntico a INDEX.json:
  `72d2b18cf8359f9f5b24ba6adec635ff82f6ba229793a017e97d25ce32a393fe`.
* SHA-256 ZIP:
  `9e981b32f5b098c1d4449a7a18d74b2653dc9a21040f63a9ea69ed19968ce9e2`.
* Cada archivo se verificó antes/después del archivado y dentro del ZIP. Todos los
  originales se preservan; ZIP nuevo readonly, sin sobrescritura.
* Sólo el índice/receipt se versionan, no el ZIP. Publicación aún NOT_PUBLISHED,
  prevista como asset de `nova-knowledge-inputs-v1-ready` o almacenamiento durable equivalente.
  El README advierte de paths personales/evidencia cruda para revisar acceso y
  destino al autorizar esa publicación futura. CI no descarga ni exige el bundle.

## Integridad, resultado y límites

Los 537 artefactos Knowledge originales y ocho documentos de la propuesta anterior
conservan todos sus bytes/SHA. No cambió producto, test existente, scorer, runner,
adapter, corpus, gold, threshold, prompt, freeze, ledger ni resultado histórico.

El verificador histórico sigue sin modificaciones y reporta **BLOCKED** únicamente
por los hashes de tres configuraciones vivas autorizadas: Core YAML, Memory YAML y
.gitignore. No se ocultó ni se repinneó ese resultado. Los otros grupos READY,
freezes, Turn crudo, ledgers y regresión histórica coinciden; el receipt aditivo
distingue claramente este cambio Git/CI de corrupción o reparación de producto.
Este cierre no transforma los FAIL en PASS ni cambia la resolución normativa READY.

Se conserva:
```text
K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14
K8 POST-CERT REMEDIATION PARTIAL
4K historical quality = 10/15
KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS
K8 CERTIFICATION V2 FAIL
SOURCE_CONFLICT_FOCAL_E2E = FAIL
SOURCE_CONFLICT_FOCAL_R2_E2E = FAIL
```

HEAD y branch permanecen `717a24218dea7fb60d8b630896d653e39091bc7b` / `main`;
índice vacío. Ningún HEAD histórico fue reescrito. En esta etapa:
producto/tests ejecutados=0; inference=0; retrieval=0; admission=0; campañas=0;
workflows remotos=0; staging=0; commit=0; push=0; tag=0; release=0.

Mensaje propuesto:
`feat(knowledge): close Knowledge Inputs V1 READY and preserve certification history`

Tag propuesto: `nova-knowledge-inputs-v1-ready`. No cambio de versión.
Detención para aprobación humana de la lista exacta antes de cualquier staging.
