# AW6 — Auth takeover y transfers

**AW6 = PASS**, limitado al cierre normativo de §35: **«Cierre: credentials no pasan al agente.»** No declara Active Web READY ni disponibilidad pública. Sin AW7.

## Baseline y preflight

Branch `main`, HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`. Working tree sucio heredado, preservado; index vacío, cinco tags intactos. `baseline_freeze.json` fija 2181 tracked y 77 untracked heredados. AW5 PASS e integridad de sus pins se verificaron antes de modificar. Arquitectura SHA `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`, sin cambios. Auditoría/findings son contexto, no reemplazan la arquitectura. No contradicción material ni decisión normativa nueva.

Preflight: takeover/selección/staging no existían; AW1 lifecycle/owner/quotas/cancel, AW2 refs/redaction/freshness, AW3 Policy/Approval/claimed Grant/ToolRuntime/audit y AW4 broker se reutilizan. AW5 proporciona Chromium efímero. Se reutiliza exclusivamente el lector host endurecido K2 `LocalHostFileAcquisition`: no Source, store, parser, attachment authority ni import Knowledge. Baseline: **628 PASS / 1 FAIL**, exit1; fallo HOME/USERPROFILE heredado, preservado.

Entorno: Windows 11 build26200, C: fixed local NTFS, HOST_UNISOLATED; Python3.14.6 absoluto; venv test AW5 externo reutilizado, pytest9.1.1, Playwright1.63.0, Chromium153.0.8010.12/rev1243 ya instalado. Ninguna descarga/dependencia/config global nueva, modelo/cloud/sitio externo. Outputs privados fuera de Git: `C:/Users/joseh/AppData/Local/Temp/nova-aw6-20261009T202326Z`.

## Entregables y gate, uno por uno

| Requisito AW6 | Componente → evidencia | Estado |
| --- | --- | --- |
| Human takeover (§10) | `BrowserTakeoverService` + manager/port: reason LOGIN/CAPTCHA/USER_INTERACTION, actor opaco host verificado, pausa global agentic, host finaliza; native takeover/expiry/headless fail-closed | PASS |
| Upload host refs (§20) | `HostFileSelectionRef` + transfer service: owner/session/epoch, identity/revision/size/SHA/MIME/nombre; exact approval ligado a origin y element; relectura endurecida antes del efecto, bytes privados al SDK; cambios rechazados | PASS |
| Download staging (§21) | slot de download exactamente aprobado, eventos drive-by/redirect no aprobados cancelados; staging privado acotado fuera del workspace, SHA y ref opaco, owner/discard, deadline/cancel/oversize sin publicación tardía ni retry | PASS |
| Redaction (§19) | valores password/OTP/hidden/storage no se capturan; SecretRedactor existente; upload de secreto registrado se deniega; filename saneado, sin filepath/contenido/cookies en ToolResult/audit | PASS |
| browserContextEpoch | fin host incrementa epoch e invalida todas las observations/elementRefs y selections previas; nueva observación requerida, sin ampliar grants | PASS |
| **credentials no pasan al agente** | takeover Chromium headful con interacción sintética host-only: password/cookie fuera de capture/ToolResult/audit; no API de autofill/cookies/storage/model selectors; refs anteriores rechazados | **PASS, alcance de fixtures y contratos** |
| Compatibilidad/regresión | 0 nuevos FAIL/ERROR/skips/xfails/exclusiones; Core conserva su único FAIL heredado, sin recalificarlo | PASS de ausencia de regresiones AW6 |

Takeover exitoso significa **handoff solicitado**, no login probado por Nova. `HUMAN_AUTHENTICATED` es señal reportada por el host, no grant ni garantía remota. Headless sin UI termina UNKNOWN y conserva pausa; no simula autenticación ni retoma automáticamente. Toda acción modelada en las pruebas usa Application/ToolRuntime/Policy, ApprovalGate exacto, grant claim y audit durable existentes. Host controls de selección/fin no son permisos emitidos por web content.

Limits: bytes/selecciones/downloads finitos provistos explícitamente por el host, sin inventar defaults normativos. Fixtures 128/256 bytes; límites/action deadlines del manager se conservan. Un download usa slot/callback one-shot; el callback no toma lock de lifecycle desde el worker, usa token/deadline de la lease y descarta staging si vence durante publicación. SDK puede recibir temporalmente bytes privados antes de cancelar un drive-by; no se afirma cero bytes ni sandbox OS.

## Archivos y contratos

Producto nuevo: `local_cli/core/active_web_transfers.py`, `local_cli/application/browser_takeover.py`, `local_cli/application/browser_transfers.py`, `local_cli/infrastructure/active_web/download_staging.py`.

Delta mínimo: `local_cli/application/active_web.py` (pausa/epoch), `local_cli/application/browser_actions.py` (planes opt-in), `local_cli/infrastructure/active_web/playwright_adapter.py` (handoff/bytes-upload/slot-download). Port, DTOs y errores tipados internos; schemaVersion1 en refs/views, sin DB/migraciones, engine/paths fuera de Core. `UploadBuffer` y callback son privados, no wire público.

Tests nuevos: `test_aw6_contracts.py`, `test_aw6_engine.py`. `ci/pytest_contracts.json`: exclusivamente 22 nuevas clasificaciones fail-closed; 15 funciones portables, 7 funciones native-local. Remover sólo esas adiciones recupera exactamente SHA anterior `6300d1d2768a4d4e8f2abf43d4bf34b9dd3e54a0db64683b6b421b1fa95d498f`. Ningún workflow/runner/seletor histórico eliminado. No es AW7 ni instalación browser en CI.

Datos de descargas permanecen privados/inertes. Export/save host picker e import Knowledge explícito son acciones **separadas**, no ejecutadas ni expuestas automáticamente aquí; frontend wiring corresponde AW7. Discard host-only está disponible. MEMORY, Knowledge, provider credentials, grants/schema Security, Core loop y Desktop no se modificaron.

## Pruebas y regresiones

Producto/test frozen en `product_freeze.json` antes de las verificaciones finales.

| Gate | PASS | FAIL | ERROR | SKIP | Exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| AW6 dentro del focused frozen | 47 (35 portable + 12 Chromium real) | 0 | 0 | 0 | 0 |
| Active Web AW0–AW6 focused frozen | 566 | 0 | 0 | 0 | 0 |
| Core completo, selección positiva vigente | 3280 + 53 subtests | **1 heredado** | 0 | 7 históricos | **1** |
| Security | 615 | 0 | 0 | 0 | 0 |
| Memory | 791 | 0 | 0 | 0 | 0 |
| Knowledge | 1015 | 0 | 0 | 0 | 0 |
| Desktop | 68 | 0 | 0 | 0 | 0 |
| TypeScript noEmit | correcto | 0 | — | — | 0 |

Focused se superpone con Core: no sumar como denominador independiente. XML Core3341 incluye 3288 instancias +53 subtests, no 3341 tests primarios. Los siete skips son exactamente los nodeids de AW5; no skips/xfails nuevos. Collection guard PASS, inventory4001/unclassified0. No normal-HTML/scripted-provider equivalente a LLM: no campaña LLM requerida por AW6.

Corridas de desarrollo preservadas: 158/0; **36/6 HARNESS_BUG**; 42/0; 47/0. Se corrigieron sólo seis assertions nuevas aún no congeladas (mappingproxy → wire válido, campo `outcome`, epoch del Session), no producto para ocultar FAIL ni assertions históricas. Los XML y trace SHA conservan los fallos.

Core FAIL: `tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`. **PREEXISTING_CORE_HARNESS_DEBT / NON_BLOCKING_FOR_AW6**. HOME privado difiere de USERPROFILE en PowerShell; mismo fallo antes y después. Bash tool/test/runner tienen exactamente SHA baseline. No repair/skip/xfail/filter; exit1 real intacto. AW6 cierra por cumplir su gate y ausencia de regresiones introducidas, **no** porque todo Core sea verde ni porque desaparezca deuda heredada.

`test_results.json` contiene comandos PowerShell completos, argv/setup, runtime, start/end JUnit, denominadores, fails/skips y hashes. End derivado timestamp+suite.time, no SLA total adicional. Outputs/JUnit/basetemp fuera de checkout, plugins/config privados deshabilitados. Native receipts sintéticos incluyen request/observation/approval/results/audit y filesystem checks, sólo en runtime externo; no logging productivo de conversaciones.

| Output | SHA-256 tests.xml |
| --- | --- |
| final-core | `6b97f4524d018094ec5c120deb22cf1ecf3d5ff8e2a3614bddc23fca42456574` |
| final-knowledge | `8157fb48e607aa6d7a088487d46a9a89f8f0255a3cfc386de24d5a31b1a89c46` |
| final-memory | `2fa958b8e068894e376264d10bbac944d85725f9b52f47995dc4eb36d310a9c8` |
| final-security | `91e06253f1bf99f962c971df3c8730540325fa2df5ed974374456ea4c8c724fd` |
| focused-final | `52eb1c6c8c3e7ad3ff6843b528bbc2faa71419b20b39ce5a7797d7ea5c980d44` |

No performance threshold nuevo en AW6: bounds/deadlines/cancel/unknown son contratos probados; duración de tests no es SLA universal.

## Integridad y límites

`integrity.json`: cuatro deltas heredados autorizados (tres Application/adapter + inventory), 0 drift inesperado, 0 frozen drift; arquitectura/docs históricas intactas; 225 artefactos raw AW0–AW5 revalidados, 0 drift. Cinco tags/HEAD/branch y staging intactos. Post-run snapshot: 0 procesos Chromium/driver propios residuales, sin matar procesos del usuario.

`invariant_matrix.json` traza los 50 AW-INV; preservación/deferral ≠ 50 certificaciones globales. Actor approval/takeover es sintético y la interacción UI se realiza por código **del harness host-only**, no login productivo ni certificación de humano/CAPTCHA/site real. Redacción no es DLP universal ni cifrado. FixtureAdmission sustituye sólo endpoint de server.test; PUBLIC_ONLY productivo no se debilita. No certificación egress exclusivo/UDP/TLS universal ni aislamiento físico; HOST_UNISOLATED permanece.

`available = UNKNOWN`, `publicOnly = UNKNOWN`. No tools/bootstrap/proyecciones públicas AW7, vision, perfil persistente o AW8. Sin auto-ingestion Knowledge/Memory ni nuevo AgentLoop/Session. MEMORY semantic NOT_CERTIFIED y certificaciones previas no reabiertas.

La decisión normativa/literal del cierre es **AW6 = PASS**. Detener para revisión humana. Sin commit/push/tag/release, sin READY y sin AW7.
