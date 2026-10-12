# AW4 — Network broker

AW4 = PASS

Cierre del componente broker conforme a §35: **«Cierre: broker enforcement demostrado.»** No es ACTIVE_WEB_CORE=READY, disponibilidad de navegador ni certificación de ausencia de bypass de Chromium.

## Baseline y reutilización

Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`. Working tree heredado sucio y staging vacío; todos los cambios AW0–AW3 conservados. `baseline_freeze.json` registra archivos/pins y tags Core/Security/Memory/Knowledge.

Arquitectura SHA-256 `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`. AW3 manifest SHA `cc3df0fa2c8c5505ccae3a62e74117e91184d52b81da713354aab4090ebe2e47`, intacto. Auditoría/findings e historia conservadas; ninguna certificación reabierta.

Preflight y alcance: `preflight.json`. Reutilizados S5 `canonical_url/public_address`, resolver acotado y transporte TCP con IP fijada, AW0 snapshot fail-closed, AW1 ownership/lifetime como contrato de callback host, y AW3 ToolRuntime/Policy/approval sin cambios. No se reutiliza el ejecutor GET de web_fetch como browser ni se modifica su significado.

Baseline antes de producto: **481 PASS / 1 FAIL heredado** HOME/USERPROFILE, 0 ERROR/SKIP. Outputs siempre fuera de Git.

## Implementación de AW4

- Core puro: planes y configuración privada, límites host requeridos, error tipado y cleanup socket/worker. Contratos internos, no nuevos DTO públicos, schemas persistentes ni migraciones.
- Application `BrowserNetworkPolicy`: prueba host explícita `True` antes/después de DNS y durante IO; un string de página o valor truthy no es autoridad. Ownership/lifetime/context/close del manager pueden respaldar esa prueba; no crea grants ni decide browser actions. El callback debe ser acotado y no bloquear IO bajo locks del futuro adapter.
- Broker opt-in autenticado en `127.0.0.1`, puerto efímero, credenciales privadas únicas por instancia. No modifica proxy/firewall/configuración global ni ofrece un endpoint al modelo.
- Cada nuevo request HTTP/CONNECT revalida host/puerto/sesión/DNS. Todos los answers deben ser públicos (máximo 64), sin DNS cache de admission. No DNS al conectar, redirects automáticos, ambient proxies, alternate-IP retry ni fallback.
- HTTP absolute-form acotado; CONNECT authority-form a puerto permitido; conexión al endpoint numérico admitido usando el transporte S5. Default policy HTTP80/CONNECT443; overrides host finitos/explicitos, máximo 16 puertos por grupo.
- Framing estricto HTTP/1.1: Host coherente, Content-Length único/acotado, sin duplicados/folding/TE/Expect/Upgrade. Un request por socket HTTP; se generan Host/length/Connection-close y se retiran headers de proxy/hop. No streaming chunked, HTTP/1.0 proxy request, SOCKS o eval/selector browser.
- Denegación de file/javascript/data/internal/custom schemes como targets, protocolos no soportados y upgrades WS plaintext. HTTPS/WSS sobre CONNECT son opacos: el broker controla el endpoint, no desencripta ni certifica semántica remota/cada virtual origin dentro del túnel.
- Timeout/BUSY/revocation/cierre conservan fallo tipado y no vuelven a enviar. Resultados tardíos no se entregan; cleanup limitado devuelve confirmado únicamente para listener/conexiones/workers observados.
- Diagnósticos acotados (1024 + contador de dropped) sin bodies/query/cookies/auth headers/channel passwords. **No sustituyen SecurityAudit ni un BrowserActionReceipt remoto.**
- Probe explícito local: verifica broker vivo y denegación productiva. `networkBroker` del componente puede ser KNOWN true; `available/publicOnly` del navegador siguen UNKNOWN. Engine/profile/versions/SW/WebRTC/QUIC nunca se infieren de un proxy o configuración.
- 29 nuevos contratos base añadidos al inventario CI positivo, con todos sus parámetros. Sin workflows, runners, filtros, exclusiones, skips ni xfails nuevos.

Archivos de producto/test: `local_cli/core/active_web_network.py`, `local_cli/application/browser_network.py`, `local_cli/infrastructure/active_web/{__init__,egress_broker,capability_probe}.py`, `tests/active_web_v1/test_aw4_{network,proxy}.py`; cambio aditivo en `ci/pytest_contracts.json`. Ningún producto Core/Security/Memory/Knowledge anterior se editó.

## Evidencia real y límites del claim

**113/113 AW4 PASS:** 82 policy/DNS/ownership/límites cases y 31 proxy-module cases. Estos últimos combinan sockets nativos con fallas/substituciones explícitas; no son 31 certificaciones de egress público o Chromium.

- Productive PUBLIC_ONLY con listener real rechaza private/loopback/IPv6/metadata, DNS localhost/mixed/rebinding y no contacta el fixture prohibido.
- Transporte HTTP/TLS usa sockets reales y certificados sintéticos existentes. Para tests positivos sólo se sustituye explícitamente el endpoint admitido por el fixture privado `server.test` (`FixtureAdmission` test-only). Esa sustitución **no existe en policy productiva**, no prueba Internet y no se anuncia como private-network capability.
- Resolver doubles prueban todos los answers, DNS fresh y pinning; transporte-fault double prueba error tipado/no-retry sin filtrar detalles. TLS hostname/cert verification del cliente es real con CA sólo del fixture; el broker no hace MITM.
- Un socket directo del harness puede contactar su servidor local mientras el broker deniega ese destino. Esto conserva **HOST_UNISOLATED**, no supone firewall o prevención global de bypass.

§18.2–3 condiciona disponibilidad Core a exclusividad real del engine. Es una obligación pendiente de AW5/real-engine/certificación, no una licencia para anunciar capabilities en AW4. No se instalaron Playwright/Chromium, no se implementaron flags/adapter SW/WebRTC/QUIC ni se pretendió probarlos con doubles. No contradicción material encontrada con el orden AW4→AW5 de §35.

## Criterio por criterio

| §35 AW4 | Resultado | Evidencia |
|---|---|---|
| BrowserEgressBroker | PASS | Proxy native, auth, límites, BUSY/timeout/close, no fallback |
| PUBLIC_ONLY | PASS en sockets del broker | Reglas S5, literal y DNS, native forbidden fixture hits=0 |
| DNS/CONNECT | PASS | Fresh all-answers, numeric pin, no segunda DNS; túnel TLS native |
| Protocol restrictions | PASS | Schemes/ports/authority/framing/upgrade/redirect control |
| Capability probes | PASS | Running/closed probe; browser availability/publicOnly UNKNOWN |
| No bypass claim unless verified | PASS | No claim global/engine; direct host socket demuestra límite |
| Broker enforcement demostrado | PASS | 113 contratos finales + regresión/integridad sin nueva deuda |

Tests/IDs concretos en `manifest.json`; trazabilidad de los 50 AW-INV en `invariant_matrix.json`, distinguiendo preservado, broker-boundary y futuro diferido. **No se atribuyen 50 PASS de navegador real.**

## Historia de desarrollo preservada

| Corrida | Resultado | Clasificación |
|---|---|---|
| development-1 | 105 PASS / 1 FAIL | HARNESS_BUG: reader no manejaba peer abort WinError10053; assertions BUSY intactas |
| development-2 | 104 PASS / 2 FAIL | PRODUCT_BUG_AW4: close con input pendiente podía descartar DENY/BUSY |
| development-3 | 106 PASS | Fix: half-close + discard acotado ≤50 ms/64 KiB; no upstream/retry nuevo |
| development-4 | 108 PASS / 1 FAIL | HARNESS_BUG: port cerrado podía timeout, no refusal inmediata OS-independent |
| development-5 | 110 PASS | Fault OSError determinista, assertion tipada intacta; timeout nativo separado |
| focused-final | 594 PASS / 1 FAIL heredado | Producto final congelado; 113 AW4 PASS, 0 ERROR/SKIP |

Después de la expansión prospectiva owner/lifetime/epoch/close se congeló `product_freeze.json` y ejecutaron todas las regresiones finales. Ningún FAIL se volvió skip/xfail; ningún resultado histórico se borra. No hubo campaña de modelo, quality retries ni Internet normativo.

## Regresión final completa

| Gate | PASS | FAIL | ERROR | SKIP | SHA-256 XML |
|---|---:|---:|---:|---:|---|
| final-core | 3224 | 1 | 0 | 7 | 525c01c24fb7701e3d8cbb53967175793bf45019e4554b5f45047536fd7a1f24 |
| final-knowledge | 1015 | 0 | 0 | 0 | 6a820404f61cea0df5cf4d35bb00fcff4a18d0e0ee939e7780941382d8b4e8ba |
| final-memory | 791 | 0 | 0 | 0 | ceed30e3170816d56ba198faac9dd20a91c22558263fcbb636d8e5923374cfbe |
| final-security | 615 | 0 | 0 | 0 | 05bd903fb4a88a8194ef8046a0f216a8af39ea9fa65d03be95fdc8d28206f263 |

Total: **5645 PASS / 1 FAIL heredado / 0 ERROR / 7 skips históricos**, más **53 subtests PASS**. Denominador de parameter instances **5653**, subtests separados. Pytest 9 agrega subtests en suite.tests y log, no como testcase nodes independientes. AW4/focal no sumados dos veces.

Desktop **68 PASS / 0 FAIL / 0 SKIP**; Node 24.16.0; TypeScript exit 0. Warnings históricos Transform Types/MODULE_TYPELESS, sin cambios frontend.

Python 3.14.6/pytest9.1.1, Windows11 build26200, NTFS local/HOST_UNISOLATED, venv offline existente. Plugin autoload deshabilitado; config/runtime privados. Comandos, start/end/duración, XML/log/selection hashes y guards en `test_results.json`.

Skips son exactamente los siete de AW3: tres symlink (Windows Developer Mode/WinError1314), dos POSIX executable-mode y dos legacy WebMonitor retirado. **newFailures=0 / newSkips=0 / newXfails=0**. Memory conserva un único parámetro `new_session_id()` con UUID generado al importar, y Security/Knowledge conservan el multiset de casos aunque pueda variar el orden/hash de collection. Raw outputs no normalizados/repinneados.

Core conserva **FAIL**:
`tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`.

**PREEXISTING_CORE_HARNESS_DEBT — NON_BLOCKING_FOR_AW4**: HOME/USERPROFILE divergentes bajo runner privado, reproducido baseline/final, BashTool/test/assertion/runner inalterados. Job Core exit **1**, no anunciado verde. Gate de §35 satisfecho + ausencia de regresiones nuevas; no waiver de READY ni reescritura de deuda.

## Integridad y límites restantes

`integrity.json`: 2180 tracked fuera de CI preservados, inherited untracked drift=0, pins finales drift=0, CI anterior reconstruido byte-a-byte SHA `07e9c00c4ab19d75599d29120f2acabff7c710033e599636ee86305dcc445b01`, 29 additions solamente; index/HEAD/branch/tags intactos.

Outputs: `C:/Users/joseh/AppData/Local/Temp/nova-aw4-20261009T184936Z`. Ningún DB/audit privado/cache/log runtime dentro de Git. Arquitectura y evidencias anteriores inmutables.

Limitaciones: sin engine, proxy-exclusivity browser proof, engine DNS/coalescing/virtual origins/TLS reuse validation, SW/WebRTC/QUIC enforcement, no real browser/model E2E ni certificación Linux/macOS; CONNECT opaco; no process isolation ni universal remote transaction/correctness guarantees. Callback de sesión/autoridad es host-owned y debe ser acotado; composición real con ToolRuntime/adapter queda en AW5. El cleanup sólo confirma sockets/workers propios, no procesos browser ni terminación de llamadas DNS OS no interrumpibles.

Sin auth/takeover/transfers, nuevos frontends, Memory/Knowledge writes, browser tools, schemas persistentes, dependencias o configuración global. MEMORY/DOCUMENT SEMANTIC_PROFILE permanecen **NOT_CERTIFIED**. No OPEN DECISION material requerida para AW4; integración/pruebas reales de fases posteriores no resueltas por adelantado.

Siguiente referencia: **AW5 — Playwright/Chromium adapter**, **no implementada**. Sin commit, push, tag ni release; no READY. Detención para revisión humana.

