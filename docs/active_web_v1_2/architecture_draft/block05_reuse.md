# Block05: reutilización sin trasladar certificación

Estado: clasificación prospectiva V1.2, 11-10-2026. **No cambia el PASS histórico.**

Fuente final aceptada:
[resultados de continuation_11_product_udf_construction_fix](../../active_web_v1/aw8/webview2_remediation/05_transfers_takeover_lifecycle/secret_boundary_remediation/revision_02/continuation_07_terminal_snapshot_fix/continuation_04_strong_terminal_authority/continuation_11_product_udf_construction_fix/resultados.md),
[manifest](../../active_web_v1/aw8/webview2_remediation/05_transfers_takeover_lifecycle/secret_boundary_remediation/revision_02/continuation_07_terminal_snapshot_fix/continuation_04_strong_terminal_authority/continuation_11_product_udf_construction_fix/manifest.json)
y [regresión](../../active_web_v1/aw8/webview2_remediation/05_transfers_takeover_lifecycle/secret_boundary_remediation/revision_02/continuation_07_terminal_snapshot_fix/continuation_04_strong_terminal_authority/continuation_11_product_udf_construction_fix/regression_results.json).

```ini
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
BLOCK05_ACCEPTED_FULL = 561 PASS / 0 FAIL / 0 ERROR / 0 SKIP
WEBVIEW2_BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
```

Los 561 tests no certificaron PUBLIC_ONLY ni aislamiento de red del engine. La capability
sintética del wiring acreditaba el camino ToolRuntime/Approval/Grant, no disponibilidad productiva.
Los intentos previos BLOCKED/PARTIAL permanecen con su estado; no se fusionan denominadores.

## 1. Clases exactas

| Clasificación | Significado |
| --- | --- |
| `REUSABLE_AS_ARCHITECTURE_CONTRACT` | La regla de dominio/autoridad se conserva; reutilizarla exige pruebas de su composición nueva, sin conceder PASS automático |
| `WEBVIEW2_CERTIFICATION_ONLY` | El resultado, mecanismo o aggregate PASS pertenece a versión/SDK/host/UDF/configuración WebView2 evaluados |
| `REQUIRES_V1_2_RECERTIFICATION` | El control sigue siendo obligatorio y debe demostrarse bajo las autoridades/snapshots/adapter/lifecycles V1.2 |
| `REMOVED_FROM_THREAT_MODEL` | V1.2 deja de prometer el control para Interactive Browser; no borra evidencia ni retira el mismo control de Controlled Fetch |

Una fila tiene una clase principal. “Contrato reutilizable” no significa autorización de uso
ni binary compatibility. “WebView2 only” no obliga a reimplementar todo: se puede conservar el
mecanismo existente y probar deltas/integración en la composición V1.2 recomendada.

## 2. Inventario completo del cierre final Block05

Las siguientes **30 filas** cubren cada identificador `= PASS` del documento final aceptado,
incluidos sus cuatro identificadores agregados. Cada fila indica aplicación en V1.2.

| Garantía histórica | Clasificación principal | Controlled Fetch | Interactive Browser y evidencia futura |
| --- | --- | --- | --- |
| `PRODUCT_UDF_PROFILE_CONSTRUCTION_FIX` | `WEBVIEW2_CERTIFICATION_ONLY` | No UDF/browser profile | Conservar constructor known-folder/ownership/path budget probado sólo para ese perfil; validar entorno y lifecycle del adapter V1.2 |
| `C07_TERMINAL_SNAPSHOT_FIX` | `WEBVIEW2_CERTIFICATION_ONLY` | Sin terminal DOM | Aggregate de reparación host/IPC del candidato; no nuevo PASS V1.2 |
| `BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02` | `WEBVIEW2_CERTIFICATION_ONLY` | Redacción explícita de credenciales API separada | Aggregate de secretos del candidato WebView2; recertificar uso del nuevo snapshot/proyección/takeover |
| `WEBVIEW2_REMEDIATION_BLOCK_05_FINAL` | `WEBVIEW2_CERTIFICATION_ONLY` | Ninguna herencia de suite browser | PASS inmutable de 561; no publicOnly, no availability V1.2 |
| `DOWNLOAD_NATIVE_INITIATION` | `REQUIRES_V1_2_RECERTIFICATION` | Iniciar HTTP typed/transfer propio, no callback WebView2 | Revalidar mismo DownloadStarting/SDK en composición V1.2 y permit browser exacto |
| `DOWNLOAD_DRIVE_BY_DENIAL` | `REQUIRES_V1_2_RECERTIFICATION` | Respuesta/Content-Disposition no inicia transfer automático | Cancel pre-file-effect del engine con permit ausente/stale; primera escritura no debe preceder guard |
| `DOWNLOAD_STAGING_LIFECYCLE` | `REQUIRES_V1_2_RECERTIFICATION` | Streaming staging con owner/capability/expiry/digest propios | Context/browser close no borra automáticamente staging retenido; owner/lifetime/discard veraces |
| `DOWNLOAD_TOOLRUNTIME_APPROVAL_PATH` | `REQUIRES_V1_2_RECERTIFICATION` | network.fetch y FILE_DOWNLOAD distintos de browser grant | Nuevo binding sin `network=PUBLIC_ONLY`; exact ToolRuntime/Approval/Grant, sin synthetic ceiling productivo |
| `CONFIRMED_TERMINAL_CAN_RESUME` | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | No resume DOM | Resume sólo con autoridad terminal legítima/continuidad, epoch nuevo y observación segura |
| `UNCONFIRMED_TERMINAL_FAILS_CLOSED` | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | Transfer/request incierta no certifica complete | Sin terminal/lineage sensible comprobados, bloquear resume/proyección; no recolección optimista |
| `HUMAN_TAKEOVER_BOUNDARY` | `REQUIRES_V1_2_RECERTIFICATION` | No login/takeover ni cookies | Pausa/actor host/retorno real; no gestos/modelo que emitan aprobación; login no autoriza mutaciones |
| `BROWSER_CONTEXT_EPOCH_INVALIDATION` | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | Request/transfer version propios, no epoch browser compartido | Navegación/takeover/recreación invalidan refs/selections/approvals; integración B4/B5 |
| `SECRET_NON_EXPOSURE` | `REQUIRES_V1_2_RECERTIFICATION` | SecretRef API privado + redacción del resultado; sin cookies | Política de declared-sensitive/known values en todas las superficies públicas, no DLP universal |
| `HOST_FILE_SELECTION_AUTHORITY` | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | No permiso automático para POST de archivos | HostFileSelectionRef owned, file identity/revision/MIME/digest/lock y scope; browser grant propio |
| `WEBVIEW2_UPLOAD_PATH` | `WEBVIEW2_CERTIFICATION_ONLY` | Ninguna vía DOM/CDP | Asignación al nodo/copia privada probada en WebView2; revalidar la misma ruta bajo bindings V1.2 |
| `DOWNLOAD_AUTHORIZATION_AND_STAGING` | `REQUIRES_V1_2_RECERTIFICATION` | Permiso y network proof del HTTP client | Permit download browser distinto, Completed/digest/limits; no confundir staging compartido con authority |
| `TRANSFER_OUTCOME_INTEGRITY` | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | STARTED/UNKNOWN/PARTIAL, no POST/transfer retry | No-effect sólo probado; loss tras STARTED ambiguo, sin replay ni rollback ficticio |
| `HOST_UDF_CHILD_LIFECYCLE` | `REQUIRES_V1_2_RECERTIFICATION` | Owned sockets/request/staging, sin procesos browser | Controller/Job/process tree/profile cleanup sólo de instancias nuevas owned; sin claim de red aislada |
| `STRONG_TERMINAL_AUTHORITY` | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | HTTP framing/EOF no son authority de mutación siguiente | Únicamente SUBMIT_CONFIRMED/TAKEOVER_END_CHECKPOINT; señales de contenido o silencio no bastan |
| `TERMINAL_SNAPSHOT_PROVENANCE` | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | Receipt/transport provenance propio de fetch | Snapshot ligado a fuente/instance/lineage/epoch host; nunca prueba sólo porque una página lo declare |
| `CONTROL_DOCUMENT_ORDERING` | `REQUIRES_V1_2_RECERTIFICATION` | No documentos/control channel DOM | Comprobar mismo orden IPC/host/lineage antes de nueva proyección/acción |
| `LATE_EVENT_REJECTION` | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | Eventos request/owner/operation stale rechazados | Eventos de documento/epoch/instance/operation anterior no restauran refs ni authority |
| `TRUE_SHORT_COMMITTED_DENIAL` | `REQUIRES_V1_2_RECERTIFICATION` | No seal de DOM | Terminal corto genuino sin prueba suficiente sigue denegado; no relajarlo para pasar tests |
| `BOUNDED_TRANSIENT_SENSITIVE_VALUE_POLICY` | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | Registro finito de API secrets suministrados; expiry scoped | Registry/policy finitos, fail-closed al agotar continuidad/capacidad; sin extracción indiscriminada |
| `MONOTONIC_SENSITIVE_KNOWLEDGE` | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | Secrets conocidos no reaparecen en resultado | Conocimiento sensible no se pierde por reemplazar documento/takeover dentro de lineage vigente |
| `SCHEMA_AWARE_REDACTION` | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | Result/audit/headers permitidos schema-aware | Leaf-before-aggregation, nombre/valor/meta/projection cubiertos; DTO nuevo necesita pruebas |
| `CROSS_DOCUMENT_SECRET_REDACTION` | `REQUIRES_V1_2_RECERTIFICATION` | No DOM; redirects/resultados auth tienen redacción propia | Navegación/destrucción de context y reflexión sintética conservan protección sin presentar otro PASS |
| `MODEL_PROJECTION_SECRET_BOUNDARY` | `REQUIRES_V1_2_RECERTIFICATION` | Contexto sólo de output redacted finito | Ningún campo nuevo del snapshot/observations/frontend/audit hace reaparecer material sensible |
| `SECRET_REGISTRY_LIFECYCLE` | `REQUIRES_V1_2_RECERTIFICATION` | Owner/operation/expiry y no importación browser secrets | Registry finito por sesión/lineage; retiro no permite resume inseguro; sin forensic erasure |
| `BLOCK05_FINAL_REGRESSION` | `WEBVIEW2_CERTIFICATION_ONLY` | No herencia de denominadores browser | Resultado congelado; V12-B7 tiene suite/nombre/evidencia propios |

## 3. Contratos transversales heredados y claims retirados

Estas filas añaden reglas de arquitectura relacionadas con Block05, **no nuevos PASS de Block05**.
No se atribuye a su suite un cierre que pertenecía a otros bloques o nunca se logró.

| Contrato/claim | Clasificación | Tratamiento V1.2 |
| --- | --- | --- |
| ToolRuntime/Policy/Approval/Grant y ceilings | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | Misma cadena de autoridad, nuevos capabilityId/scopes/bindings; tests de mezcla negativa |
| BrowserPort, refs opacos, lifecycle/quotas y outcomes | `REUSABLE_AS_ARCHITECTURE_CONTRACT` | Nombres/conceptos reutilizables; no second AgentLoop ni selector/JS del modelo |
| ExternalProtocolGuard pre-effect DENY_ALL | `REQUIRES_V1_2_RECERTIFICATION` | Sigue obligatorio para Interactive Browser. El guard de Block03 y regresión Block05 sólo certificaron WebView2 anterior |
| PRIVATE IPC/framing/owner y DTO projection | `REQUIRES_V1_2_RECERTIFICATION` | Nuevos snapshots se validan strict; endpoints/paths/secret refs nunca autoridad aportada por página |
| Browser binding/usable disponibles sólo si `network=PUBLIC_ONLY` | `REQUIRES_V1_2_RECERTIFICATION` | Sustituir prospectivamente en V1.2 por capability browser NETWORK_ISOLATION_NOT_PROVIDED y guard/authority/secrets; conservar predicate/DTO V1 para lectura histórica |
| Exhaustive browser network isolation / todo socket browser mediado | `REMOVED_FROM_THREAT_MODEL` | No claim Interactive Browser; Controlled Fetch sí certifica exclusivamente su camino de egress |
| WebRTC globalmente disabled/P2P ausente | `REMOVED_FROM_THREAT_MODEL` | Browser tiene riesgo residual; Controlled Fetch no tiene este engine/canal |
| Service Workers globalmente disabled, incluso restore/background | `REMOVED_FROM_THREAT_MODEL` | Browser tiene riesgo residual; lifecycle owned no afirma ausencia durante la sesión |
| QUIC/browser NetworkService cerrado para cada context | `REMOVED_FROM_THREAT_MODEL` | Configuración defensiva opcional; no requisito source-controlled ni prueba universal de sockets |
| Engine PUBLIC_ONLY como requisito de available browser | `REMOVED_FROM_THREAT_MODEL` | `networkIsolation=NOT_PROVIDED`; namespace nuevo. Fetch PASS no habilita browser |
| Fork Chromium/contención SO/hostile-engine containment | `REMOVED_FROM_THREAT_MODEL` | Dirección pospuesta por coste; no era PASS Block05. Reabrir sólo por nueva decisión humana |

La categoría REMOVED no elimina secret non-exposure, exact approval, guard, lifecycle, ref
invalidation ni transfer ownership. No se conserva un “PUBLIC_ONLY de mejor esfuerzo”.

## 4. Historia y criterio de uso

V1/V1.1 y cada resultado histórico quedan byte-intactos. Se registra prospectivamente:
**V1.1 Block05 PASS; Block06 BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT.** En particular, el
stock CEF rechazado y la revisión source-controlled que requiere prototipo no pasan a aprobados.

Los tres perfiles CEF siguen con su estado `CLEANUP_UNCONFIRMED`; los 36 UDF históricos no
se revisan, borran ni cuentan como cleanup de V1.2. Las nuevas pruebas futuras sólo actúan
sobre perfiles/roots/instances propios recién creados y dejan estados veraces ante locks.

Reusar el mismo WebView2 permite focalizar recertificación en cambios de autoridad, snapshot y
composición, y ejecutar regresión existente intacta donde corresponda. Un runtime/configuración
distinto exige probes focales propios; no un programa general de 22 gates. Cambiar a otro engine
no traslada mecanismo nativo ni pruebas de Block05. Si una frontera V1.2 requerida falla,
detener esa capacidad para revisión humana sin debilitar el contrato ni repetir para borrar FAIL.
