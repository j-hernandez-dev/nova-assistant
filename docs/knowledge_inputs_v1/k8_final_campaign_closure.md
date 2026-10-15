# Cierre formal de la campaña K8 original

## Resolución final

`K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14`

Fecha de cierre: 2026-10-08, 17:42:32 UTC.

La campaña actual queda **cerrada** con 13 casos PASS y 1 FAIL. La única segunda ejecución del examen original se consumió y **no debe repetirse**. No se autoriza una tercera ejecución, una nueva certificación del mismo examen ni una reinterpretación retrospectiva.

`source-conflict` permanece **FAIL / RETRIEVAL_FAILURE**. No se cambia su corpus, gold, scorer, protocolo, freeze ni evidencia. Su conversión posterior en regression test determinista no constituye una nueva evidencia prospectiva de calidad ni altera este resultado.

No se declara K8 PASS ni `NOVA_KNOWLEDGE_INPUTS_V1_READY`.

## Evidencia preservada

- [Resultado de la segunda ejecución](k8_final_execution_resultados.md), SHA-256 `f5ba52e7a317cbbe5922f4a4b517a8e30614c25eab65c68f230f437b74298571`.
- [Manifest de la segunda ejecución](k8_final_execution_manifest.json), SHA-256 `5d03d57dcfc2d63c1748a6a1656b1187161916f8d13e2162a3220000568fa5f3`.
- Raw report: `C:/Users/joseh/AppData/Local/Temp/nova-k8-final-execution-20261008/e2e-second-original/report.json`, SHA-256 `89915b968c6a0a708ca801a2b11be108e3bec06df9aaa279a7dda18065aeafb3`.
- Execution freeze: SHA-256 `de5637405626f7b0650b2f75dab44c0cd5b3a24f62f39bed5776a5b9c35fafab`.
- Freeze original: SHA-256 `2c95d25b26d90e11e1333a5d5f1db6ae45fe09813b06a094b9d1649e9a6009e9`.

Antes del cierre se comprobaron read-only 17 pins del examen, 241 del producto, 1931 del repositorio, 585 referencias históricas y 138 artefactos raw. Todos conservan sus hashes. La historia original 5/14 y Repairs V1–V6 permanece intacta.

Branch `main`; HEAD `717a24218dea7fb60d8b630896d653e39091bc7b`. Working tree previo preservado y staging vacío; tags anteriores intactos. No inferencia, tests, producto ni arquitectura modificados para este cierre. Estos nuevos archivos son un registro aditivo, no sustituyen evidencia histórica.

## Tarea independiente autorizada

Nombre: **K8 Post-Certification Remediation — Multi-source Conflict Retrieval**.

No es Repair V7 y no permite ejecutar nuevamente el E2E K8 original. El éxito de la remediación únicamente puede declararse `K8 POST-CERT REMEDIATION PASS`, nunca K8 PASS retrospectivo.

Alcance autorizado:

- Auditar KnowledgeQueryPlan y retrieval para separar factual subject, comparison/multi-source intent, source-cardinality/diversity intent, output controls y epistemic controls.
- Mantener lexical floor `>0.5`; no sustituir el análisis por blacklist de palabras del caso observado.
- Admitir varias fuentes relevantes distintas cuando la petición sea comparativa y existan esas evidencias, preservando scope/revision/current/delete.
- Añadir regression determinista del fallo histórico, separado de calidad.
- Congelar prospectivamente corpus nuevo con IDs, textos, valores y gold independientes: dos fuentes concordantes/conflictivas, tres fuentes, relevante+distractores, single-source, comparación EN/ES, negativos, deleted/superseded y cross-workspace.
- Exigir R@5=100%, P@1=100%, required multi-source admissions=100%, abstention>=95%, scope/current/delete=100% y false source expansion=0 en críticos.
- Ejecutar Knowledge, MEMORY, Core/guard, Desktop y HEAD completos después; clasificar los fallos sin ocultarlos ni introducir skips/xfails para obtener verde.

No READY, commit, push ni tag. Al terminar la nueva tarea se detiene para revisión humana.

