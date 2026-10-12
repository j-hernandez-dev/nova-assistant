# BOUNDED_TRANSIENT_SENSITIVE_VALUE_POLICY — prospectiva
Decisión humana: WV2-B05-C02-PROJECTION-PROOF-SCOPE-003 resuelta mediante política, no mediante reconciliación de los cinco FAIL de nvr23.

## Contrato
- Cada buffer completo no vacío realmente observado se conserva inmediatamente en memoria host-native de la BrowserSession, exact-deduplicated. Known(t+1) incluye Known(t).
- Estado inicial TRANSIENT; promoción irreversible COMMITTED cuando la instrumentación existente observa change/blur, submit, pagehide, retiro del contexto con current pending, o checkpoint antes de completar takeover/publicación.
- Edición/clear/epoch/navigation no borran valores anteriores ni despromueven COMMITTED.
- TRANSIENT 1–3 UTF-16 units: sólo exact-leaf equality, no global substring matching.
- TRANSIENT y COMMITTED >=4 UTF-16 units: matching literal de substring, sin excepciones por word boundary.
- COMMITTED 1–3 UTF-16 units: SECRET_BOUNDARY_UNCONFIRMED, no resume/publicación. Se retiene conocimiento incluso después del failure hasta dispose.
- Ceilings sin cambios: 1024 valores distintos, 64 controles pendientes, 4096 UTF-16 units por valor, 262144 unidades totales, 30 minutos desde activación. Overflow/expiry -> fail-closed, nunca eviction.
- Registry no sobrevive cierre definitivo de BrowserSession/host; no comparte owner ni secrets cross-session.

## Fronteras
La única modificación productiva es SensitiveValueRegistry y el ensamblado de texto en ObservationRuntime: sanea leaves antes de agregar separadores host-owned, tras el checkpoint final. Ningún control-plane discriminator/ref/epoch/ID/status/error/framing se redacciona. Page-derived title/text/names/state/forms/dialogs/URLs/transfer metadata siguen la redacción host-side existente antes del IPC; URL userinfo/query/fragment continúan omitidos.
No cambia SensitiveTracking, TakeoverRuntime, TransferRuntime, schemas, Policy, Grant, driver ni fixtures. No se envían raw values a Python, modelo, audit/log/XML/evidence. Nuevos native tests usan valores dentro del proceso C# y receipts booleanos, no inferencia ni Internet.

## Evidencia prospectiva congelada
Se añaden 14 contract y 10 native casos, independientes de los checks históricos:
short transient exact/substring distinction, long transient, long committed, short committed lengths 1/2/3 fail-closed, promotion/no downgrade, Retire/Checkpoint terminal correcto, buffers históricos/clear, overflow, disposal/independencia; captura real y retención entre edición, navegación same/cross/history, submit, closed IPC control-plane.
Focal obligatorio: los mismos 33 node IDs en orden de nvr23, una vez. Sólo 33/33 habilita inventario completo original 396 + 24 casos nuevos = 420, sobre este mismo candidato sin cambios entre corridas.
Tests y helpers existentes permanecen byte-intactos, incluso los cinco FAIL nvr23. Algunos tests anteriores confirman valores cortos y esperan publicación; si fallan bajo esta decisión, no serán editados ni filtrados para fabricar PASS.

## Claims y límites
Nova Active Web V1.1 no certifica universal information-flow/DLP para cada substring transitorio de credential material. La garantía es: inputs declarados sensibles no automatizables; committed no publicable; transient >=4 literal protegido; transient corto exact-leaf protegido; credential terminal demasiado corto impide resume.
No secure-memory, forensic-erasure ni taint-tracking claim. Registro en memoria .NET volátil, no vault.
networkEgressControl/publicOnly/available=UNKNOWN; AW8=BLOCKED; ACTIVE_WEB_CORE=NOT_READY.
Historia byte-intacta; 36 UDF históricos CLEANUP_UNCONFIRMED sin mantenimiento. Sin bloque06, AW8, commit, push, tag o release.

