# K8 final — preflight bloqueado, sin inferencia

Estado global: **K8 PARTIAL**. Estado de esta autorización: **BLOCKED_BEFORE_INFERENCE**.
No hay una segunda campaña ni resultados nuevos de calidad. Los 14 casos siguen pendientes; no se reportan como 0/14 FAIL. La repetición única autorizada no se ha consumido.

## 1. Baseline y conservación

- Branch: main.
- HEAD: 717a24218dea7fb60d8b630896d653e39091bc7b.
- Captura UTC: 2026-10-08T16:08:42.8982440Z.
- Working tree inicial: 314 entradas previas; staging vacío.
- Windows 11, build 26200, NTFS local, HOST_UNISOLATED.
- Python 3.14.6, ejecutable C:/Users/joseh/AppData/Local/Python/pythoncore-3.14-64/python.exe.
- No se restauró, limpió, stageó ni alteró ningún archivo previo. No cambios de producto, tests, protocolos, prompts, corpus, gold, scorer, thresholds o arquitectura.

La captura completa, hashes esperados/actuales y tags están en [preflight_v1.json](k8_final_evidence/preflight_v1.json).

## 2. Integridad del examen original

Los pins de corpus, protocolo, fixtures, scorer/harness y arquitectura coinciden byte a byte con la evidencia original:
 
| Artefacto | SHA-256 |
| --- | --- |
| Corpus K8, incluido gold/14 casos | 832be39fa3efa475cd74b89c8f5d1632e445f5a6a67cecb72833d4f12814cd1a |
| Protocolo original | c0eb231bb2cbc812e49524cd295dc237c29265d4b4671cf7c2d97c285e11c092 |
| Harness E2E completo, incluido grounded_score | 27b745dc3a6a087c61156c10ed47ed03bd6f7df0c4cc5f787fdfda5645d46c4b |
| Freeze E2E original | 2c95d25b26d90e11e1333a5d5f1db6ae45fe09813b06a094b9d1649e9a6009e9 |
| Freeze standalone original | 84512b3fe5042afd2cc46fcd74fc0f1385ba7156b8f04d048f5126b0592d97ba |
| Arquitectura Knowledge | 417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432 |

Se verificaron las 6 referencias del freeze standalone sin mismatch. Del freeze E2E, 183/194 referencias coinciden; las 11 diferencias son archivos del producto reparado, no cambios al examen.

## 3. Bloqueo demostrado

El freeze E2E original no fija solamente el examen: también fija hashes históricos del producto. El harness aplica **todos** esos pins en `verify(freeze)` antes de acceder a Ollama o iniciar los casos, en run_k8_e2e.py:48–50 y :117.

Los archivos con pin histórico incompatible con el producto actual son:

- local_cli/agent.py
- local_cli/application/context.py
- local_cli/application/knowledge_context.py
- local_cli/application/knowledge_retrieval.py
- local_cli/application/providers.py
- local_cli/application/session.py
- local_cli/application/tool_runtime.py
- local_cli/infrastructure/knowledge_extraction.py
- local_cli/infrastructure/knowledge_retrieval_sqlite.py
- local_cli/sub_agent.py
- local_cli/tools/agent_tool.py

Son diferencias preexistentes al inicio de esta tarea. La comprobación independiente del estado V6 verificó 320 referencias sin mismatch: 299 pins previos ajustados exclusivamente a los dos deltas documentados de V6, más sus 21 artefactos finales. No se clasifica esta divergencia como nueva regresión del producto ni como modificación del corpus.

Se ejecutó **sólo el verificador original**, no `main` ni `run_campaign`:

~~~powershell
$env:PYTHONPATH='C:/Users/joseh/AppData/Local/Temp/nova-k3-pdf-repair-20261007/dependencies'
python -B -c 'import json;from pathlib import Path;from tests.knowledge_inputs_v1.run_k8_e2e import verify;verify(json.loads(Path("docs/knowledge_inputs_v1/k8_evidence/e2e_freeze_v1.json").read_text()))'
~~~

Inicio UTC: 2026-10-08T16:09:26.5941916Z. Fin UTC: 2026-10-08T16:09:27.9399688Z. Exit: 1.

Resultado literal:

~~~text
ValueError: FROZEN_FILE_CHANGED: local_cli/agent.py
~~~

Clasificación: **HARNESS_CONTRACT_CONFLICT**. El verificador funciona conforme a su implementación; el conflicto consiste en ejecutar producto reparado conservando simultáneamente sus pins históricos como requisito de ejecución. No es evidencia de fallo del modelo. No hubo llamadas a Ollama, carga/descarga de modelos, inferencia, red pública ni retry.

Una invocación preliminar del diagnóstico tuvo un error de sintaxis PowerShell, antes de iniciar Python. La invocación corregida arriba sólo comprobó hashes; ninguna inició la campaña.

No se omitió, monkeypatcheó ni debilitó el verificador. No se cambió el freeze ni se repinneó silenciosamente el producto.

## 4. Historia preservada

- [K8 original PARTIAL, 5/14](k8_resultados.md), [manifest](k8_manifest.json).
- [Repair V1](k8_repair_resultados.md), [manifest](k8_repair_manifest.json).
- [Repair V2](k8_repair2_resultados.md), [manifest](k8_repair2_manifest.json).
- [Repair V3](k8_repair3_resultados.md), [manifest](k8_repair3_manifest.json).
- [Repair V4](k8_repair4_resultados.md), [manifest](k8_repair4_manifest.json).
- [Repair V5](k8_repair5_resultados.md), [manifest](k8_repair5_manifest.json).
- [K8 REPAIR V6 PASS](k8_repair6_resultados.md), [manifest](k8_repair6_manifest.json).

Se verificaron los 16 manifests históricos pinneados por V6 sin cambios; el manifest V6 se identificó por su SHA actual. Las 30 referencias raw de la campaña original (attempt, report y requests/result de sus 14 casos) coinciden con sus hashes históricos. El detalle individual está en el preflight.

No se ejecutaron regresiones de cierre: están condicionadas al PASS de la segunda campaña, que aún no comenzó. La regresión V6 publicada permanece histórica, no se presenta como nueva regresión de esta tarea.

## 5. Gate y autorización pendiente

| Requisito | Estado |
| --- | --- |
| Examen original byte a byte intacto | PASS |
| Pins del producto V6 intactos | PASS |
| Freeze original y evidencia histórica conservados | PASS |
| Verificador original acepta producto actual | BLOCKED |
| Segunda campaña original 14 casos | NOT_EXECUTED |
| Scoring original de la segunda campaña | NOT_EVALUATED |
| Regresiones posteriores a E2E PASS | NOT_EXECUTED |
| K8 PASS | NO DEMOSTRADO |

Para continuar se necesita autorización explícita para reconciliar **sólo los pins de producto de ejecución**, en un artefacto separado: conservar el freeze histórico íntegro y los pins del examen original, vinculando la nueva ejecución al producto V6 ya verificado. Esto no implica cambiar datos, protocolo, scorer, prompts, thresholds ni producto. **No se creó ni aplicó esa reconciliación.**

DOCUMENT_SEMANTIC_PROFILE, MEMORY SEMANTIC_PROFILE y OCR_PROFILE permanecen NOT_CERTIFIED. No evaluación READY, Repair V7, commit, push o tag. Se detiene para revisión humana.

