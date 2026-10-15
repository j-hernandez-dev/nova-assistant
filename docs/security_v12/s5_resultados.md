# Resultados S5 — cierre

**Estado: PASS. Gate S5 satisfecho en Windows.** Sólo S5 implementado.
`web_fetch` productivo mediado por el cliente HTTP de Nova, PUBLIC_ONLY y límites
aprobados. Sin S6, commit/push, dependencias productivas nuevas ni cambios OS.

Diseño: [s5_network_safety.md](s5_network_safety.md).
Decisión: [SEC12_OD_04_S5.md](SEC12_OD_04_S5.md).
Inventario y SHA-256: [s5_manifest.json](s5_manifest.json).

## Baseline y preservación

Core V1 y SECURITY V1.2 leídos completamente antes de implementar. Baseline
relevante: Nova Core con S0–S4, S4 PASS, branch `main`, HEAD
`158b60effa484cd34a58b991f3ee4ca3f808d924`, staging vacío y working tree dirty
preexistente. Se verificaron los **245 pins S4** antes de editar: todos coinciden.
No se consultó ni reutilizó proyecto/branch SECURITY deprecated.

Snapshot anterior: [before/snapshot.json](s5_evidence/before/snapshot.json), 622
archivos existentes. Antes de modificar producto: **142 passed**, sin skips ni
failures, [baseline](s5_evidence/baseline/run.json). Incluye contratos S4/S2,
runtime/approval, fronteras Core, providers/schemas y caracterización de la vieja
superficie web, incluida fixture HTTP loopback real.

Preservación final: **614 archivos intactos, 8 modificados, 0 desaparecidos** del
snapshot. Las tres eliminaciones previas README.easy-ja.md/README.ja.md/hello.py
se conservan; no se revierten ni se agregan eliminaciones. Staging sigue vacío,
HEAD sin cambio. Documentos y evidencia histórica S0–S4 permanecen intactos,
incluido WinError 1314 y el gate manual posterior de symlinks. Sus manifests no
se regeneran con fuentes S5. Los antiguos pins de fuentes modificadas representan
el baseline histórico, no el producto posterior a S5.

Verificación: [closure_verification.json](s5_evidence/closure_verification.json).
Los **636 hashes de fuentes** registrados por la corrida definitiva siguen
coincidiendo. Los artefactos de cierre creados después se pinnean en el manifest.

## Implementación / archivos

Creados:

- `local_cli/core/network.py`: contratos/puerto, límites, endpoint/hop,
  presupuesto total y errores seguros.
- `local_cli/application/network.py`: policy URL/IP/redirects, comprobación de
  ceiling/parent, coordinación de fetch y resultado/audit mínimo.
- `local_cli/infrastructure/http_fetch.py`: DNS bounded-wait, socket pinned,
  I/O no bloqueante, TLS con hostname verificado, GET y lectura bounded.
- `local_cli/network_config.py`: defaults expresamente autorizados.
- `tests/security_v12/run_s5.py`, `network_fixtures.py`, `test_s5_contracts.py`,
  `test_s5_runtime.py`, `test_s5_network.py` y tres archivos de
  `network_tls_fixture/`: tests, puertos mock y material TLS público de fixture.
- ADR, diseño, informe, manifest y toda `s5_evidence/` (raw logs/XML/run.json,
  observaciones nativas, snapshots y diagnósticos), incluyendo fallos intermedios.

Modificados respecto a S4, preservando su implementación anterior:

- `local_cli/application/policy.py`: capability web BROKER_ENFORCED y network
  intent explícito; no se amplía la autoridad de shell ni su policy.
- `local_cli/application/tool_runtime.py`: factory productiva obligatoria,
  network binding en digest, dispatch tipado sin fallback/cache, validación final,
  idempotencia/terminal y propagación del servicio.
- `local_cli/application/session.py`, `local_cli/sub_agent.py`,
  `local_cli/tools/agent_tool.py`: servicio compartido en main y ambos caminos de hijos.
- `local_cli/tools/web_fetch_tool.py`: schema/descripción/nombre intactos;
  reemplazo del urllib sin mediación, incluso en el facade de compatibilidad.
- `tests/security_v12/test_s2_policy.py`, `test_s2_runtime.py`: expectativa de
  control BROKER y puerto HTTP mock explícito. Se conservan assertions de
  policy/claim/orden/ejecución única; no se introduce fallback legacy para tests.

No se modifican AgentRuntime, Core security/grants, providers/Ollama, adapters
CLI/Desktop, broker FS ni launcher de procesos. El inventario exacto está en el manifest.

## Tests y evidencia definitiva

Comando: `python -B tests/security_v12/run_s5.py --output docs/security_v12/s5_evidence/closure_final --host-real`.
Python instalado **3.14.6**, Windows NT **10.0.26200.0**. Perfiles/temp/fixtures
privados, sin red externa, modelos reales, UAC/admin, instalaciones ni cambios
en el trust store del sistema. Opt-in host-real sólo para las fixtures S5.

| Grupo | Resultado | Tipo |
|---|---|---|
| closure_final/s5 | **93 passed**, 0 skips | 51 unit/contract + 42 Application/runtime/issuer/integration con puertos mock y providers scripted |
| closure_final/prior_regression | **647 passed + 10 subtests**, 1 skip | Core/backend/CLI/JSONL/frontends, S1–S4 unit/ports/contracts/integration/smoke; incluye smoke/cancelación nativa Core |
| closure_final/s5_host_real | **28 passed**, 0 skips | HTTP/TLS/DNS/socket IPv4/IPv6 Windows reales en fixtures privadas; mocks de DNS/admission sólo cuando se declaran |

**Total definitivo: 768 passed + 10 subtests, cero failures.** El único skip es
smoke opcional de un daemon Ollama real no habilitado; no sustituye un requisito
del gate S5. El cliente Ollama productivo sí ejecutó HTTP real contra una fixture
`/api/tags` local, mientras web_fetch denegaba ese mismo destino. No se declara
inferencia real ni servicio Ollama/modelo real funcionando.

[Raw run](s5_evidence/closure_final/run.json),
[unit/runtime](s5_evidence/closure_final/s5.log),
[regresión](s5_evidence/closure_final/prior_regression.log),
[host-real](s5_evidence/closure_final/s5_host_real.log),
[observaciones](s5_evidence/closure_final/network_observations.json).

Cobertura S5: HTTP/HTTPS, certificados/hostname correctos y rechazo TLS inseguro,
pinning sin segunda resolución, ausencia de proxy/auth/cookies, redirects públicos
relativos/cross-host/HTTP→HTTPS, DENY downgrade/private/file/data, DNS mixto/
rebinding, límites de cadena/cuerpo/texto y marcador, deadline acumulado, headers/
body trickle, cancelación repetida, cierre peer EOF/RST, handshake TLS lento,
DNS OS localhost y DNS bloqueado con worker limitado, errores tipados/content
type/encoding/incomplete/Location duplicada/refusal, ceiling/parent/revocation/
revision/cancel/config stale, replay sin retry y terminal único.

Las pruebas positivas de HTTP/TLS nativo conectan a fixtures loopback. Cuando
Application debe llegar a ellas, se sustituyen **explícitamente** DNS y admisión
de fixture, no el broker GET. La policy productiva PUBLIC_ONLY se comprueba en
tests separados y deniega esas mismas fixtures sin TCP/GET. Los casos públicos
externos son unit/mock: no se reclama validación nativa de Internet público.

Se prueban backend común productivo, hijo por `agent` y por `StartSubAgent`
con servicio compartido/grant propio. Provider scripted no es LLM real. No hay
Electron UI E2E ni humano real aprobando; S5 pública no permite private con approval.
No se repite el gate symlink S3 ni el gate de procesos S4: sus adapters nativos
no cambiaron, su evidencia está intacta y la regresión pertinente se repitió.

## Verificación incremental / incidentes conservados

No se omitieron pruebas para lograr PASS. Toda corrida crea un directorio nuevo.
Los conteos de corridas se solapan y no se suman como pruebas únicas.

| Corrida | Resultado |
|---|---|
| block1_contracts | 41 pass / 8 fail: acceso incorrecto a campo Core y token protocol de fixture |
| block1_contracts_recheck | 49 pass |
| block2_runtime | 138 pass / 2 fail: campos requeridos de grant fixture y expectativa S2 de control anterior |
| block2_runtime_recheck | 141 pass |
| block3_native | 85 pass; 16 host pass |
| full_gate_candidate | 85 + 647 pass, 10 subtests, 1 skip; 15 host pass / 1 fail de latencia cancel |
| cancel_diagnostic | 50 pass; 19 host pass / 1 fail; excluir creación de cliente no eliminó la latencia |
| cancel_control_socket_recheck | 85 pass; 17 host pass / 3 fail; duplicar socket no resolvió la lectura bloqueante |
| nonblocking_deadline_recheck | 85 pass; 20 host pass, incluidas cinco cancelaciones |
| product_routes_and_budget / audit_and_error_recheck | ambas: 88 pass; 24 host pass |
| tls_dns_cleanup_recheck | 90 pass; 24 host pass / 3 fail: fixture exigía sólo EOF al abortar |
| peer_closure_recheck | 90 pass; 27 host pass; peer confirma EOF o reset, no un socket abierto |
| final | 92 + 647 + 27 pass, 10 subtests, 1 skip |
| refused_connection_probe / refused_connection_recheck | 51/93 pass; ambas 27 host pass / 1 fail con deadline fixture .5 s |
| refused_timing_recheck | 93 pass; 28 host pass |
| closure_final | **93 + 647 + 28 = 768 pass**, 10 subtests, 1 skip |

Se corrigieron los errores de contrato/fixtures sin alterar el issuer ni schemas.
La cancelación realmente siguió fallando tras separar el tiempo de creación del
cliente; se reemplazó el I/O bloqueante por polling no bloqueante con deadline
absoluto. La causa exacta de la carrera del socket bloqueante no fue capturada;
la explicación relacionada con su cierre/makefile es una inferencia, no una
causa demostrada. La solución definitiva pasó repeticiones y gate completo.

La fixture de cierre se reforzó con observación del peer. Exigir sólo FIN/EOF
era demasiado específico para cierre abortivo con bytes no leídos: se registran
EOF y CONNECTION_RESET reales; timeout o peer abierto no pasan. No se reduce el
criterio de cierre ni el bound de retorno de cancelación.

Para conexión rechazada, un probe nativo midió **2,037 s**, connect_ex 10035 y
SO_ERROR 10061 en el conjunto excepcional de select. Con .5 s la fixture expiraba
correctamente antes del rechazo, así que su expectativa de clasificación era
incorrecta. Se comprueba el conjunto excepcional y se usa 3 s sólo en ese test;
los **30 s productivos no cambian**. Diagnóstico:
[connection_refused_diagnostic.json](s5_evidence/connection_refused_diagnostic.json).

El OpenSSL ya incluido en Git se usó offline una vez para generar el material
TLS público de fixture. El entorno restringido rechazó inicialmente el arranque
de MSYS (NtCreateDirectoryObject); la generación autorizada fuera de esa
restricción pasó. No es dependencia de Nova ni del runner y no cambió trust OS.

## Gate SECURITY V1.2 §19 / §29 S5

| Criterio | Estado / evidencia |
|---|---|
| web_fetch HTTP(S) productivo mediado y schema compatible | PASS — factory/runtime/direct facade, schema S0 y rutas backend/hijos |
| Scheme policy, file/data DENY | PASS — contratos/runtime; ningún handler o lector alternativo |
| Redirects/destino y DNS, no expansión privada silenciosa | PASS — unit/mock + redirects/DNS OS/fixtures nativas bloqueadas |
| Límites de tiempo/size/redirects, flags y publicación bounded | PASS — contratos + payload/total budget/trickle/handshake nativos |
| Audit solicitado/efectivo, errores tipados, replay/terminal | PASS — runtime/issuer + observaciones nativas |
| Loopback/private IPv4/IPv6 conforme a OD-04 autorizada | PASS — PUBLIC_ONLY + pruebas específicas |
| Ollama/provider conserva su ruta host separada | PASS — regresión provider + cliente real HTTP contra fixture API local |
| Shell/Git vía shell: intent/policy, sin claims de firewall | PASS — policy S2 preservada, intent HOST_UNISOLATED/unmediated y diseño explícito |
| Core boundaries y regresión pertinente | PASS — 647 pruebas/10 subtests, schemas/fronteras/lifecycle/frontends |
| Gate completo S5 | **PASS Windows** |

Todos los criterios del gate S5 están cumplidos. No hay regresiones observadas
en las corridas definitivas. Los viejos tests S0 de aceptación file/data/ftp,
lectura unbounded y redirect loopback registran el baseline histórico: ese
comportamiento se reemplaza intencionadamente por S5, no se conserva como un
requisito productivo ni se borra su evidencia. No se afirma que toda prueba de
caracterización histórica de todas las fases describa el comportamiento actual.

## Deuda / OPEN DECISIONS / siguiente fase

No queda deuda bloqueante ni OPEN DECISION de S5. SEC12-OD-04 está cerrada por
elección expresa del usuario; límites adoptados exactamente.

Limitaciones explícitas: getaddrinfo OS puede sobrevivir al timeout (máximo un
worker compartido, fail-fast sin cola); no hay validación host-real Linux/macOS
ni Internet público; no se contiene routing ni efectos del servidor remoto.
Audit es mínimo/live, no durable/general. Environment/Secrets y redacción total
siguen pendientes de S6/S7; Core OD-06 no se cierra con estos bounds de cliente.
Se conserva la limitación previa de workspace rebinding. Nada de esto se
presenta como firewall del shell, aislamiento físico ni cuotas OS preventivas.

Siguiente fase lógica: **S6 — Environment / Secrets**, **no implementada**.
No commit ni push. HOST_UNISOLATED se mantiene; S3 conserva sus claims únicamente
en sus superficies FS realmente mediadas.
