# Roadmap V1.2 proporcional y decisiones para revisión

Estado: **DRAFT**, 11-10-2026. Ningún bloque se implementa en esta fase.
Los identificadores V12-B0…B7 son nuevos y no sustituyen Block07 ni AW8 históricos.

## 1. Ocho bloques pequeños con fronteras comprobables

| Bloque | Entrega acotada | Criterio para cerrar |
| --- | --- | --- |
| **V12-B0 — Arquitectura normativa y threat model** | Aprobar split, claims, scopes y riesgos; registrar decisión de adapter, snapshot y límites; congelar corpus focal inicial | Revisión humana del borrador; ningún claim browser PUBLIC_ONLY/aislamiento; historial V1.1 y no-goals explícitos; sin cambios productivos como requisito de este bloque |
| **V12-B1 — Contratos Controlled Fetch** | Request/receipt/transfer/auth-secret refs propios; seam tipada del broker; GET/HEAD, optional bounded POST/download/auth; scopes/limits/outcomes y routing sin bypass | Contract tests de strict schema, owner/capability separation, redirect scope, payload/credential binding, budget y STARTED sin retry; funciones opcionales sin pruebas permanecen indisponibles |
| **V12-B2 — Certificación Controlled Fetch PUBLIC_ONLY** | Integrar policy/broker/S5 en cliente real sin engine; claims propios y recibos sanitizados | Misma composición prueba clasificación, DNS all-answer, numeric pinning, TLS, redirect, límites y fallos; ENFORCED sólo en methods/modes certificados; cero engine/cookies/ambient auth/fallback |
| **V12-B3 — Baseline Interactive Browser** | Adapter candidato recomendado WebView2, BrowserPort/IPC, owner/page/lifetime y ExternalProtocolGuard | Real host/runtime, navegación/observation estructurada, max3 y cierre/UNKNOWN honestos; guard DENY_ALL pre-effect probado en children/popups/takeover; `networkIsolation=NOT_PROVIDED`; no tools productivas todavía |
| **V12-B4 — Autoridad y acciones browser** | Ref registry/epoch/freshness; acciones fijas; risk classification; ToolRuntime/Policy/Approval/Grant y outcomes exactos | Sin JS/selectors libres, payload/origin/target/epoch/operation exactos, denegación previa al efecto, ausencia de retry después de STARTED, crash con UNKNOWN; namespace V1.2 separado de grants Fetch |
| **V12-B5 — Recertificación transfers/takeover/secrets** | Uploads host-owned, downloads browser/staging, takeover y continuidad sensible Block05 en la composición nueva | Cancel drive-by pre-file-effect; bytes/Completed/digest; file identity/lock/copy; confirmed terminal resume y unconfirmed deny; epoch/ref/approval invalidation; sin exposición de declared-sensitive/known values; cleanup owned veraz |
| **V12-B6 — Snapshot e integración productiva** | Snapshot versionado con dos capabilities; availability derivada, AgentLoop prefer Fetch, frontend opt-in/risco/takeover; denied-route ledger | Snapshot no transporta authority; legacy V1 nunca activa V1.2; browser disponible no implica publicOnly; no fallback de denial/401; subagents sin browser; credentials/refs/staging/Grant no cruzan capabilities; misma Application en CLI/JSONL/Desktop |
| **V12-B7 — E2E final V1.2** | Suite focal conjunta y manifiesto de la configuración/producto que se pretende habilitar | Cadena completa en un candidato congelado: fetch, browser, authority, transfers/takeover/secrets y fallos de boundary; compatible proof profiles; resultados/hashes/limits y negativos preservados; aprobación humana de uso/producto sólo con evidencia completa |

B0 cierra diseño únicamente tras revisión; este draft no lo marca PASS. B1/B2 pueden completarse
antes del browser. B3 no contiene integración productiva; B4/B5 no anuncian available=true.
B6 sólo podrá habilitar una modalidad con certificación focal compatible y opt-in válido; el
cierre general y autorización final del release/producto V1.2 permanecen en B7. Ningún bloque
requiere download/build Chromium ni mantenimiento de perfiles históricos.

## 2. Corpus inicial y evidencia limitada al claim

Cada familia tiene un positivo, un negativo de authority/freshness y el fallo pertinente. Reusar
fixtures/pruebas existentes por contrato mantiene proporcionalidad; no sumar sus denominadores
como nuevos tests independientes ni crear un programa de gates de browser network exhaustivo.

| Familia focal | Casos mínimos a demostrar | Evidencia requerida |
| --- | --- | --- |
| Destino y DNS | IPv4/IPv6 públicos; loopback/private/link-local/reserved/mapped/transición; respuestas vacías/mixtas/excesivas; cambio de DNS tras admisión | DNS queries/count, plan admitted, numeric endpoint conectado; para negativos, ausencia de upstream privado, sin interceptar tráfico browser |
| Redirect y TLS | Hop público permitido; hop fuera del grant/private; HTTPS downgrade; Host mismatch; certificado incorrecto; port denied | Revalidación por hop con mismo budget, hostname/SNI y denial antes del hop no autorizado |
| HTTP/limits | GET/HEAD, JSON/HTML/text estáticos; headers/body sin longitud/oversize, trickle, malformed framing; expansión rechazada/limitada | Request typed real, wire/decoded/header/count quotas, timeout/cancel, parser finito y publicación truncada honesta |
| POST/auth | POST autorizado y body tamper; read grant no cubre POST; auth origin/expiry; redirect/challenge después de dispatch; cookie import denied | Exact approval digest, secret ref privado, metadata redacted, STARTED/UNKNOWN y cero auto-retry; optional auth/method no certificado no ejecuta |
| Fetch download | Completo pequeño y límite/incomplete/digest MIME; body no crea transfer automáticamente | Receipt/staging owned, finalización HTTP confirmada; no auto-export/open/Knowledge; procedencia CF |
| Browser baseline/guard | Observation fija; quotas/timeout/crash; custom scheme/redirect/script/popup/takeover | Registered-handler canary calibrado y deny pre-effect de la misma configuración; page/host/process lifecycle; sin claim de red universal |
| Browser authority | Grant exacto positivo; stale/cross-owner refs, navigation/epoch, payload/form target cambiado; unknown click, input disclosure | Binding/Approval/dispatch correlacionados; denials pre-effect; mutation STARTED sin replay con loss/late event |
| Upload/download browser | Host selection correcta frente a file replacement/revision; permit correcto frente a drive-by/wrong-page; Completed/loss | Native primitives del adapter actual, filesystem/staging audit, refs/epoch/identity exactos; sin invocar redes de terceros hostiles |
| Takeover/secrets | Login fixture sin creds reales; navegación/retiro/reflexión del secreto declarado; confirmed terminal/unconfirmed terminal corto | Continuidad sensible validada antes de public result; lineage/terminal provenance; pause/epoch/resume y no authority del login |
| Cross-capability/routing | API/read por Fetch; interacción explícita por browser; deny PUBLIC_ONLY→browser rechazado; Grant/NetworkProofRef/secret cookie mezclados | Host routing razones/opId/policy revision, denial ledger, schemas y parent attenuation; no aceptación de texto de página como aprobación |
| Integración final | Misma Application y configs; capability revocation, failure, restart/late events | Available compatible por capability, unknown/false honestos; historia/profiles previos intactos; sin re-run para borrar fallos |

Fixtures locales/private canaries son negativos o transport controlados claramente etiquetados:
no se añade una excepción productiva PUBLIC_ONLY para pasar positivos. Tests unitarios pueden
inyectar un resolver/socket double y sólo prueban contratos; la certificación requiere observador
de transport real compatible y canaries calibrados donde se afirme ausencia de dispatch.
No tráfico real malicioso ni credenciales personales. Browser prueba guard/authority, no ausencia
global de WebRTC/SW. Una capability futura que quiera un claim adicional necesita decisión
humana y pruebas propias; no puede deducirlo de estas suites.

Cada bloque conserva expected/observed, intentos FAIL, configuración/runtime/hashes del candidato,
denominator y cleanup de recursos nuevos owned. Un fallo causal impide cerrar el claim afectado;
ningún retry de mutación ni cambio silencioso de umbral. Actualizaciones cambian sólo evidencia
compatible de la frontera afectada y sus contratos dependientes, no obligan a repetir 22 gates
que V1.2 no promete. Si el guard o el secret boundary no se sostienen en WebView2 elegido,
interrumpir esa ruta y revisar alcance/adapter con el humano.

## 3. Decisiones mínimas abiertas

**D1 — confirmar WebView2 como primer adapter Interactive Browser bajo V1.2.** Recomendado:
reutilizar el host y controles ya probados en Block05, manteniendo `networkIsolation=NOT_PROVIDED`
y recertificando guard/authority/snapshot/transfer/takeover/secret boundary. Esto no elimina
Block06 V1.1 ni acredita nuevas capabilities. Otro engine requiere justificar coste y pruebas
nativas propias de estas fronteras, sin mandato de fork Chromium.

No hace falta reabrir el split ni preguntar si PUBLIC_ONLY debe proteger el browser: el humano
ya decidió sus modelos distintos. La revisión del paquete completo incluye aceptar el riesgo
residual interactivo y los límites propuestos; no se requiere otra decisión aislada para cada
familia de pruebas. Un ajuste de límites o lanzar inicialmente sólo GET/HEAD puede resolverse
en B0/B1 sin inventar permisos ni claims. POST/auth/download cuentan como opcionales hasta
probarse; el contrato queda diseñado aunque su habilitación sea gradual.

Estado final del diseño:

```ini
ACTIVE_WEB_V1_2_ARCHITECTURE = READY_FOR_HUMAN_REVIEW
MINIMUM_OPEN_DECISIONS = D1_INITIAL_INTERACTIVE_ADAPTER
PRODUCT_IMPLEMENTATION_STARTED = false
```

Este estado significa que el diseño completo y la decisión mínima están disponibles para
revisión. No autoriza ejecutar B1…B7, cambiar producto, validar el AW8 histórico o publicar.
La continuación deberá partir de la revisión humana del borrador en este mismo trabajo.
