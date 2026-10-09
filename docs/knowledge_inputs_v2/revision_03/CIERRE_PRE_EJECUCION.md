# Cierre de preparación — K8 Certification V2-R3

Estado final: `FROZEN_PENDING_HUMAN_REVIEW`, sin autorización de campañas. Se añade exclusivamente revision_03; V1 y las revisiones previas permanecen byte-inmutables según 499 pins de preservación.

Validación determinista: 24 documentos nuevos, 21 definiciones de caso, denominadores independientes 4K=14 y 8K=21. Cero colisiones literales de IDs, valores opacos, payloads/queries completos y ngramas de ocho palabras contra el inventario histórico. Alcance y hashes completos en evidence/validation-final.json; no se afirma independencia semántica universal.

Checks de preparación: 26 tests sintéticos PASS, con observaciones fabricadas y quality_eligible=false. La primera corrida de preparación (25 tests PASS) también se conserva. Sólo se ejecutaron unittest, compilación sintáctica, validación offline y preflight; no se importó producto durante esa validación ni se contactó Ollama. El preflight final debe mostrar integrity_errors=[] y JOINT_AUTHORIZATION_ABSENT.

`campaigns_consumed=0`, `inference=0`, `retrieval=0`, `admission=0`. Los booleans de gate provienen de scorer.py y no de resultados suministrados por harness. runner.py y nova_adapter.py contienen ya el recorrido real completo; éste sólo fue comprobado con un adaptador sintético y revisión estática de contratos, no con el examen ni con modelo.

Freeze pinnea corpus/gold, funciones de merge/scoring/parser, runner/adaptador, protocolo, response contract, case order/profiles/thresholds, retry rules, identidad/configuración de R2, runtime offline, todos los ejecutables/checks y copias archivadas de evidencia disponibles al sellar. evidence_index.json incluye el SHA del freeze final y las copias verificadas; queda fuera del freeze para evitar un ciclo de hashes. La autorización pendiente también queda fuera por ser un mecanismo aditivo que activa el freeze exacto sin modificarlo.

El perfil conserva exactamente modelo/digest/llm y ventanas de R2. NOT_SUPPORTED de seed conserva la elección R2, con su limitación probatoria explícita en execution_profile_v2_r3.json. No se descubrió ni consultó backend/configuración nueva.

La evidencia original de preparación permanece privada en C:/Users/joseh/AppData/Local/Temp/nova-k8-v2-r3-review-20261008. Sólo copias verificadas se archivan. No se consumió K8 original, post-cert ni V2; no se cambiaron producto, tests/manifests/scorers históricos, framing, caps o reservas. No hay declaración V2 PASS, READY, commit, push ni tag.

Para una autorización futura el humano debe aprobar ambas campañas en un único acto y crear un archivo AUTHORIZED ligado al SHA final, con referencia a su aprobación. El comando de ejecución ya acepta ese archivo, un output nuevo fuera del checkout y un ledger persistente externo; no requiere editar código, perfil ni freeze. En esta etapa se entrega sólo el registro PENDING_HUMAN_AUTHORIZATION.
