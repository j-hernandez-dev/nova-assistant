# Autoridad terminal fuerte — candidato prospectivo

INPUT, CHANGE y BLUR llaman Observe/ObserveInput: conocimiento monotónico, current y revision. No crean snapshot ni llaman Commit.
SensitiveTerminalReason es una unión interna cerrada de SUBMIT, PAGEHIDE, CHECKPOINT (fin de takeover exclusivamente) y ENGINE_WORLD_RETIRE. Los nombres corresponden respectivamente a SUBMIT_CONFIRMED, PAGEHIDE_CONFIRMED, TAKEOVER_END_CHECKPOINT y ENGINE_WORLD_RETIRE.

SUBMIT captura únicamente controles pertenecientes al form del evento real. PAGEHIDE conserva su evento real correlacionado. El private-world producer es fijo y no recibe JS/selectores del modelo.
ENGINE_WORLD_RETIRE mantiene el seal exacto de continuation_03 sin longest/pending ni heurísticas. Late capture posterior al seal conserva el valor conocido y causa sticky fail-closed.
El fin de takeover obtiene snapshot+revision+ack para la misma generación y world uniqueId, verifica coverage y consume Commit(snapshot). Entrada y fences de capture obtienen observaciones correlacionadas sin snapshot/commit.

TRANSIENT 1–3 conserva exact-leaf; TRANSIENT >=4 y COMMITTED >=4 conservan substring. COMMITTED 1–3 sigue SHORT_COMMITTED_VALUE y SECRET_BOUNDARY_UNCONFIRMED. Bounds 1024 valores, 4096 UTF-16 por valor, 262144 total, 64 controles pendientes y 30 minutos: unchanged; no eviction.
El legacy Input(commit=true) se rechaza. Callers sin witness fuerte sólo observan TRANSIENT. No existe HOST_CONFIRMED.

El sink de fallo se compila únicamente por un import test-only durante la campaña histórica autorizada. Guarda una selección final (reason, caller, revisiones y generación opaca), nunca valores/DOM/URLs. Observer productivo permanece null; el schema IPC productivo y sus errores no cambian. No taps CDP, sleeps, retries ni logs por evento.

Sin DLP universal, secure-memory ni taint-tracking. Control plane fuera del redactor y leaf-boundary sin cambios.
networkEgressControl/publicOnly/available = UNKNOWN; AW8 = BLOCKED; ACTIVE_WEB_CORE = NOT_READY. No Block06.
