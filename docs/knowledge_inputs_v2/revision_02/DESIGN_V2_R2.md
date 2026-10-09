# K8 V2-R2 — diseño corregido

V2-R2 es una revisión explícita de V2-R1. V2-R1 y V1 permanecen intactas. Se corrigieron conflictos documentales reales, estados de scope/session y lifecycle en el store fixture, revisiones superseded/active, tombstone de Nube, claims heterogéneos y consulta retrieval-determinable de tres materias.

El gold ya no contiene criterios abiertos: cada caso fija facts, claims prohibidos, abstención, citas permitidas/prohibidas, efectos, revisión vigente y scope. El scorer deriva gates desde esos campos; no hay revisión humana posterior de una respuesta vaga. Authority/injection y lifecycle/tombstone son gates distintos.

El digest exacto se recuperó del protocolo histórico K8: `qwen3.5:9b`, SHA `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`, Ollama/llamacpp. `seed=NOT_SUPPORTED` porque el protocolo histórico no lo fijó y esta etapa no consulta el backend. Campañas 4K y 8K siguen sin autorización.
