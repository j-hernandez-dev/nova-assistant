# K8 Post-Certification Remediation — perfil suplementario 8K

Perfil: `SUPPLEMENTAL_OPERATIONAL_PROFILE_8K`.

Resultado: `SUPPLEMENTAL 8K MULTI-SOURCE PROFILE PASS`.

Estado global conservado: `K8 POST-CERT REMEDIATION PARTIAL`.

Estado normativo: `Knowledge-specific minimum context window = NOT_DEFINED`.

La autorización de esta evaluación no define 8192 como mínimo oficial de Knowledge Inputs. El protocolo prospectivo 4096 y sus cinco FAIL permanecen íntegros, con `ADMISSION_BUDGET_INFEASIBLE_UNDER_4K`. No se obtiene un PASS retrospectivo ni se sustituye una medición 4K por ésta.

## A — Identidad y única variable de capacidad

Se utilizó el mismo corpus/gold, scorer y thresholds congelados, sin editar sus archivos. Se ejecutó la función y assertion originales `test_frozen_prospective_quality` / `measure` del scorer post-cert, SHA `ce4eec225fabcaa1170f5a19d7b50dd6571af913784aaf84180261a98818cb1a`.

Como el scorer fija literalmente `ContextSelection(4096)`, un adaptador externo y temporal suministró `ContextSelection(8192)` mediante el preset Core existente. No se reemplazaron scoring, métricas, assertions ni clases de producto. El adaptador se restauró tras la ejecución; se registraron exactamente 40 selecciones 8192.

Para conservar UUIDs reales, se copiaron privadamente los bytes del estado SQLite de la medición 4K post-cert `quality-final/pytest-private/test_frozen_prospective_qualit0/state`, en lugar de reimportar fuentes y generar nuevas revisions. La otra adaptación de ejecución sustituyó la siembra por verificación/lectura de ese mismo estado: los 24 sourceIds, todas las revisions actuales y previas, los chunks, scope, lifecycle, locators, blobs y valores factuales son los del estado 4K de referencia. Se verificaron tanto los bytes del clone previo a abrirlo como su identidad semántica después de usarlo. El estado histórico quedó byte-idéntico.

No hay cambio de variable documental: este adaptador conserva los datos que la siembra normal regeneraría con nuevos UUIDs. La única variable de capacidad alterada es `Turn context window: 4096 -> 8192`. Los 40 rankings, planes estructurados, gold, requiredSources, modos, estado semantic y contador de retrieval coinciden con la medición 4K de referencia.

El producto post-cert es el mismo. Se fijaron y verificaron sus **241 archivos de producto**, incluidos Core/MEMORY/Desktop y `pyproject.toml`. Floor `>0.5`, caps 32/32/24/10, RRF, provenance, citations, guard, reservas y fracciones permanecen intactos. Los 1952 archivos de baseline permanecieron byte-idénticos durante la evaluación. No hubo red, inferencia, instalaciones, modelos descargados ni cambios de configuración global.

Runtime: Python `3.14.6`, `C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe`, `-B`, mismo site offline existente. Output privado válido: `C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-supplemental-8k-20261008-b`. Exit code 0. Es invocación directa del scorer/assertion congelados, no una ejecución de las suites completas ni una certificación de hardware/modelo. Se mantienen las limitaciones de calidad lexical determinística, sin medir respuestas de un LLM.

## B — Presupuesto registrado antes de medir los gates

Antes de llamar al scorer se generó `budget-pre-gates.json`, SHA `ac19f66bd62a758a17210cee30c0a64bcd41aa611dc85664dc0235a5a2763c62`. El log registra primero `BUDGET_RECORDED_BEFORE_GATES` y después los resultados. Los cinco casos triples se auditaron con `stage/freeze` reales en un clone independiente del mismo estado.

```text
Turn context window                  8192
output reserve                       1024 = clamp(ceil(8192 * .125), 1024, 4096)
safety margin                         820 = max(512, ceil(8192 * .10))
system total                          466 = Knowledge guard 426 + Core sintético 31 + protocolo 9
schemas / project / skills              0
available                            5882 = 8192 - 1024 - 820 - 466
SharedRetrievalCap                    882 = floor(5882 * .15)
MEMORY / otros retrieval                0
Knowledge cap efectivo                882
```

El aumento de safety margin de 512 a 820 es resultado de la misma fórmula vigente, no un cambio de policy. Contador `utf8_bytes_div_3`, estimated=true; incluye JSON exterior, escaping de filas y overhead. `stage`, `freeze` y `KnowledgeCapsule.token_cost` cuentan el mismo payload una vez, sin doble cargo.

| Caso | K1/K2/K3 incrementales, desde wrapper 45 | K1/K2/K3 acumulados | Capsule admitido | Cap | Evidencias completas |
| --- | --- | --- | ---: | ---: | ---: |
| pc-en-three | 101 / 102 / 102 | 146 / 248 / 350 | 350 | 882 | 3 |
| pc-en-all | 101 / 102 / 102 | 146 / 248 / 350 | 350 | 882 | 3 |
| pc-es-three | 102 / 102 / 103 | 147 / 249 / 352 | 352 | 882 | 3 |
| pc-en-summarize | 101 / 102 / 102 | 146 / 248 / 350 | 350 | 882 | 3 |
| pc-es-all | 102 / 102 / 103 | 147 / 249 / 352 | 352 | 882 | 3 |

Los 20 positivos usan el guard de evidencia, `system=466`, `available=5882`, cap 882. Los 20 negativos conservan la ruta normativa de ausencia: `system=221`, `available=6127`, cap 919, capsule vacío. El raw del mismo scorer contiene el presupuesto individual de los 40 casos; no se impuso artificialmente un mismo system/cap a ambas rutas.

## C — Gates y admisión real

| Gate | Resultado | Threshold congelado | Estado |
| --- | --- | --- | --- |
| Recall@5 | 20/20 = 100% | 100% | PASS |
| Precision@1 | 20/20 = 100% | 100% | PASS |
| Required multi-source admissions, macro | 15/15 = 100% | 100% | PASS |
| Abstention | 20/20 = 100% | ≥95% | PASS |
| Scope/current/delete | 40/40 = 100% | 100% | PASS |
| Critical false source expansion | 0/40 | 0 | PASS |

Required sources micro: **33/33**. Input original preservado en 40/40 y exactamente un retrieval por caso. Se obtuvo admisión, no únicamente recuperación.

Los cinco casos triples contienen tres sourceIds distintos en la capsule congelada, con texto original completo y `truncated=false`; EN conserva los tres valores `PCC_CAD_D53/E53/F53`, ES los tres `PCC_INT_M86/N86/O86`. No se reemplazó una afirmación por un carácter, sufijo o cota artificial. Todos los sourceId/revisionId/chunkId/locator corresponden al estado 4K clonado y a los candidatos autorizados.

Una comprobación adicional **sólo de citations/provenance**, sin volver a medir gates, reconstruyó la ruta productiva en otro clone del mismo estado. Las cinco registries reales congeladas coinciden exactamente con los targets/textos medidos; `[K1] [K2] [K3]` validan en su Turn, los tres IDs se rechazan en otro Turn y `[K4]` no admitido se rechaza. La comprobación es estructural; no afirma entailment de una respuesta generada por un LLM.

## D — Interpretación

El bloqueo de los cinco triples 4K es compatible con insuficiencia del cap de ese perfil: las afirmaciones originales completas cuestan 350/352 tokens, superiores al cap 314 en 4K y claramente inferiores al cap 882 en 8K. La ruta de admisión vigente logra las tres fuentes sin cambio de producto cuando disponen de espacio. Esto no demuestra corrección universal de admission ni crea source-aware admission nuevo.

```text
SUPPLEMENTAL 8K MULTI-SOURCE PROFILE PASS
K8 POST-CERT REMEDIATION PARTIAL
Knowledge-specific minimum context window = NOT_DEFINED
4K: ADMISSION_BUDGET_INFEASIBLE_UNDER_4K — cinco FAIL históricos intactos
```

El perfil 8K es evidencia suplementaria de capacidad, no re-medición ni reparación del protocolo 4K. Se verificaron antes/después los 46 artefactos del manifest post-cert anterior y los 24 del manifest de auditoría de presupuesto. No se editó corpus, gold, scorer, thresholds, producto, resultados 4K ni manifests anteriores.

## E — Identidad post-cert y guards históricos V6

Se generó una identidad explícita del producto post-cert de 241 pins en `citation-identity-proof.json`. Respecto del freeze V6, los únicos desajustes siguen siendo exactamente los dos del delta post-cert previamente autorizado: `knowledge_query.py` y `knowledge_retrieval_sqlite.py`. No hubo delta de producto adicional.

Los dos guards históricos conservan intacta su función byte-pinneada `verify_freeze()`, que compara el producto actual con los SHA V6 antes de medir. Sus freezes/hashes/assertions históricos no se reescribieron, ni se añadieron monkeypatches, xfails, exclusiones o sustituciones para ocultar los FAIL. Los resultados V6 históricos no se atribuyen al producto post-cert.

**La integración de la reconciliación en esos dos tests está pendiente de decisión humana.** Para que acepten la identidad post-cert explícita es necesario introducir otra ruta en su `verify_freeze()` actual. La instrucción anterior exige detenerse antes si se necesita tocar la assertion histórica. Se solicitó confirmación específica para añadir únicamente esa ruta, preservando la verificación histórica y una copia exacta del guard original; no se realizó el cambio sin esa confirmación. La identidad/pins verificada por esta evidencia no se presenta como si ya hubiera hecho pasar los dos tests.

No se relanzaron Knowledge/MEMORY/Core/Desktop/HEAD ni el corpus V6. No hay nuevo claim de suites completas sin FAIL. Los 11 skips históricos y los FAIL registrados anteriormente siguen intactos. E2E original no se repitió.

## F — Intentos y preservación

El intento inicial `...supplemental-8k-20261008-a` registró correctamente presupuesto, pero falló **antes de puntuar casos** al exigir ausencia de WAL en la verificación del clone que el store acababa de abrir. Clasificación: `HARNESS_BUG`, no fallo del perfil 8K ni del producto. Se corrigió únicamente el auditor/adaptador no congelado para leer la vista SQLite read-only cuando el clone tiene WAL. El intento y su log permanecen intactos; la medición válida se hizo en el directorio nuevo `...-b`.

Una consulta exploratoria read-only previa usó el nombre de columna inexistente `lifecycle_state`; se corrigió a `state`, sin escrituras ni medición. Su error permanece en el transcript.

La campaña original sigue cerrada como `K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14`, con `source-conflict` `FAIL / RETRIEVAL_FAILURE`. No Certification V2, K8 Repair V7, READY, commit, push ni tag. Detenido para revisión humana.

## Evidencia

- Scorer raw 8K: `C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-supplemental-8k-20261008-b/gates/postcert-quality.json`, SHA `66bfe3445bb40c45eb795beac5980cb886ba22b993804244b44a1c0f10afbe93`.
- Resultado suplementario: `...-b/supplemental-profile-result.json`, SHA `5d5afbf324565424bf46d76df3822d67409d29df19af83a5c92d2cf036b34e71`.
- Proof de registries/identidad: `C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-supplemental-8k-citation-proof-20261008-a/citation-identity-proof.json`, SHA `e7919d6f04ca67fc9d1833c68d2d306da199b7955723b6e661da4053ea0734dc`.
- Manifest aditivo: `docs/knowledge_inputs_v1/k8_post_cert_supplemental_8k_manifest.json`.
