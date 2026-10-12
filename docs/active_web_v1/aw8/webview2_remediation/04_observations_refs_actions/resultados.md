# Active Web V1.1 — §35.2 bloque 04: observations / refs / actions

`WEBVIEW2_REMEDIATION_BLOCK_04 = PASS`

`SAFE_TO_ADVANCE_TO_BLOCK_05 = true`

Resultado limitado al adapter/contratos de este bloque. No se avanza al bloque05, no se ejecuta AW8 ni se certifica disponibilidad productiva/red.

## Baseline y alcance

Branch `main`, HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`, sin cambio. Working tree dirty previo conservado (18 tracked modifications y trabajo Active Web/native untracked heredado), staging vacío y cinco tags anteriores intactos. Freeze completo: **2397 archivos previos, 154 históricos/arquitectónicos**. Pins del bloque03 verificados antes de modificar: drift0. Arquitecturas V1/V1.1, AW0–AW8 y bloques01–03 byte-intactos al final.

Normativa aplicada: V1.1 §§6.3, 7, 12–17, 18.6–7, 19, 22, 23.1, 30, 32, **§35.2 bloque4** y §36.7. Se preservan contracts/schemas Core AW2/AW3. La normativa permite primitives internas y scripts fijos del host; `resolve` sólo inspecciona metadata, no hace click/acciones ni ejecuta código suministrado por el caller/página. No se modifica la interfaz engine-agnostic ni se introduce una segunda policy.

## Implementación

Ruta de Infrastructure: `WebView2ObservationAdapter → Named Pipe privado v4 → nova-browser-host → WebView2/CDP`. Se conserva ownership/ACL/PID del pipe y el lifecycle/UDF de bloques01–02, junto con **el mismo ExternalProtocolGuard** del bloque03. C# no importa Application/AgentLoop, no clasifica autoridad ni emite Grants.

SDK oficial **Microsoft.Web.WebView2 1.0.4258.31**, runtime observado **154.0.4258.62**, .NET SDK **10.0.203**, `net10.0-windows`, x64, Windows11/NTFS/HOST_UNISOLATED. Build/test/output/SDK feed externos al checkout; sin instalación de Runtime ni cambios globales/CA/registro.

### Captura y bindings privados

Scripts fijos/versionados `nova-wv2-observation-1` en worlds CDP aislados inspeccionan texto renderizado y metadata mínima de nodos interactivos. No DOM/HTML completo, values de inputs/passwords, cookies, headers o storage. Los bindings guardan **el RemoteObject exacto**, origin, fingerprint, epoch y versión nativos dentro del host. El modelo nunca recibe objectId/backendNodeId, selectors, JS, coordinates ni native handles.

Fingerprint incluye identidad semántica/estado compatible, connected/visibility, capabilities, label, href y destino/método de form. No contiene password/input values. La revalidación compara todos los campos del mismo nodo; la comparación atómica normaliza únicamente el orden de claves JSON, no omite campos ni relaja identidad. Nodo eliminado/reemplazado con idéntico texto permanece stale, sin búsqueda/rebind por label/selector.

Se proyectan los DTOs existentes mediante **BrowserObservationService**: refs `bwe/bwo` opacas, URL saneada/origin, title, summary, elements/forms/dialog state. `engineBinding=wvb_<GUID>` es privado entre Infrastructure/host; no selector ni DOM ID. Frames inspeccionados sólo si su origin coincide realmente con el top frame; contexts opacos/cross-origin se omiten, nunca se les inventa el origin padre. Browser-internal/about:blank sin origin publicable devuelve captura vacía, no datos internos.

El perfil IPC acotado admite hasta32 elementos solicitados,8192 chars de summary,512 de field y frame16384/payload4096 bytes heredados. Peticiones mayores se **rechazan** de forma tipada, no se limitan silenciosamente ni cambian ceilings Core. Una fila extra íntegra permite al contrato AW2 marcar `truncated=true`; esa fila no genera ref pública. Exceso de frame devuelve OBSERVATION_LIMIT, no un DTO cortado. Valores de input introducidos permanecen únicamente como conocimiento de redacción efímero acotado del host, no se copian de regreso en observation/audit.

### Freshness / epochs

Captura nueva retira el snapshot privado anterior. CLICK/INPUT/SELECT/submit/navigation/history y popup invalidan bindings; engine events de navegación/frame/history cambian identidad nativa. El manager vigente conserva ownership de los epochs/versiones **públicos**; un sink de invalidación de composición trusted sólo reduce freshness. Los counters nativos no se reinterpretan como counters Core: el binding correlaciona ambos owners/incarnations.

`BrowserObservationService.validated_target` conserva su prueba de owner/session/page/epoch/version/origin/capability y obtains proof real del adapter antes de dispatch. La operación nativa revalida nuevamente y, para acciones DOM, valida metadata del RemoteObject exacto en la misma ejecución fija que actúa. Un cambio detectado en IO invalida estado y el gate AW2 rehúsa publicar/yield un snapshot antiguo. No auto-retry para conseguir snapshot exitoso; el caller debe pedir una nueva observation.

### Acciones y frontera de efecto

Implementadas internamente: **CLICK, INPUT_TEXT, SELECT_OPTION, PRESS_KEY, SCROLL, BACK, FORWARD, WAIT**, submit por form/fields propios y navegación de links únicamente al harness local mapeado. `WAIT` usa **segundos** finitos positivos dentro del deadline vigente, preservando la semántica existente. PRESS_KEY tiene whitelist cerrada sin chords OS; focus/proof del nodo exacto y dispatch CDP fijo. Si focus produce una situación incierta, UNKNOWN; no se selecciona otro nodo por semejanza. Forms revalidan cada field y membership exacto; si ya hubo un field effect y falla la siguiente prueba, PARTIAL/UNKNOWN, no rollback/no-effect inventado.

IPC v4 añade únicamente payloads tipados de capture/resolve/act/local-navigation; no generic eval/CDP/JS/selector/launch. OperationId de acción correlacionado con el request Application. `ACTION_STARTED` nativo distingue aceptación del request y recepción de acción potencialmente effectful. Antes del boundary se puede demostrar FAILED_NO_EFFECT_CONFIRMED (tipo/key/target inválidos). Después de STARTED, disconnect/crash/timeout/cancel o pérdida de confirmación no se convierten en NOT_STARTED: **UNKNOWN**. No retries; same-operation replay en Application devuelve receipt cacheado, no redispatch.

## Evidencia nativa versus sintética

Páginas locales controladas se sirven mediante virtual-host mapping WebView2 en:

- `https://nova-local.invalid`
- `https://nova-second.invalid`

Las dos origins representan topology de harness sobre archivos privados, **no** Internet, TLS remoto confiable, BROKER_ENFORCED ni PUBLIC_ONLY. HTML sigue `UNTRUSTED_PAGE_DATA`; scripts de page actors sólo cambian el DOM del espécimen, no instruyen Application ni conceden autoridad. No global CA/ignoreHTTPSErrors. [Primitive oficial de mapping](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.setvirtualhostnametofoldermapping?view=webview2-dotnet-1.0.4258.31).

Evidencia de captura/acciones: `observation_evidence.json` y `action_evidence.json`, con snapshots públicos, receipts/outcomes, hashes de raw externo y runtime/binaries. La instrumentación fija CDP usa únicamente APIs privadas del SDK; no se expone al modelo. [API oficial de WebView2 CDP](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.calldevtoolsprotocolmethodasync?view=webview2-dotnet-1.0.4258.31), [CDP Input](https://chromedevtools.github.io/devtools-protocol/tot/Input/).

Los tests de integración usan **ActiveWebService, descriptors públicos BrowserTool, ToolRuntime, BrowserPolicyEngine, ApprovalGate, GrantIssuer y SecurityAudit reales** con el port WebView2 real. La capability DTO legacy/authority ceiling del fixture son **sintéticos para wiring**; no se presentan sus campos KNOWN true/engine legacy como descubrimiento del host ni certificación de WebView2/network. El producto/default tools sigue cerrado. Normal arguments actuales se transforman por el planner existente; no ContractOnlyBrowserTool ni executor paralelo. Todos los bindings de approval existentes (session/page/epoch/observation/target/origin/action/payload/effects/context/deadline) permanecen intactos. C# no recibe bearer Approval/Grant tokens.

## Gates

| Criterio | Resultado | Evidencia |
|---|---|---|
| STRUCTURED_OBSERVATION | PASS | Captura real visible/hidden/password/forms/iframe/disabled; sin valores privados/DOM; overflow/refusal tipados |
| OPAQUE_ELEMENT_REFS | PASS | DTOs AW2, RemoteObjects privados, duplicate labels actuando sólo sobre segundo nodo observado, cross-session/page rejection |
| FRESHNESS_AND_STALE_REJECTION | PASS | 8 actores DOM independientes: replace/remove-recreate/disable/label/href/form action/history/frame; navigation real segunda origin; refs one-use tras click/input/select/history |
| TYPED_WEBVIEW2_ACTIONS | PASS | Unión cerrada y submit; capability mismatch y key inválida fallan antes de STARTED; quotas/concurrencia conservadas |
| POLICY_APPROVAL_GRANT_PRESERVED | PASS | Mediación actual con approval/grant/audit y efecto nativo; aprobación stale rechazada; AW1–AW3 244 PASS; schemas sin cambio |
| ACTION_OUTCOME_INTEGRITY | PASS | Receipt real STARTED→SUCCEEDED, STARTED→UNKNOWN por IPC/cancel, NOT_STARTED por approval stale; no retry/rollback; FAILED_NO_EFFECT_CONFIRMED separado antes de efecto |
| CONTEXT_PROJECTION_BOUNDARY | PASS | BrowserObservationService/ContextManager existentes; current user protegido, framing tool/untrusted y filas/refs atómicas, sin elevación de cap MEMORY/RAG |

## Tests / denominadores

Comandos exactos, runtimes, timestamps/duración, XML/hashes, casos por categoría y outputs externos en **test_results.json**. Autoload de plugins deshabilitado, basetemp externo, sin nuevo skip/xfail/filter/quality retry ni inferencia de modelos.

| Suite | Resultado |
|---|---|
| Focal final host/IPC/WebView2/bloque04 | **198 PASS**, 0 FAIL/ERROR/SKIP, exit0 |
| Nuevos tests bloque04 | 42: 13 OBSERVATION_NATIVE, 20 ACTION_NATIVE, 2 OBSERVATION_CONTRACT, 7 ACTION_CONTRACT |
| Host/IPC/WebView2 heredados dentro del focal | 156 PASS; no recertificación completa bloque03 |
| AW1–AW3 focused | **244 PASS**, exit0 |
| Active Web portable contracts | **672 PASS**, exit0 |
| Security | **615 PASS**, exit0 |
| MEMORY | **791 PASS**, exit0 |
| Knowledge | **1015 PASS**, exit0 |
| Desktop | **71 PASS**, exit0 |
| TypeScript | `tsc --noEmit`, exit0 |
| Core amplio | **3411 PASS, 1 FAIL, 7 skips históricos, 53 subtests PASS adicionales**, exit1 |

XML final: `C:/Users/joseh/AppData/Local/Temp/nova-wv2-04-final03.xml`.

SHA-256: `5939b3b94d7d0c73386cec5157fbf022c329313b026f17ce280c9467aad0cf23`.

No se suman suites solapadas como denominador único HEAD; se reutiliza el inventario positivo completo aplicable actual más suites native/contract específicas. Los cambios finales de bounds son sólo módulos Infrastructure nuevos/native; la regresión heredada no utiliza esos módulos nuevos y sus archivos/rutas siguen byte-intactos. El focal final198 verifica el delta. No se repiten suites masivas para fabricar números.

### Historia de implementación preservada

1. Attempt01: **0 PASS / 1 FAIL**, HARNESS_BUG: el test nuevo consultó `.capabilities` en lugar del campo vigente `interaction_capabilities`.
2. Attempt02: **22 PASS / 10 FAIL**. PRODUCT_BUG: comparación atómica JSON dependía del orden de claves; key dispatch no tenía focus/char efectivos; history terminaba antes de NavigationCompleted. HARNESS_BUG: sleep fijo no demostraba ejecución del actor de página oculta. Se corrige sin relajar identidad/assertions: igualdad de todos los campos, entrega de key real, espera de navegación y espera bounded de evidencia read-only del cambio, **no retry de acción/calidad**.
3. Attempt03: **33 PASS / 5 FAIL**. HARNESS_BUG: fixture de mediación enviaba request AW3 privado a descriptor público; se reutilizó ActiveWebService/args actuales, sin cambiar Policy. PRODUCT_BUG: un protocolo externo denegado avanzaba epoch de documento; ahora sólo retira freshness, no inventa navegación completada/origin nuevo.
4. Attempt04: **38 PASS**. Final01 y final02: **196 PASS**, conservados antes de las reconciliaciones de compatibilidad/bounds.
5. Revisión final: WAIT segundos, frames opacos no retagged, captura no silenciosamente clamped, fila extra íntegra para truncación AW2 y fields hasta32 sujetos al payload4096 vigente. Planes suplementarios congelados antes de sus casos. Final03: **198 PASS**.

Todo XML/raw anterior permanece externo separado, con hashes; no se reescribe una corrida fallida como PASS.

### Core / deuda heredada

HOME/USERPROFILE sigue **PREEXISTING_CORE_HARNESS_DEBT / NON_BLOCKING_FOR_BLOCK04**. Test/BashTool/assertion/runner sin modificación; exit1 conservado, Core no se anuncia verde.

El FAIL JSONL observado en bloque03 queda byte-intacto en su evidencia. En esta resolución **no** se etiqueta retrospectivamente PREEXISTING: la clasificación es **HARNESS_RACE / NON_CAUSAL_TO_BLOCK04**, apoyada por ruta/test/coordinator/event stream sin cambios y espera del primer frame seguida de comprobación no sincronizada del segundo. Este run lo pasó, lo cual no sustituye ni borra el FAIL anterior.

Los siete skips corresponden a symlinks/permissions POSIX/monitor legacy, mismos IDs que el baseline. 0 nuevos skips/xfails/exclusions y ninguna regresión material nueva atribuible al bloque.

## Integridad y límites de claims

Sólo tres archivos existentes cambiaron: `WebView2Runtime.cs`, `LifecycleServer.cs`, `Program.cs`. Nuevos: `ObservationRuntime.cs`, `ObservationScripts.cs`, `ActionProtocol.cs`, `observation_adapter.py`, `action_ipc.py`, fixture HTML/tests y evidencia aditiva. 44 pins de producto, 154 históricos sin drift; arquitecturas, Application/Core/Policy/Security/Memory/Knowledge/Desktop/CI/Playwright sin modificación. UDF/jobs de la corrida final limpiados, 0 engines propios vivos.

Guard regresado de manera acotada: la capa DOM activa el handler nativo existente sobre mailto, con Cancel=true, y deniega popup en NewWindowRequested; no se retiró ni modificó ExternalProtocolGuard, no nueva campaña canary/registro OS. No se presenta engine-internal denial como enforcement del guard.

Limitaciones: perfil de observación acotado no exhaustivo/DOM dump; SDK/runtime/configuración concretos; no LLM universal/vision; receipts observan dispatch/renderer, no verdad/correctitud de servicios remotos. No transfer, credential manager, takeover Application completo, red/capability v2/tool activation ni AW8 final. No sandbox/isolation claim.

```text
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

OPEN DECISION normativa nueva: ninguna. La próxima dependencia es §35.2 bloque05, **sólo como referencia**, pendiente de nueva autorización. Sin commit, push, tag ni release; detener para revisión humana.
