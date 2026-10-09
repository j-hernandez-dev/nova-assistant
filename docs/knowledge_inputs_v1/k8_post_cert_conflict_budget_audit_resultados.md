# K8 Post-Certification Remediation — auditoría de admisión

Resultado de esta continuación: `ADMISSION_BUDGET_INFEASIBLE_UNDER_4K`.

Se aplica la parada de la rama C autorizada. No se ha implementado source-aware admission, reconciliación V6 ni cambio de producto, contratos, ventana o thresholds en esta continuación. No se declara `K8 POST-CERT REMEDIATION PASS`.

## Alcance y trazabilidad

Se reutilizó exclusivamente el corpus prospectivo post-cert ya congelado. Se auditaron los cinco casos que fallaron tanto en la primera medición como en la medición posterior registrada: `pc-en-three`, `pc-en-all`, `pc-es-three`, `pc-en-summarize`, `pc-es-all`. Ambas mediciones históricas permanecen intactas; esta auditoría no las reemplaza, no recalcula los gates y no constituye una tercera certificación.

La auditoría ejecutó la ruta real `KnowledgeAdmission.retrieve/stage/freeze` y `ContextManager` con SQLite privado, sin MEMORY, tools, red ni inferencia. Dos replays de los mismos cinco casos produjeron presupuestos, payloads y desgloses idénticos. Los tres sourceIds relevantes se recuperaron en cada caso y sólo dos llegaron al capsule. No se modificó ranking ni floor `>0.5`.

Runtime: Python `3.14.6`, ejecutable `C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe`, `-B`, dependencia offline ya existente. Salida fresca y privada: `C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-conflict-budget-audit-20261008-a`. `run.json`: exit code 0. Es una auditoría con assertions, no una ejecución pytest ni una suite de regresión.

Se verificaron los 46 artefactos del manifest post-cert anterior antes y después. Los 1949 archivos del inventario tomado tras añadir el auditor permanecieron byte-idénticos durante la medición. HEAD sigue en `717a24218dea7fb60d8b630896d653e39091bc7b`, rama `main`, staging vacío y tags intactos. Los únicos archivos añadidos en esta continuación son el auditor y estos documentos aditivos; las modificaciones anteriores del usuario/producto permanecen intactas.

## Presupuesto del Turn

La ventana y todas las fracciones/reservas son las vigentes, sin cambios:

```text
Turn total                         4096
output reserve                     1024
safety margin                       512
system total                        466 = Knowledge guard 426 + Core sintético 31 + frame del protocolo 9
schemas / project / skills            0
available                          2094 = 4096 - 1024 - 512 - 466
SharedRetrievalCap                  314 = floor(0.15 * 2094)
MEMORY / otros retrieval              0
cap realmente disponible Knowledge  314
```

Antes de insertar el guard, `system=40`, `available=2520` y el cap provisional es 378. Ese cap **no es el de admisión**: `stage` añade el guard obligatorio primero y vuelve a preparar el contexto. No se puede omitir el guard ni usar el cap previo para hacer caber K3. El mensaje actual se conserva íntegro y no reduce el mínimo que determina el cap en estos cinco casos.

| Caso | Turn | Query | System | Available | Cap Knowledge | `stage` / `freeze` / capsule | Fuentes admitidas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pc-en-three | 4096 | 48 | 466 | 2094 | 314 | 248 / 248 / 248 | 2/3 |
| pc-en-all | 4096 | 41 | 466 | 2094 | 314 | 248 / 248 / 248 | 2/3 |
| pc-es-three | 4096 | 51 | 466 | 2094 | 314 | 249 / 249 / 249 | 2/3 |
| pc-en-summarize | 4096 | 46 | 466 | 2094 | 314 | 248 / 248 / 248 | 2/3 |
| pc-es-all | 4096 | 45 | 466 | 2094 | 314 | 249 / 249 / 249 | 2/3 |

`stage` y `freeze` cuentan el mismo payload, no dos cargos acumulativos. `KnowledgeCapsule.token_cost` registra ese mismo coste, no un tercer cargo. Hay 66 tokens restantes en EN y 65 en ES, insuficientes para otra fila citable, aun con un texto mínimo útil.

## Conteo exacto conforme al contador vigente

No se empleó tokenizer del modelo. Son unidades estimadas de admisión del contador contractual `utf8_bytes_div_3`, no tokens medidos de un LLM:

```text
coste = ceil(bytes UTF-8 de serialized(clean message) / 3) + 12
```

`clean message` conserva `role` y `content`, retira únicamente claves privadas `_context_*` igual que producto. Se incluyó el segundo nivel de escaping JSON: las filas JSON están dentro del string `content` del JSON exterior. Ignorar ese nivel subestimaría el coste.

La atribución por componente usa bytes exactos aditivos y redondeo telescópico en orden fijo: envelope, framing, metadata, citations, locator/label, texto y separadores. Sólo se aplica un `ceil` global; no se suman techos independientes. El JSON raw conserva cada campo y cada byte, el orden y el padding final de redondeo.

### Desglose de las tres evidencias mínimas útiles

Cada celda de componente muestra `bytes exteriores / tokens atribuidos`. `Framing` muestra wrapper y header/footer; los 12 tokens de overhead del mensaje se suman aparte. CitationRegistry host añade cero tokens; sus campos renderizados `id`/`cite` sí están contados.

| Caso | Envelope + framing | Metadata/provenance | `id` / `cite` | Locator / display label | Texto factual | Separadores | Overhead | Total bytes / tokens |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- |
| pc-en-three | 28/10 + 67/22 | 204/68 | 90/30 | 417/139 | 165/55 | 35/12 | 12 | 1006/348 |
| pc-en-all | 28/10 + 67/22 | 204/68 | 90/30 | 417/139 | 165/55 | 35/12 | 12 | 1006/348 |
| pc-es-three | 28/10 + 67/22 | 204/68 | 90/30 | 417/139 | 171/57 | 35/12 | 12 | 1012/350 |
| pc-en-summarize | 28/10 + 67/22 | 204/68 | 90/30 | 417/139 | 165/55 | 35/12 | 12 | 1006/348 |
| pc-es-all | 28/10 + 67/22 | 204/68 | 90/30 | 417/139 | 171/57 | 35/12 | 12 | 1012/350 |

Por fila, los campos normativos/actuales se preservan: `id=13 bytes`, `cite=17`, `label=34`, `locator=105`, `trust=33`, `partial=17`, `truncated=true=18`, braces/commas=9. Las claves y quoting pertenecen al componente del campo. El texto con su sintaxis cuesta 55 bytes en EN y 57 en ES; de ellos, la afirmación factual tiene respectivamente 42 y 44 bytes. Los tres locators siguen siendo `TEXT_LINES`, `lineStart=1`, `lineEnd=1`, `schemaVersion=1`; el display label sigue siendo `Synthetic K1 fixture`. Los ocho bytes adicionales de separadores corresponden a cuatro newlines escapados del payload de tres evidencias.

### Desglose del capsule realmente admitido, dos evidencias completas

| Casos | Envelope | Framing | Metadata/provenance | `id`/`cite` | Locator/label | Texto | Separadores | Overhead | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- |
| pc-en-three, pc-en-all, pc-en-summarize | 28/10 | 67/22 | 138/46 | 60/20 | 278/93 | 112/37 | 24/8 | 12 | 707 bytes / 248 tokens |
| pc-es-three, pc-es-all | 28/10 | 67/22 | 138/46 | 60/20 | 278/93 | 116/38 | 24/8 | 12 | 711 bytes / 249 tokens |

El CitationRegistry contiene mappings `sourceId/revisionId/chunkId/locator/displayLabel/originDisplay/schemaVersion` ligados al Turn; no se serializa de nuevo al prompt. Su representación informativa host tiene 795/793/795/799/793 bytes para los cinco casos en el orden de las tablas, con **0 tokens adicionales de prompt**. SourceRegistry también añade **0 tokens de prompt**. Esto describe el comportamiento vigente, no una reducción de provenance. Los dos marcadores admitidos validan estructuralmente con sus targets originales; `[K3]` permanece inválido porque no fue admitido. No se presenta una fila hipotética como una cita actual.

### Incrementos K1, K2, K3

El wrapper sin filas cuesta 45 tokens como referencia de cálculo; producto no admite una capsule vacía con ese cargo. Cada incremento es la diferencia entre costes del payload completo, no el conteo aislado de la fila.

| Caso | Texto completo: incremento K1/K2/K3 | Texto completo: acumulado K1/K2/K3 | Prefix útil: incremento K1/K2/K3 | Prefix útil: acumulado K1/K2/K3 |
| --- | --- | --- | --- | --- |
| pc-en-three | 101 / 102 / 102 | 146 / 248 / 350 | 101 / 101 / 101 | 146 / 247 / 348 |
| pc-en-all | 101 / 102 / 102 | 146 / 248 / 350 | 101 / 101 / 101 | 146 / 247 / 348 |
| pc-es-three | 102 / 102 / 103 | 147 / 249 / 352 | 101 / 102 / 102 | 146 / 248 / 350 |
| pc-en-summarize | 101 / 102 / 102 | 146 / 248 / 350 | 101 / 101 / 101 | 146 / 247 / 348 |
| pc-es-all | 102 / 102 / 103 | 147 / 249 / 352 | 101 / 102 / 102 | 146 / 248 / 350 |

## Factibilidad útil y mínimo demostrado

“Útil” exige retener la afirmación original que permite comparar las fuentes: sujeto, atributo y valor factual opaco completo. Se conservó el prefix contiguo hasta el final del valor, sin paráfrasis ni transformación. Sólo se retiró el punto terminal, declarando `truncated=true` como corresponde al excerpt. Por ejemplo:

```text
TALVORA10653 beacon cadence is PCC_CAD_D53
ZEVORIA10986 intervalo baliza es PCC_INT_M86
```

Se probaron todos los subsets/órdenes posibles: 3 alternativas de una fuente, 6 de dos y 6 permutaciones de tres por caso. No hay combinación ni orden más barato bajo este renderer y este modelo de prefix útil.

| Casos | Mínimo útil 1 fuente | Mínimo útil 2 fuentes | Mínimo útil 3 fuentes | Déficit de 3 frente a cap 314 |
| --- | ---: | ---: | ---: | ---: |
| pc-en-three, pc-en-all, pc-en-summarize | 146 | 247 | 348 | 34 |
| pc-es-three, pc-es-all | 146 | 248 | 350 | 36 |
| Presupuesto que cubre todos los cinco | 146 | 248 | 350 | 36 |

Son mínimos demostrados del **presupuesto Knowledge**, con guard/sistema/reservas ya descontados del Turn. No equivalen a recomendar una ventana total de 350 tokens ni prueban mínimos universales para cualquier documento/locator.

Además se calculó una cota deliberadamente optimista: preservar sólo los tres valores completos, sin siquiera sujeto/atributo, manteniendo intactos todos los demás campos. Sus 913 bytes cuestan `ceil(913/3)+12 = 317`, aún por encima de 314. El cap permite como máximo `(314-12)*3 = 906` bytes; ni esta cota cabe, por 7 bytes. No se admite ni se acepta como sustituto útil ese payload. A diferencia del diagnóstico previo de 307 tokens con un carácter por fuente, esta cota conserva los identificadores factuales completos; truncarlos o representar diferencias artificiales entre caracteres perdería los valores originales necesarios para comparar.

Conclusión: reservar espacio por source no puede resolver estos cinco casos bajo el cap vigente sin perder contenido factual o alterar framing/metadata/citations. La estrategia source-aware no obtiene autoridad para exceder límites. No se reduce ninguno de esos campos ni el guard para fabricar PASS.

## Guards históricos V6

Se realizó sólo inspección y comprobación de hashes. `test_k8_repair6_quality::test_prospective_structure_and_frozen_artifacts` y `::test_frozen_v6_quality` llaman primero a `verify_freeze()`, que compara incondicionalmente el archivo de producto actual con cada pin V6. Los dos únicos desajustes del freeze son los del delta post-cert ya identificado:

| Producto | SHA V6 original | SHA actual post-cert, anterior a esta auditoría |
| --- | --- | --- |
| local_cli/infrastructure/knowledge_query.py | 6590bab13e77718d9aa9c3de75779fc5683a502fec83c623f0709dffb302df2c | 15dd6f01ccdd8aedce0808543a9ffea68bc5866b6c857a4bce1f72c8a8886cea |
| local_cli/infrastructure/knowledge_retrieval_sqlite.py | f8b499ed545c6ed1e12d3f5ca9dc47b3b7b3b7103bd65c6b4d1c55a655b25412 | a3a59bf40823fa74950e7da9ddd58837850f2098d881b2491b3d14911021c7cf |

La clasificación histórica `HARNESS_BUG` permanece. `k8_repair6_freeze_v2.json` conserva SHA `cdbe771621f93c1c98b5268a7e2c1f232f399977c8eca45ba0f6eb15467b71b1`; no se reescribieron sus pins ni la assertion histórica. No se añadieron monkeypatches, exclusiones, xfails, sustituciones de producto ni filtros de suites. La reconciliación explícita sigue **pendiente**, no simulada por esta tabla: la rama C obliga a parar antes de continuar. Incorporar una ruta diferente de verificación a estos tests requerirá revisar explícitamente su punto de comprobación; no se realizó ese cambio ni se atribuye evidencia V6 al producto posterior.

## Revalidación y revisión humana requerida

No se corrigió producto en esta continuación, por lo que no se ejecutaron nuevos gates ni Knowledge/MEMORY/Core/Desktop/HEAD. Esto no convierte los FAIL históricos en skips ni en PASS. Los resultados anteriores permanecen: multi-source admissions 10/15; Knowledge y HEAD con tres FAIL, incluidos ambos guards V6; 11 skips históricos de HEAD intactos. No hay claim de 0 FAIL/ERROR.

Knowledge Inputs V1 §25 mantiene un único SharedRetrievalCap y §23 permite admitir menos; no declara una ventana operativa mínima exclusiva de Knowledge. Core V1 §17 y el catálogo implementado admiten 4K/8K/16K/32K/64K manual y AUTO; 4K sigue siendo el fallback conservador con límites desconocidos. MEMORY V1 reconoce 4K/8K/16K como configuraciones normales. Por tanto **no se puede afirmar que 8192 sea ya el mínimo oficialmente requerido por Knowledge**. Tampoco se verificó aquí capacidad de ningún modelo/host ni se ejecutó una evaluación a 8192.

Se solicita revisión humana para confirmar la ventana operativa mínima oficialmente soportada por Knowledge Inputs y decidir si el gate debe evaluarse **también**, con evidencia adicional identificada separadamente, en esa ventana. El siguiente preset de Core por encima de 4096 es 8192; no se impone ni se autoriza por inferencia. El corpus/protocolo 4K y sus cinco FAIL permanecerán inmutables cualquiera que sea la decisión.

La campaña original continúa cerrada como `K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14`, con `source-conflict` histórico `FAIL / RETRIEVAL_FAILURE`. No K8 PASS retrospectivo, E2E original, K8 Repair V7, Certification V2, READY, commit, push ni tag. Detenido para revisión humana.

## Evidencia aditiva

- Auditor: `tests/knowledge_inputs_v1/k8_post_cert_budget_audit.py`.
- Raw completo: `C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-conflict-budget-audit-20261008-a/admission-budget-audit.json`, SHA `345b25cee87928b26f7bbde3d64cdb58dcbf644161d6db28de415c4eb52ae381`.
- Manifest de esta auditoría: `docs/knowledge_inputs_v1/k8_post_cert_conflict_budget_audit_manifest.json`.
- Manifest anterior protegido: SHA `d75ce3554d6c61837e7717c50d3f093cd986c58da5c5664b636284d9ddb81e4b`.

Nota de instrumentación: una invocación inicial falló antes de crear output/medir por importar `pypdf` antes de inyectar el site offline. Se movieron esos imports al worker privado. No se descargó nada, no se cambió producto y el fallo inicial permanece en el transcript; no se presenta como medición válida.
