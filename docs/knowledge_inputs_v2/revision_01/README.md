# V2-R1 — cierre pre-ejecución

Revisión explícita sobre los artefactos V2 congelados; no reescribe corpus, gold, diseño ni protocolo. Añade scorer, runner, tests sintéticos, perfil de ejecución y freeze final. El runner tiene un preflight obligatorio que rechaza drift, falta de identidad exacta del LLM/backend/parámetros/seed o ausencia de autorización conjunta para 4K y 8K. Hasta completar esas decisiones humanas, el estado permanece `FROZEN_PENDING_HUMAN_REVIEW` y no existe estado `READY`.
