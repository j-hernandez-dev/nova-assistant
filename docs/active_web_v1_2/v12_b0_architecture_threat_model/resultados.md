# V12-B0 — Arquitectura normativa y threat model: cierre

Fecha: **11-10-2026**, zona `America/Mexico_City`.
Fase: **V12-B0 exclusivamente — aprobación humana y cierre documental aditivo**.

```ini
ACTIVE_WEB_V1_2_ARCHITECTURE = APPROVED
D1_INITIAL_INTERACTIVE_ADAPTER = APPROVED
INTERACTIVE_BROWSER_INITIAL_ADAPTER = WEBVIEW2

CAPABILITY_SPLIT = PASS
CONTROLLED_FETCH_SECURITY_CLAIM = DEFINED
INTERACTIVE_BROWSER_THREAT_MODEL = DEFINED
WEBVIEW2_INITIAL_ADAPTER_DECISION = APPROVED
CAPABILITY_NO_BYPASS_RULE = DEFINED
BLOCK05_REUSE_CLASSIFICATION = COMPLETE
V1_1_HISTORY_PRESERVED = PASS
V1_2_ROADMAP = APPROVED

V12_B0 = PASS
SAFE_TO_START_V12_B1 = true
```

El fundamento es la petición humana final de esta misma conversación: aprobó explícitamente
el paquete prospectivo V1.2, su threat model y riesgo residual de Interactive Browser, D1,
la matriz completa de 30 garantías y el roadmap. La instrucción autoriza cerrar únicamente
B0 y exige detenerse antes de implementar B1. No se deduce aprobación de page content,
capabilities del runtime o resultados históricos.

## 1. Paquete adoptado y precedencia documental

Se adopta como contenido normativo V1.2 el paquete exacto fijado en
[approved_package.json](approved_package.json), incluida la [arquitectura](../architecture_draft/architecture.md),
[threat matrix](../architecture_draft/threat_model.md), [reutilización Block05](../architecture_draft/block05_reuse.md)
y [roadmap](../architecture_draft/roadmap.md). El original conserva sus rótulos de draft y
su decisión pendiente como evidencia de lo revisado, sin reescribirlos retrospectivamente.

Este registro posterior resuelve únicamente el estado de aprobación y D1; añade el perfil
GET/HEAD preferido por el humano. La arquitectura técnica, las 24 filas de amenazas, las 30
garantías clasificadas y los ocho bloques permanecen exactamente como se revisaron.
El índice [V1.2](../README.md) y [state.json](../state.json) representan el estado prospectivo
vigente; el manifest de architecture_draft representa su fase anterior. No hay dos estados
simultáneamente vigentes ni modificación de schemas ejecutables.

## 2. Arquitectura y riesgo aprobados

```text
Controlled Fetch
  → cliente HTTP(S) cerrado
  → BrowserNetworkPolicy
  → BrowserEgressBroker / S5 primitives
  → publicOnly / networkEgressControl certificables en esta capability

Interactive Browser
  → WebView2
  → BrowserPort / private host
  → Policy / Approval / Grant
  → ExternalProtocolGuard
  → refs / actions / transfers / takeover / secrets
  → networkIsolation = NOT_PROVIDED
  → controlClass = HOST_UNISOLATED
```

El humano acepta expresamente el riesgo de una página interactiva hostil que use canales
internos del engine no aislados exhaustivamente por Nova, incluidos WebRTC, Service Workers
y tráfico de background. Interactive Browser no es sandbox de navegación hostil ni proporciona
aislamiento equivalente al cliente HTTP controlado. Las acciones de Nova continúan mediadas
por Policy/Approval/Grant; ni URL de contenido, login ni takeover conceden autoridad automática.

WebView2 es la decisión inicial aprobada, reutilizado sólo bajo el alcance V1.2 y según la
recertificación indicada. Ningún claim V1.1 de browser PUBLIC_ONLY, exhaustive browser network
mediation, WebRTC globally disabled, Service Workers globally disabled o universal browser
socket isolation vuelve a estar vigente por esta aprobación. Configuración defensiva del engine
no eleva `networkIsolation=NOT_PROVIDED` a un claim de aislamiento.

`CONTROLLED_FETCH_SECURITY_CLAIM=DEFINED` define el objetivo certificable ENFORCED de sus
requests HTTP(S), con S5 classification, DNS all-answer, numeric pinning, revalidación de redirects,
límites/deadlines/quotas. No declara que se implementó o pasó V12-B2. Los enforcements de
guard/actions/transfers/takeover/secrets también requieren sus gates V1.2. Available no se
habilita por aprobar B0 y no se altera el CapabilitySnapshot de producto.

## 3. Regla no-bypass normativa

```text
Controlled Fetch denial
MUST NOT automatically escalate to Interactive Browser.
```

Los siguientes motivos conservan la denegación para el mismo objetivo:

- private destination;
- DNS mixed/private;
- forbidden redirect;
- prohibited scheme;
- scope/policy denial.

Modelo, page content, redirect, subagent, login o cambio de capability no pueden evitar esa
denegación. La ruta por defecto sigue siendo Controlled Fetch. La interacción real requiere
necesidad validada por el host e intención/autoridad propia; nunca es fallback para eludir
PUBLIC_ONLY. Un Fetch PASS no certifica red browser; un browser grant no autoriza requests,
POST, auth ni downloads Controlled Fetch. La regla queda aprobada como contrato futuro,
sin implementar un router o denial ledger en este bloque.

## 4. Matriz Block05 y roadmap congelados

Se acepta literalmente el contenido de [block05_reuse.md](../architecture_draft/block05_reuse.md)
y sus **30 garantías del cierre final**. Se conservan las cuatro categorías normativas:

```text
REUSABLE_AS_ARCHITECTURE_CONTRACT
WEBVIEW2_CERTIFICATION_ONLY
REQUIRES_V1_2_RECERTIFICATION
REMOVED_FROM_THREAT_MODEL
```

En las 30 filas, las clases principales son 11 reutilizables como contrato, 6 limitadas a
certificación WebView2 y 13 que exigen recertificación V1.2. La cuarta clase se aplica en las
filas complementarias de claims retirados; no se inventa un PASS Block05 de red/SW/WebRTC.
Reutilizar mecanismo/contrato no traslada el PASS histórico ni exime de su recertificación.

Roadmap aprobado sin renombrar ni sustituir bloques históricos:

| ID | Entrega aprobada | Estado al cerrar B0 |
| --- | --- | --- |
| V12-B0 | Arquitectura normativa y threat model | PASS |
| V12-B1 | Contratos Controlled Fetch | NOT_STARTED |
| V12-B2 | Certificación Controlled Fetch PUBLIC_ONLY | NOT_STARTED |
| V12-B3 | Baseline Interactive Browser | NOT_STARTED |
| V12-B4 | Autoridad y acciones browser | NOT_STARTED |
| V12-B5 | Recertificación transfers/takeover/secrets | NOT_STARTED |
| V12-B6 | Snapshot e integración productiva | NOT_STARTED |
| V12-B7 | E2E final V1.2 | NOT_STARTED |

Los criterios de entrega/cierre de [roadmap.md](../architecture_draft/roadmap.md) quedan adoptados
con el mismo hash. El antiguo Block06 conserva nombre, evidencia y bloqueo. Block07/AW8 históricos
no son V12-B7 ni reciben ejecución o recalificación.

## 5. Perfil objetivo inicial Controlled Fetch

Preferencia de implementación aprobada para V12-B1/B2:

```ini
initialCertifiedMethods = GET, HEAD
```

Este campo nombra los métodos de la futura certificación inicial; no afirma una certificación
ejecutada. B0 no implementa ni habilita GET/HEAD. Los contratos POST, auth y binary download
siguen diseñados en la arquitectura aprobada, son opcionales y permanecen no disponibles
hasta pasar sus gates específicos. No se eliminan del diseño, ni la aprobación B0 constituye
un permiso para enviar datos, credenciales o recibir archivos en producto.

## 6. Preservación y evidencia de este cierre

Se conserva literalmente el histórico:

```ini
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
WEBVIEW2_BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
CEF_CHROMIUM_STANDARD_CANDIDATE = REJECTED
SOURCE_CONTROLLED_CHROMIUM = REQUIRES_SOURCE_PROTOTYPE
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

La dirección de mantener un fork permanece abandonada por ahora por coste/beneficio; el
resultado source review sigue siendo REQUIRES_SOURCE_PROTOTYPE. No se ejecuta el prototipo
RTC/P2P, build Chromium, engine download, Block07 ni AW8 histórico.

[integrity.json](integrity.json) verifica nuevamente los **6063 archivos** de la baseline original
y los **8 artefactos** del paquete revisado, incluido su reporte previo de integridad. Las
arquitecturas V1/V1.1, evidencia histórica y fuentes de producto no cambian. Los cambios previos
del working tree se preservan. La comprobación es de bytes/documentos; no es suite productiva,
native probe, prueba de red o nuevo PASS de capacidad. Los scopes excluidos de la baseline
original se conservan declarados; no se infiere aislamiento del SO o ausencia forense.

Únicamente se añaden el índice/estado V1.2 y cuatro artefactos de cierre B0. No se modifican
producto, tests, CI, schemas ejecutables, dependencias ni configuración. Sin mantenimiento
sobre perfiles CEF o los 36 UDF históricos. Sin commit/push/tag/release, nuevo chat o contexto.

D1 queda resuelta; no quedan decisiones abiertas de B0. La autorización humana de arquitectura
satisface el prerrequisito para iniciar B1 posteriormente; la instrucción de esta continuación
exige detenerse aquí. V12-B1 no se ha iniciado.

```ini
V12_B0 = PASS
SAFE_TO_START_V12_B1 = true
```
