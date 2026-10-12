# Active Web V1.2 — estado prospectivo aprobado

Fecha: **11 de octubre de 2026**. Actualización exclusivamente documental.

```ini
ACTIVE_WEB_V1_2_ARCHITECTURE = APPROVED
D1_INITIAL_INTERACTIVE_ADAPTER = APPROVED
INTERACTIVE_BROWSER_INITIAL_ADAPTER = WEBVIEW2
V12_B0 = PASS
SAFE_TO_START_V12_B1 = true
```

La revisión humana final aprobó el paquete de arquitectura, threat model, riesgo residual de
Interactive Browser, matriz de reutilización Block05 y roadmap V12-B0…V12-B7. Este cierre
se registra aditivamente en [V12-B0](v12_b0_architecture_threat_model/resultados.md), su
[manifest](v12_b0_architecture_threat_model/manifest.json) y el [estado actual](state.json).

El [paquete revisado](architecture_draft/README.md) se conserva byte-intacto, incluidos sus
estados históricos DRAFT/READY_FOR_HUMAN_REVIEW y D1 abierta. La aprobación posterior de B0
resuelve esos estados para el mismo contenido fijado por hashes en
[approved_package.json](v12_b0_architecture_threat_model/approved_package.json).
El contenido técnico de ese paquete queda adoptado como arquitectura normativa V1.2, con
las precisiones aprobadas de perfil inicial y adapter registradas en este cierre.

| Capacidad | Arquitectura aprobada | Claim |
| --- | --- | --- |
| Controlled Fetch | Cliente HTTP(S) cerrado → BrowserNetworkPolicy → BrowserEgressBroker / primitivas S5 | publicOnly/networkEgressControl certificables dentro de esta capability; aún sin implementación/certificación V1.2 |
| Interactive Browser | WebView2 → BrowserPort/host privado → Policy/Approval/Grant, ExternalProtocolGuard, refs/actions/transfers/takeover/secrets | `networkIsolation=NOT_PROVIDED`, `controlClass=HOST_UNISOLATED`; riesgo residual aceptado por el humano |

La denegación de Controlled Fetch **MUST NOT automatically escalate to Interactive Browser**.
Private destination, DNS mixed/private, forbidden redirect, prohibited scheme y scope/policy
denial permanecen denegados para ese objetivo. No se recupera ningún claim browser PUBLIC_ONLY
o de aislamiento exhaustivo V1.1; la autorización de una capability no sirve en la otra.

El perfil objetivo inicial de V12-B1/B2 es **GET, HEAD**. POST, auth y binary download mantienen
sus contratos diseñados y son opcionales/no disponibles hasta superar sus gates específicos.
La aprobación del diseño no acredita capacidad productiva ni genera Approval/Grant de uso.

V1/V1.1 y toda evidencia histórica mantienen sus bytes y estados. En particular:

```ini
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
WEBVIEW2_BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
CEF_CHROMIUM_STANDARD_CANDIDATE = REJECTED
SOURCE_CONTROLLED_CHROMIUM = REQUIRES_SOURCE_PROTOTYPE
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

El PASS de Block05 pertenece a la composición histórica WebView2; no es PASS de implementación
ni recertificación V1.2. Los IDs V12-B0…V12-B7 son prospectivos, sin renombrar Block06/Block07/AW8.

La [integridad B0](v12_b0_architecture_threat_model/integrity.json) registra los hashes del
paquete aprobado y la comprobación de preservación. V12-B0 es el único bloque cerrado; B1…B7
siguen sin iniciar. `SAFE_TO_START_V12_B1=true` significa que el prerrequisito de arquitectura
está satisfecho, no que esta continuación haya iniciado o autorizado ejecutar B1.
Se detiene para revisión humana, conforme a la solicitud final.
