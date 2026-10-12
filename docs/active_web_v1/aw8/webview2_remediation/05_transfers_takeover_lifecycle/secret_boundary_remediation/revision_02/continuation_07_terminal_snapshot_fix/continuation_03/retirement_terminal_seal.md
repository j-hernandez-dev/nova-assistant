# Retirement terminal seal — continuation_03

## Alcance autorizado

Corrección prospectiva del lifecycle sensible, sin cambiar TRANSIENT/COMMITTED, thresholds, assertions, fixtures ni driver. Historia de continuation_02: 23/24 y cross FAIL permanece intacta. Arquitectura V1/V1.1 y ámbitos Core/Security/Memory/Knowledge/Desktop/network no se modifican.

## Identidad y orden

El registry privado pertenece a una BrowserSession/host. Cada protected document se registra con PageIdentity, documentGeneration opaca y EngineUnique del contexto CDP; el número reutilizable de executionContextId no es la identidad de registry. Las callbacks engine-owned de destrucción, clear y reemplazo de contexto llaman SealForRetirement con esa identidad registrada.

El sello valida owner/Page/generation/world y estado vivo. En el dispatcher WebView2, sin await ni callbacks de página, marca la generación sellada antes de seleccionar sus controles vigentes. Congela exactamente Current/Revision, sin escoger el valor más largo ni consultar un histórico por timestamp. El snapshot existente sólo se reutiliza si coincide exactamente con current/revision. De otro modo se crea un snapshot inmutable ENGINE_WORLD_RETIRE. Commit valida el mismo witness, owner y current; después se retira lifecycle. Un snapshot ya consumido es idempotente, no una segunda promoción.

RetireDocument genérico no aporta un witness engine: conserva sus semantics de no inferir terminal desde pending. Un world sin controles sensibles es un conjunto vacío, no una credencial fabricada. Un control ya desconectado conserva conocimiento TRANSIENT; no se lo vuelve a asociar heurísticamente a un elemento vivo. Un control vigente sin current/revision confiables, o cualquier identidad de sello incierta, cierra sticky la frontera.

## Eventos tardíos

Una generación sellada se conserva como tal hasta el cierre de registry. Observe valida identidad y bounds, registra el buffer tardío como known y selecciona LATE_EVENT_AFTER_RETIREMENT_SEAL. No altera current/terminal, ni siquiera ante duplicate/stale revision. Require/Redact y reanudación permanecen SECRET_BOUNDARY_UNCONFIRMED. No se descarta el conocimiento para preservar disponibilidad. Overflow/expiry siguen fail-closed.

## Terminal corto y redacción

ENGINE_WORLD_RETIRE de current real con longitud 1..3 pasa por Commit y conserva SHORT_COMMITTED_VALUE → SECRET_BOUNDARY_UNCONFIRMED. TRANSIENT corto conserva exact-leaf; >=4 conserva substring protection; conocimiento monotónico, ceilings y schema-aware redaction no cambian. El leaf fix permanece byte-intacto: bounded raw leaves → redacción individual host-side → separadores/agregación → proyección pública.

## Diagnóstico

Se conservan observers escalares sólo como test infrastructure: en el ejecutable productivo son null, sin opción/configuración/IPC de debug. El sink cross y el sink C06 se incorporan únicamente por imports de build del harness. No reciben valores/DOM/URLs/credential hashes. Nuevos reasons/sites se añaden al final para no cambiar códigos diagnósticos históricos. No se certifica DLP universal, secure-memory ni forensic erasure.

## Validación

Orden A→G fijado en validation_plan.json. Los dos errores de compilación iniciales se preservan; no llegaron a inferencia ni runtime. Los resultados se agregan en artefactos separados. No Block06, AW8 E2E, READY, commit/push/tag/release.
