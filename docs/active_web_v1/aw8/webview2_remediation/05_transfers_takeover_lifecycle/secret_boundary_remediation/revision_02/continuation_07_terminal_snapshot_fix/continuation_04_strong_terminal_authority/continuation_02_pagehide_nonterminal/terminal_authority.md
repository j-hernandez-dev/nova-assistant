# Conjunto definitivo de autoridad terminal

`SensitiveTerminalReason` contiene sólo SUBMIT=3, CHECKPOINT=5 y ENGINE_WORLD_RETIRE=7; CHECKPOINT significa fin de takeover correlacionado. PAGEHIDE es `SensitiveInputSignal`, como INPUT/CHANGE/BLUR.
El handler fijo PAGEHIDE sigue observando todos los controles sensibles, valores, current y revisions. El parser privado lo encamina a ObserveInput; no crea snapshot, no llama Commit y no produce SHORT_COMMITTED_VALUE por sí solo.
Si el world se destruye, el seal ya implementado captura exact current/revision de la generación owned y Commit(snapshot) conserva la defensa de terminal corto. Si sigue vivo, el checkpoint de fin de takeover obtiene ack/snapshot exactos. Retirement no se modifica ni se reconstruye desde longest/pending.
SUBMIT conserva su evento real y controles del form, sin cambios. Los fences de capture y entrada de takeover no tienen autoridad terminal.
TRANSIENT 1–3 exact-leaf, TRANSIENT >=4 substring, COMMITTED >=4 substring y COMMITTED 1–3 fail-closed: intactos. Registry monotónico y ceilings/expiry intactos. Leaf-boundary y schema-aware redaction intactos. Control plane fuera del redactor.

Sink diagnóstico existente retenido sólo en harness de C. Primera branch ya fallada → scalar MMF; sin nueva campaña, logging por input, taps, sleeps ni retries. El build productivo excluye tests y observer null.
networkEgressControl/publicOnly/available = UNKNOWN; AW8 = BLOCKED; ACTIVE_WEB_CORE = NOT_READY. Los 36 UDF históricos no se mantienen.
