# Active Web V1.1 — Enmienda normativa aprobada

Fecha: 2026-10-10. HEAD de documentación: `b0bf60f91956e4a5c17af02be5a6e241ec0363a7` (`main`).

`ACTIVE_WEB_ARCHITECTURE_V1_1 = APPROVED_AND_DOCUMENTED`

## Alcance y causa

Se incorporan P-01–P-05 aprobadas humanamente de [External Protocol Enforcement Review](../architecture_review/EXTERNAL_PROTOCOL_ENFORCEMENT_REVIEW.md). El nuevo documento [NOVA_ACTIVE_WEB_ARQUITECTURA_V1_1.md](../../architecture/NOVA_ACTIVE_WEB_ARQUITECTURA_V1_1.md) es normativo **prospectivo**.

Causa: `AW8-EGRESS-EXTERNAL-PROTOCOL-001`. La arquitectura V1 atribuyó al broker una superficie host-launch que éste no observa. El cierre focal quedó BLOCKED por `ARCHITECTURAL_ENFORCEMENT_LIMIT`; no se reinterpreta.

Esta entrega crea sólo cuatro documentos. No implementa WebView2, modifica código/tests/CI/dependencias/runtime, instala componentes, ejecuta pruebas/probes/inferencia ni reanuda AW8. No hay staging/commit/push/tag/release.

## Cambios aprobados

| Propuesta | Incorporación | Secciones V1.1 |
|---|---|---|
| P-01 | BrowserNetworkEgressControl separado de ExternalProtocolGuard; DENY_ALL pre-effect también takeover; broker no es authority de launches; audit host-owned | §4.3, §10.1, §18, §26.3, §31 |
| P-02 | Candidato Windows WINDOWS_WEBVIEW2 mediante BrowserPort/private IPC/host Infrastructure; Playwright histórico sin fallback | §5–6, §9.1, §27, §34–35 |
| P-03 | Snapshot **conceptual** schemaVersion 2 aditivo: dos fronteras/observaciones separadas; misma composición y fail-closed por incompatibilidad | §25, §31, §37 |
| P-04 | AW-INV-051–053 prospectivos; 50 enunciados y corpus históricos preservados; seis precisiones prospectivas explícitas | §33, §42 |
| P-05 | Continuación engine-specific dentro de AW8; recertificación guard/red/BrowserPort/lifecycle y gates/claims futuros | §35–38, §40 |

La arquitectura contiene la matriz completa `V1 SECTION → V1.1 CHANGE → MOTIVO → EVIDENCIA HISTÓRICA` (§41) y `AW-INV → V1.1 STATUS` (§42). [traceability.json](traceability.json) contiene las mismas correspondencias, requisitos P-01–P-05 y hashes históricos.

## Contratos conservados

21 secciones base permanecen textualmente iguales tras normalizar finales de línea para el nuevo documento: §§1, 3, 7, 8, 11–17, 19–24, 28–30 y 32. No se reduce ningún límite, approval, freshness/ref, effect/outcome, staging, framing, presupuesto o exclusión de alto impacto.

Los 50 enunciados históricos AW-INV-001–050 permanecen iguales. Hay 44 `UNCHANGED`, seis `REFINED` sólo prospectivamente (007, 008, 027, 029, 030, 048) y tres `NEW_PROSPECTIVE` (051–053). Se conservan los 32 criterios READY de V1, refinando los afectados y añadiendo 33–35; ninguno se elimina/reduce.

`HOST_PRE_EFFECT_DENY` es metadata Active Web, no un nuevo SECURITY ControlClass. `HOST_UNISOLATED` permanece intacto. No hay segundo AgentLoop, Application, Security ni autoridad de frontend/host.

## Historia inmutable

Se conservan AW0 original execution PARTIAL y su cierre normativo aditivo PASS, AW1–AW7 y sus cierres, AW8 original BLOCKED, prerequisite remediation 01/02 PARTIAL y egress closure BLOCKED. Los PASS de wiring/capability de revision 02 siguen limitados a la composición evaluada.

Todos los manifests/freezes/raws/corpus/resultados ya existentes permanecen byte-intactos. No se repinean ni cambian verdicts. El corpus AW0 de 50 invariantes no recibe retroactivamente 051–053.

La evidencia native Playwright/Chromium AW5–AW8 no certifica WebView2. Su código permanece `HISTORICAL / NON_CERTIFIED ACTIVE WEB ADAPTER`; no se elimina ni se permite fallback automático. La deuda HOME/USERPROFILE sigue `PREEXISTING_CORE_HARNESS_DEBT`, sin reparación/ejecución/recalificación.

## Pins críticos

| Artefacto | SHA-256 |
|---|---|
| V1 histórica | `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e` |
| Review aprobada | `6b4b2ada5297492746f0551c5032987af012d3b295fa6836da2e1eacbe751e04` |
| V1.1 prospectiva | `46ec3201460ba37a6fe47f6cf94e80f0024ec442c9323115a0cf19d64de95e1d` |
| AW8 histórico manifest | `93d3ae2b2566e7af347212a5cac7aa2fa326d92d7f1f8ee738f42424a8d4ce19` |
| Egress closure manifest | `228105f11d0d7f9eec3a3d847e54af7765e4c4f7d764f7e0366fda7bd3670306` |
| Corpus AW0 histórico | `67a6b89f4aaca54bfdb8f2b1642f4e6ff18b829e0cf1735e8d598072a0d243b4` |

[manifest.json](manifest.json) registra todos los pins críticos AW0–AW8/revisiones/cierre focal y fingerprints del estado previo/posterior. No es un nuevo freeze de producto ni certificación.

## Próxima continuación, no ejecutada

Dentro de AW8 y sólo con autorización futura: contrato de host/IPC → adapter WebView2 → ExternalProtocolGuard → observations/refs/actions → transfers/takeover/lifecycle → BrowserNetworkEgressControl → discovery → integración productiva → certificación de prerrequisitos. Sólo entonces solicitar reanudación AW8.

Quedan por elegir técnicamente lenguaje/framework, empaquetado/runtime verificable e IPC cerrado; no son capabilities implementadas. Red y guard requieren pruebas host-real independientes sobre la misma composición, con protocolo registrado controlado y HTTPS confiable, sin autoridad global silenciosa.

## Claims actuales

`ACTIVE_WEB_CORE=NOT_READY`, `available=UNKNOWN`, `publicOnly=UNKNOWN`.

`ACTIVE_WEB_ENGINE=WINDOWS_WEBVIEW2` es un claim **futuro** condicionado a host-real; no se publica como disponible ahora. No se declara AW8 PASS ni READY. Detención para revisión humana.
