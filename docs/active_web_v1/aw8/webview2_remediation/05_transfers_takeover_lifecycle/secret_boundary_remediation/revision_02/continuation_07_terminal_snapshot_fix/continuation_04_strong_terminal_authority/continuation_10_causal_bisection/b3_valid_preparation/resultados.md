# B3 — reparación del harness y medición válida

```ini
B3 = PASS
BISECTION = COMPLETED
ROOT_CAUSE_DOMAIN = PRODUCT_UDF_PROFILE_CONSTRUCTION
```

Una única B3 efectiva autorizada. La request 200 / text/plain / 35 bytes, sin Content-Disposition, produjo DownloadStarting y DownloadOperation. El callback diagnosticó la presencia y confirmó Cancel=true / Handled=true inmediatamente. **No se evaluó completion ni staging; no es un download productivo exitoso.**

## Identidad y preparación

| Constraint | Resultado |
| --- | --- |
| SESSION_FORMAT_CONSTRAINT | bws_ + exactamente 32 hex lowercase; 36 caracteres |
| INSTANCE_FORMAT_CONSTRAINT | bhi_ + exactamente 32 hex lowercase; 36 caracteres |
| UDF_BASENAME_CONSTRAINT | nova_wv2_<session>_<instance>, igualdad exacta; 82 caracteres |
| UDF_PARENT_CONSTRAINT | Absoluto, directorio existente/no reparse ni symlink, privado y writable; UDF todavía inexistente |

No se admiten IDs cortos. Se conservaron generación UUID y semántica normales. Sólo se añadió un wrapper de harness: reubica el path al parent privado corto y conserva exactamente el basename productivo. El builder/harness anteriores y todos los C# permanecen intactos.

Parent: **45 caracteres**. UDF nueva: **128 caracteres**, frente a 212 en B2-B. El parent comenzó vacío y fue verificado writable con un handle DeleteOnClose antes de lanzar el host. La UDF fue creada por la factory nativa original con su ACL privada y marker de instance. No se reutilizó el UDF microprobe ni el antiguo u3.

La validación de LifecycleServer.cs:23 y la validación de cleanup por basename/owner marker no fueron modificadas, desactivadas ni relajadas.

## Gates previos al único dispatch

Ownership validation PASS → pipe/handshake creado y correlacionado → WebView2Runtime construido según el orden del LifecycleServer original → session_create/environment real → page_create/control real → navigate_local completado → único dispatch.

Todos los gates constan como true en la evidencia. El wrapper los comprueba antes de despachar; no añadió llamadas CDP, mensajes IPC ni campos productivos.

## Comparación con B2-B

Las cinco copias C# y **la DLL completa** son byte-idénticas a B2-B. No hubo rebuild nativo. Se conservaron:

- Perform productivo (SHA-256 aa11e291156acd2363c572d8dbd3259262cdca30c6c4c083fa5bbdcb7fee5e6e), argumentos y binding exacto dentro de la nueva encarnación;
- provider productivo y MemoryStream/CreateWebResourceResponse;
- settings, environment options, controller oculto e InPrivate;
- conjunto reducido de handlers B2-B y mismo observer/cancel endpoint;
- HTML byte-exacto, origen lógico, payload35, headers actuales y timeout25s;
- SDK 1.0.4258.31 y runtime efectivo 154.0.4258.62;
- IDs nuevos con formato/semántica productiva, sin rebind ni reutilización de refs.

No se cambió DefaultDownloadFolderPath por separado. Su construcción original sigue derivando del UDF; no se volvió a investigar Q1.

## Conclusión causal acotada

| Ejecución | Resultado |
| --- | --- |
| B1 | FAIL histórico, medición válida |
| B2-B | FAIL histórico, medición válida |
| B3 anterior con u3 | BLOCKED_PRE_ENGINE_SETUP histórico, no medición nativa |
| B3 válida autorizada | PASS, primera frontera nativa restaurada |

La familia causal identificada es **PRODUCT_UDF_PROFILE_CONSTRUCTION**. No se distingue todavía parent path, longitud total, namespace o profile initialization; no se atribuye una línea causal individual ni se implementa reparación de producto.

Las tres mediciones nativas de la bisección son B1, B2-B y esta B3. La preparación fallida u3 se conserva como una invocación anterior adicional, sin convertirla retrospectivamente en FAIL nativo o PASS.

## Integridad y límites

46 pins de producto y 109 fuentes previas sin drift; sólo se añadió b3_valid_udf.py, excluido del build productivo. P1/Q1, los 14 documentos y 42 outputs de la bisección anterior, V1/V1.1 y la corrida 527 PASS / 10 FAIL siguen intactos. Los grupos de pins se solapan y no deben sumarse como denominador único.

El freeze externo de preparación precede a una corrección **sólo de comentario** (libc → ctypes); candidate_freeze_before_execution.json registra el hash final realmente ejecutado. No cambió código C# ni comportamiento entre preparación y ejecución.

El teardown ordinario reportó cleanupConfirmed=true. El parent privado retiene únicamente la evidencia diagnóstica host-owned; no se declara que esos sidecars sean el UDF o un recurso huérfano. Los 36 UDF históricos siguen intactos y CLEANUP_UNCONFIRMED.

```ini
BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = PARTIAL
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED
SAFE_TO_ADVANCE_TO_BLOCK_06 = false
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

Sin retries, B4, reparación productiva, full Block05, secrets/takeover, Block06, AW8 E2E ni commit/push/tag/release. Detenido para revisión humana.
