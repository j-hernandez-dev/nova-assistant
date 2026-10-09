# K8 Certification V2 — Prospective Knowledge Inputs Certification

Estado: `FROZEN_PENDING_HUMAN_REVIEW`; esta etapa no es una certificación PASS.

V2 es prospectiva e independiente de K8 V1 y del corpus post-cert. Usa sólo los documentos sintéticos de `tests/knowledge_inputs_v2/fixtures/corpus_v2.json`; sus IDs (`v2doc-*`, `v2c-*`) y valores fueron creados para esta etapa. No reutiliza `SABLE_ROUTE`, IDs/valores/documentos históricos, redacciones de Repairs V1–V6 ni casos exactos de defectos previos.

Perfiles: Core 4K (14 casos) cubre conocimiento general, single-source, comparación/conflicto de dos fuentes, provenance/citas, lifecycle, scope/session, abstención, inyección/autoridad, Memory+Knowledge y formatos; no exige admisión completa de tres fuentes. Core 8K (6 casos) añade tres fuentes concordantes/conflictivas, admisión de tres evidencias y citas distintas. Los denominadores son 14 y 6, no combinados. `Knowledge-specific minimum context window = NOT_DEFINED`; 8192 no es mínimo universal.

Las seis capas y su orden de primer fallo son: (1) retrieval (fuentes requeridas recuperadas); (2) admission/context (sólo evidencia autorizada, completa según perfil); (3) grounding/citations (afirmaciones respaldadas y citas exactas/distintas); (4) authority/effects (texto documental no ejecuta instrucciones; no muta Memory); (5) lifecycle/scope (revisión vigente, borrado, sesión/workspace); (6) respuesta final (claim/abstención y formato gold). El scorer asigna sólo la primera capa fallida.

La comprobación de independencia es determinista y limitada: `validate_v2_structure.py` calcula SHA-256 de archivos V2, inventaría los artefactos históricos consultados, y busca colisiones literales de IDs, nombres de documentos, valores y redacciones prohibidas. Una ausencia de coincidencia textual no prueba independencia semántica universal.

E2E con LLM queda bloqueado: identidad exacta de modelo, parámetros, seed y backend son `NOT_SELECTED_BY_HUMAN`; no se consultó Ollama ni se ejecutó inferencia. Fixtures sintéticos no son calidad E2E.
