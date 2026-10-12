# Block05 SECRET_NON_EXPOSURE — remediation revision 02

Estado: **BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = BLOCKED**.

No se modificó producto, instrumentación, tests, driver, assertions ni fixtures.
Se detuvo el preflight por una incompatibilidad material entre los requisitos de
redacción de valores cortos y dos assertions que deben permanecer byte-intactas.
No se ejecutaron pytest, nuevos hosts WebView2 ni una regresión de candidato final.

## OPEN DECISION — WV2-B05-REV02-OPEN-DECISION-001

La autorización exige conservar inmediatamente todos los buffers completos
observados, incluidos los de longitud uno. Si un valor corto conocido aparece
en un leaf page-derived que se publicaría, debe ocultarse el leaf completo o
denegarse la observation de forma tipada. No se permite ignorarlo por longitud,
hacer eviction ni redaccionar el control plane.

El driver histórico introduce el valor sensible carácter por carácter. La
instrumentación fija captura el valor actual completo en cada input. La
comparación estática —sin imprimir el buffer— confirma que el primer buffer
no vacío de longitud uno aparece también dentro de ambos textos de control
exigidos por assertions históricas:

- `test_native_an_already_observed_sensitive_buffer_is_not_forgotten`, a través
  de `check(d)`, exige que `visible_text_summary` contenga el texto literal de
  control de la página.
- `test_declared_human_secret_not_projected_after_same_origin_navigation`
  exige otro texto literal de control después de la navegación.

Ambas pruebas están correctamente preservadas; no se cambió su assertion de
no-exposure ni su assertion de transición. Pero redaccionar todo el leaf que
contiene ese buffer impide satisfacer la assertion de texto. Bloquear la
publication impide obtener la observation exitosa que también exigen.
Permitir esos textos sin protección contradice la regla de valores cortos.

Esta es una incompatibilidad de **contratos de cierre/prueba**, no una afirmación
de imposibilidad del registry monotónico o del serializer schema-aware.
Tampoco es un nuevo límite de enforcement de WebView2 ni una relectura de la
arquitectura. Se necesita una decisión humana sobre cómo reconciliar la prueba
de transición con la no-exposición, conservando la garantía de seguridad y la
historia. No se propone debilitar el requisito de secretos.

## Auditoría de los defectos autorizados

| Defecto | Estado de revision 02 |
| --- | --- |
| WV2-B05-SECRET-EDIT-CONTINUITY-002 | Confirmado históricamente; no reparado. El crecimiento trusted reemplaza pending sin añadir inmediatamente cada buffer anterior al conjunto permanente. |
| WV2-B05-SECRET-IPC-SCHEMA-003 | Confirmado históricamente; no reparado. PublicStrings recorre indiscriminadamente strings del payload y control plane; Capture y TransferMetadata están afectados. |
| WV2-B05-SECRET-CAPTURE-DISCONNECT-004 | UNKNOWN histórico preservado; no reejecutado. No se afirma RESOLVED_AFTER_003_FIX ni causalidad directa. |

La dirección técnica requerida sigue siendo: registro inmediato monotónico,
bounds sin eviction y fail-closed; construcción explícita del payload público
saneado, redacción sólo page-derived y envelope IPC fijo construido después.
Esta dirección **no se implementó** mientras el cierre requiere simultáneamente
las assertions incompatibles.

## Evidencia y límites

`secret_continuity_evidence.json` contiene el argumento estático y únicamente
booleans/longitudes/pins; no contiene el buffer ni credenciales.
`schema_redaction_evidence.json` registra el alcance del scrubber actual y la
separación necesaria, sin atribuir un fix inexistente.
`test_results.json` distingue inspección estática de pruebas nativas: **0
ejecuciones nuevas**, sin XML/JUnit nuevo ni denominador de regresión.
Los 359 PASS / 4 FAIL previos no se reutilizan como regresión final verde.

Baseline: branch `main`, HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`; working tree previo
conservado. Se comprobaron 165 pins históricos, los
67 pins del candidato previo y los nueve artefactos
de la primera remediación: drift = 0. Se conservan los 18 archivos tracked
previamente modificados. Los hashes están en `integrity.json`.

## Criterios de cierre actuales

| Gate | Resultado |
| --- | --- |
| MONOTONIC_SENSITIVE_KNOWLEDGE | BLOCKED; reparación no aplicada |
| SCHEMA_AWARE_REDACTION | BLOCKED; reparación no aplicada |
| CROSS_DOCUMENT_SECRET_REDACTION | BLOCKED; no recertificado |
| MODEL_PROJECTION_SECRET_BOUNDARY | BLOCKED; defecto previo no cerrado |
| SECRET_REGISTRY_LIFECYCLE | BLOCKED; no recertificado en nuevo candidato |
| BLOCK05_FINAL_REGRESSION | BLOCKED; no ejecutada |

## Estados preservados

```text
BLOCK05_ORIGINAL_EXECUTION = BLOCKED
BLOCK05_SECRET_BOUNDARY_REMEDIATION = BLOCKED
BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02 = BLOCKED
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = BLOCKED
SAFE_TO_ADVANCE_TO_BLOCK_06 = false
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

Los 36 UDF históricos continúan CLEANUP_UNCONFIRMED: no se inspeccionaron,
eliminaron ni mantuvieron. No se iniciaron nuevos hosts/UDF. La deuda
HOME/USERPROFILE y el FAIL JSONL de bloque 03 permanecen sin modificación ni
reclasificación. No se modificó arquitectura ni evidencia histórica, no se
ejecutó bloque 06/AW8 final/inferencia ni commit/push/tag/release.

Detenido para revisión humana y resolución de la OPEN DECISION.
