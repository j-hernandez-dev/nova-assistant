# K8 Certification V2-R4 — corrección exclusiva de ejecución

V2-R4 se limita al defecto `BACKEND_RUNNER_MISMATCH` autorizado expresamente por el humano: R3 seleccionaba `details.runner` por nombre y agregaba un homónimo de digest distinto. El filtro de R4 exige nombre **y digest**. La ausencia del artefacto exacto en tags o ps sigue bloqueando, y un runner declarado incorrecto para el digest exacto sigue rechazándose. Un runner no declarado conserva el comportamiento no bloqueante de R3.

El runner sólo cambia tres referencias de identidad de revisión: directorio DOCS y dos referencias al nombre del freeze. Todo su recorrido, sus gates, su autorización aditiva, sus parámetros y sus reglas de reserva/retry permanecen iguales. No se oculta, elimina ni modifica el homónimo en Ollama.

Corpus, gold, scorer, casos, thresholds, profiles, protocolo, prompts, response contract, retry rules, runtime y execution profile se heredan como copias byte-idénticas. Mantienen deliberadamente sus filenames y metadata de linaje R3. La nueva revisión y el nuevo freeze están identificados por el manifiesto R4, no por reescribir esos artefactos normativos.

Identidad exacta heredada: `qwen3.5:9b`, digest `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`, Ollama, `llamacpp`, `temperature=0`, `think=false`, `maxIterations=6`, `seed=NOT_SUPPORTED`; ventanas exclusivas 4096 para 4K y 8192 para 8K.

La preparación valida el delta permitido, la preservación de V1/R1/R2/R3 y la validación literal/offline heredada. Los nueve tests nuevos son HTTP metadata sintéticos con red real prohibida. Los 26 checks heredados conservan sus bytes y sólo usan observaciones sintéticas; sus directorios desechables se ubican dentro de evidencia del proyecto, no en Temp del sistema.

El freeze nuevo pinnea toda la cadena heredada y R4, incluidos tests, documentación y evidencia previa al sello. Las comprobaciones posteriores al freeze y el índice SHA son evidencia aditiva, fuera de sus propios pins para evitar ciclos. El preflight de backend posterior sólo consulta tags/ps/show; no prepara producto ni ejecuta casos.

No existe autorización de campañas R4. La autorización R3 queda exclusivamente ligada a su SHA original y debe ser rechazada contra el SHA de R4. Al terminar la preparación se detiene para revisión humana. No se revisan natural_response, ledger timing, cobertura ni metodología; no hay campaña, READY, commit, push ni tag.
