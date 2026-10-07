# M8 — preflight de calidad final BGE-M3

Baseline: main, HEAD 468d213ede2fa52f6b2588ebaa1191b83669ccb8; working tree
preexistente de contexto/MEMORY conservado. Sin commit, push, tags, READY o CI.

Gate operacional cerrado PASS, implementación intacta. Esta evaluación no
optimiza producto, RRF, QueryComposer, floor, caps, soft350/hard600/guard50,
BGE ni su espacio. Core/SECURITY siguen vigentes; auditoría histórica no
prevalece sobre MEMORY §37 M8/MEM1-OD-07 resuelto.

Baseline antes de nuevos fixtures: 723 passed / 59.00 s, sin inferencia externa.
Contratos finales de harness/estructura: 734 passed / 56.51 s, cero skips/xfail.

## Dataset redactado antes de inferencia

m8-bge-final-heldout-v1:
- 90 recuerdos normales: 60 gold distintos y 30 distractores cercanos.
- 60 positivos: 12 exact-key, 18 lexical, 30 paraphrase.
- 12 negativos ordinarios/no-evidence, separados de métricas R@3/P@1.
- 12 paráfrasis cross-language: 6 ES→EN y 6 EN→ES.
- exact-key usa etiqueta lingüística KEY, no afirma idioma natural.
- validación offline: IDs/gold/keys/texts únicos, gold existente; cero
  coincidencias textuales con DEV/históricos/workloads operacionales anteriores.
- caracterización textual, sin score/modelo: 23/30 paráfrasis con cero tokens
  de contenido compartidos (filtro funcional estático vigente), 6 con uno y
  1 con dos. No se seleccionaron ejemplos mediante scores o inferencia.
- gold/accepted sólo para comparar outputs, no para generar embeddings/prompts.
- no invariantes críticos usados para inflar ranking; requieren campaña aparte.

SHA-256 del dataset antes de medir:
97b8d9e98ac74ad4b54efb31f35977eb4fe758ecef45d7e75bf044b2aafc7dfe

Backend observado por discovery sin inferencia: Ollama server 0.40.0;
BGE-M3:latest instalado y residente, embedding/bert/F16/566.70M/1024D;
digest 7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab.
qwen3.5:9b instalado; no se inicia chat antes de que standalone pase.
Espacio esperado:
ollama-810a779df15ccf6b50ccd4e4da669cd99ae7da990e5585a42393640cc4e9fcd9.

## Protocolo y criterio fijados antes de medir

Se reutilizan sin cambios run_m8_bge, seed/create/retrieval_rows/answer,
m8_evaluation y standalone_verdict. Wrapper nuevo sólo selecciona el dataset,
verifica el mismo espacio/digest, prohíbe preparación fría automática y
registra subsets ES/EN/cross-language; un marcador exclusivo limita un
standalone attempt por freeze. Todos los archivos existentes del freeze
operacional se verifican y se agregan nuevos artefactos antes de la medición.

R@3 >=85%; P@1 >=90%; paraphrase R@3 gain >=5 pp frente a lexical;
sin reducción agregada respecto de lexical conforme al verdict ya fijado.
WARM real y sin error en todas las consultas, hard600 conservado, p95
publicado sin quitar tails. Negativos standalone no prueban abstención LLM.

Si cualquier gate standalone falla: resultado intacto, M8 PARTIAL/FAIL,
sin nuevo dataset, retest ni E2E. Si pasa: E2E normal local independiente
4K>=85%, 8K>=90%, 16K>=90%, negación/no-evidence>=95%; evidencia literal
de gold en MemoryCapsule y disponibilidad semantic real, residencia BGE
entre Turns con qwen3.5:9b, sin rewarm oculto. Después de E2E exitoso:
campaña crítica y regresión MEMORY/HEAD completas, cero fallos críticos.

No resultado de calidad aún al escribir este preflight.

