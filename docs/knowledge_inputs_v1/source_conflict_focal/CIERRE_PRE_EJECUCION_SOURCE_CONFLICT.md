# Cierre pre-ejecución — evidencia focal source-conflict (§64.35)

Estado: `FROZEN_PENDING_HUMAN_AUTHORIZATION`. Preparación terminada; el
intento de calidad **NO se ha ejecutado**. Preflight operacional **BLOCKED**
por modelo no residente. No se ha creado `AUTHORIZED`.

Freeze SHA-256 exacto:

`549adb90296c8eb92dec6fb70994c1e4d61d62d611670764e937531c44f83364`

Este expediente sólo prepara evidencia prospectiva para criterion 35.
La auditoría aceptada permanece **38 SATISFIED / 1 NOT_EVIDENCED / 1 BLOCKED**.
Criterion 1 sigue dependiendo de 35. No se reauditaron los otros 38.
No es K8 V2, otra revisión V2, otro benchmark o certificación de contexto.

## Paquete revisable congelado

- [Diseño](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/DESIGN.md)
- [Corpus](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/corpus.json)
- [Fixture Selenvyr](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/fixtures/Selenvyr_Seal_Record.txt)
- [Fixture Orquendel](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/fixtures/Orquendel_Seal_Record.txt)
- [Gold y bindings reales](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/gold.json)
- [Identidad/configuración](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/execution_profile.json)
- [Protocolo y reglas de incidente](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/protocol.json)
- [Reglas naturales del scorer](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/SCORER.md)
- [Scorer ejecutable](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/source_conflict_focal/scorer.py)
- [Runner one-shot completo](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/source_conflict_focal/runner.py)
- [Bridge productivo/evidencia](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/source_conflict_focal/bridge.py)
- [Freeze completo: 671 pins](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/freeze.json)
- [Esquema de autorización; NO es autorización](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/authorization_schema.json)

## Caso único y gold prospectivo

`ki35-scf-veltrion-20261009`. Ambas fuentes afirman exactamente el mismo hecho:
el código del sello `VELTRION_CIPHER`. Selenvyr afirma `SEAL_ZAVREX_583Q`;
Orquendel afirma `SEAL_JUMFIK_927R`. No existe soporte para preferir uno.

| Fuente | sourceId | revisionId | chunkId |
|---|---|---|---|
| Selenvyr | 0987d75f-52e6-4521-b6f7-511dddfde5a2 | 8474533f-166c-4818-adab-87bb54050c54 | 3866c7d5-1fbf-52e1-b3e3-a9bf1430aaff |
| Orquendel | 52a07310-b1c4-4b73-b582-15cc40cf3d43 | de277f85-599b-4837-875b-0c878a88a0d9 | 4981371e-839f-548d-9c41-b7ff8028f8a3 |

Son imports host productivos independientes, WORKSPACE real, READY/current,
sin tombstone; un chunk completo por fuente, locator TEXT_LINES 1..1.
Seed cerrado, Memory privado vacío y workspace vacío están pinneados.
Un único propietario físico; ejecución copia el seed y conserva IDs y la
identidad de workspace, sin reaplicar imports para regenerar gold.

Consulta comparativa exacta, en el mismo idioma que los documentos:

> What do the two sources say about VELTRION_CIPHER? Report both conflicting values. Cite the sources. Do not choose one as truth. Do not write files. Do not use tools.

Validación estática del QueryPlan existente: diversidad=true, cardinalidad=2,
términos documentales veltrion/cipher. No se consultó retrieval para elegir
el caso. Sin cross-lingual, multitema, r1/r2, attachmentRef o selección oculta.

Gold exige ambas fuentes recuperadas y admitidas, ambos valores completos
en respuesta natural y atribuidos a sus citations reales, conflicto explícito,
sin elección arbitraria, dos targets distintos/válidos y provenance exacta
source/revision/chunk/locator. No exige JSON. Files, Memory y lifecycle
before/after deben coincidir; sin autoridad documental ni efectos no autorizados.

Scorer deriva gates desde observaciones reales y conserva primera capa única
y secundarios. Su recognizer natural es acotado y publicado: una paráfrasis
no reconocida puede fallar el scorer y no demuestra por sí misma un defecto de
Nova. No habrá cambio de reglas o adjudicación para convertir el resultado
después de observarlo. Un tool request rechazado no constituye autoridad.

## Identidad y configuración

Únicamente perfil operacional **8K**, no 4K:

- qwen3.5:9b; digest `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`.
- Ollama 0.40.2; runner declarado del artefacto exacto: llamacpp.
- context=8192; temperature=0; think=false; maxIterations=6.
- seed=NOT_SUPPORTED; no seed enviado; setting aceptado heredado.
- Presets productivos efectivos: top_p=0.95, top_k=20.
- Python 3.14.6, -B; ejecutable/runtime/dependencias pinneados.
- System natural original K8 V1 byte-idéntico; no system ni response JSON V2.
- Sin embeddings, search remoto, tuning, overrides de budgets o cambios Nova.

## Preflight real después del freeze

[Registro local aditivo](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/docs/knowledge_inputs_v1/source_conflict_focal/preflight_readonly.json);
[original crudo externo](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/preflight/c24776fee236489d85fabfc6972887a0/preflight.json);
[recibo de red](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/preflight/c24776fee236489d85fabfc6972887a0/network_receipt.json);
[requests de metadatos](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/preflight/c24776fee236489d85fabfc6972887a0/network.jsonl).

- 671 pins verificados: **sin drift**.
- Runtime y parámetros efectivos: coinciden exactamente.
- Artefacto instalado: nombre + digest exactos; llamacpp.
- `/api/ps`: ningún modelo residente.
- Resultado: **BLOCKED**, `EXACT_MODEL_NOT_INSTALLED_AND_RESIDENT`.
  El submotivo observado es **no residencia**, no identidad instalada incorrecta.
- Autorización: NOT_CREATED; no ledger/reserva de calidad focal.
- Red: GET tags, GET ps, POST show, GET version; chat/generate/embed=0.

La copia local del preflight es un registro JSON aditivo para lectura;
el original externo conserva sus bytes y SHA. Ninguno modifica el freeze.
No se cargó el modelo ni se llamó inferencia vacía. No debe ejecutarse el Turn
hasta aprobación humana separada y preflight operacional limpio.

## Evidencia de preparación y validación

- [Host import real / receipt](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/preparations/ki35-0d22fcf791d747439c446ef5c167b132/preparation_receipt.json).
- [Operaciones host](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/preparations/ki35-0d22fcf791d747439c446ef5c167b132/host_operations.jsonl).
- [Model requests preparatorios: lista vacía](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/preparations/ki35-0d22fcf791d747439c446ef5c167b132/model_requests.json).
- [Reapertura de copia sin Turn: bindings/lifecycle/Memory PASS](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/state-smoke/812da173ad55467d9b196a8c631bbdbc/state-smoke.json).
- [No reutilización: 313 artefactos históricos, cero colisiones](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/offline-validation/11a272c6efb54aa0960c65bd88586265/validation.json).
- [35 tests sintéticos PASS; cero failures/errors/skips](C:/Users/joseh/Downloads/nova-local-cli/k8-certification-evidence/source-conflict-focal/synthetic-tests-sealed/tests.xml).
- [Tests congelados](C:/Users/joseh/Downloads/nova-local-cli/nova-assistant/tests/knowledge_inputs_v1/source_conflict_focal/test_scorer.py).

La comprobación de estado terminó PASS antes de un bloqueo de identidad por
no residencia; no sometió un Turn. No se confunde con evidencia E2E del criterio.
Se conservan XML de las iteraciones de desarrollo; el XML sellado corresponde
al código/gold congelados y es el resultado final sintético. Ningún test de
scorer aportó inferencia ni retrieval/admission productivos.

Contadores **nuevos de este expediente**, no contadores históricos reiniciados:

```ini
quality_attempts=0
inference=0
retrieval=0
admission=0
v2_campaigns_new=0
```

Se realizaron dos imports preparatorios y una lista host, no consultas del
examen. 2083 archivos preexistentes verificados sin modificación;
los 538 archivos de evidencia V2 original continúan con SHA idénticos.
Ledger V2 histórico intacto: campaigns_consumed=2, inference=76,
retrieval=32, admission=32. HEAD permanece `717a24218dea7fb60d8b630896d653e39091bc7b`.

## Límite de ejecución y siguiente decisión humana

No se crea AUTHORIZED en esta etapa. Después de aprobación explícita, el
artefacto aditivo debe ligar exactamente freeze SHA, case_id, perfil 8K,
one_quality_attempt=true y no_tuning=true con execution_id/timestamp/ref humana.

Único Turn de calidad bajo la Application normal:
host import congelado → retrieval real → admission real → modelo local real
→ respuesta natural → citation registry productivo → score/evidencia.
Generations del mismo Turn hasta maxIterations no son reintentos de calidad.
Ledger exclusivo antes de submit; ningún retry automático.

Si falla, se conserva FAIL y se detiene, sin reparar y repetir.
Sólo incidentes genuinos demostrados pueden separarse por las reglas ya
congeladas; no habilitan un replay automático.

Se mantienen literalmente:

- K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14
- K8 POST-CERT REMEDIATION PARTIAL
- 4K historical quality = 10/15
- KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS
- K8 CERTIFICATION V2 FAIL

No READY, commit, push ni tag. **Detenido para revisión y autorización humana.**
