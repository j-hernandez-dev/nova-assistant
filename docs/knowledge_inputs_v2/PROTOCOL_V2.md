# Protocolo congelado V2

Sólo se permite una campaña final por perfil, en orden lexicográfico de `case.id`: 4K `v2c-001` a `v2c-014`, luego 8K `v2c-015` a `v2c-020` si ambas campañas son autorizadas. No hay tuning posterior ni selección adaptativa. Antes de ejecutar se debe registrar modelo/configuración exactos; hasta entonces el estado es bloqueado por revisión humana.

Un intento de caso es la unidad conservada. Retry permitido únicamente por incidente de harness/entorno previamente definido: proceso no iniciado, timeout del harness, archivo temporal ilegible, crash del adaptador o pérdida de transporte, nunca respuesta incorrecta, latencia del modelo, retrieval vacío o fallo de gold. Máximo un retry inmediato; se conserva el intento original y la causa. Un incidente no consume campaña si impide inicializarla; una vez emitido cualquier resultado de modelo, la campaña se consume completa y no se reejecuta.

PASS de caso requiere todos los gates: retrieval, admission, grounding/citations, authority/effects, lifecycle/scope y respuesta final. El primer fallo determina clasificación; los demás se registran como secundarios. PASS de perfil requiere 100% de gates obligatorios y 0 incidentes no resueltos, usando el denominador del perfil. No se puede declarar PASS en esta etapa porque no hubo campaña.

La validación estructural incluida en esta entrega sólo lee JSON/texto y genera hashes; no llama a producto, retrieval, admission, modelo, runners V1 ni Ollama.
