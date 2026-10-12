# Reconciliación prospectiva de assertions de transición

Decisión humana: `ASSERTION_TRANSITION_RECONCILIATION = AUTHORIZED`.
Se resuelve prospectivamente `WV2-B05-REV02-OPEN-DECISION-001`; el preflight
BLOCKED y sus seis artefactos permanecen byte-intactos.

## Alcance exacto

Sólo cambian las assertions de transición de dos pruebas. Los requisitos de
no exposición, la generación del valor, el driver, la escritura carácter por
carácter, la acción de reflexión y la navegación no cambian. No se modifica
`check(d)` ni sus otros callers.

| Test / archivo | SHA-256 antes | SHA-256 después |
| --- | --- | --- |
| native/nova-browser-host/tests/test_takeover_secret_navigation.py | `e491489a7dbee997057d70fd723db9c3a8393a8ab714c2cc494bf346ed234829` | `693703b5f249e72aa4a8db16300a5c2b91943b8b69ae2c430310eb9216123634` |
| native/nova-browser-host/tests/test_sensitive_continuity.py | `c33dc18137eb465340c2324753dd960b29269f8c746bfaf4de970cd04645575c` | `cb64741c19fb85334de03d22bf13a903141f8fc50b9136ef8d0746408e6a8136` |

### test_native_an_already_observed_sensitive_buffer_is_not_forgotten

Propósito anterior: comprobar que se ejecutó el caso controlado y se produjo
una observation post-takeover, además de demostrar que el buffer anterior no
se proyectó. La assertion compartida exigía un texto literal page-derived;
ese texto podía contener un buffer corto conocido y debía protegerse.

La nueva assertion compara una observation inicial con la posterior: misma
BrowserSession/PageRef, mismo epoch nativo de documento (caso same-document),
native observationVersion mayor, nueva ObservationRef, observationVersion
pública mayor, digest de la representación pública saneada diferente y
browserContextEpoch exactamente N+1 tras completar takeover real.

La invocación de `check(d)` en **esta función** se sustituye por sus assertions
de no-exposure/audit originales y por la comprobación estructural. El helper
compartido no cambia. No hay whitelist, excepción de longitud, sustitución
de fixture ni otro literal de página exigido como condición de transición.

### test_declared_human_secret_not_projected_after_same_origin_navigation

Propósito anterior: confirmar la transición efectiva al nuevo documento antes
de comprobar no-exposure. El literal exigido podía pertenecer a un leaf que la
frontera debía ocultar.

La prueba captura el estado host-owned antes del takeover y compara el estado
posterior: misma BrowserSession/PageRef, **engine navigation epoch mayor**,
native observationVersion mayor, nueva ObservationRef, observationVersion
pública mayor y browserContextEpoch exactamente N+1. El avance nativo confirma
la nueva encarnación de documento; la comprobación no se reduce a existencia
de una observation. La única navegación de la secuencia controlada continúa
siendo la acción original del harness, sin modificación.

## Procedencia de los campos

- `WebView2ObservationAdapter._epochs` proviene de los campos cerrados
  `engineEpoch/engineVersion` emitidos por el host y ya existentes en bloque04.
- BrowserSession/PageRef/ObservationRef/observationVersion pertenecen a los
  contratos Application ya existentes.
- browserContextEpoch se obtiene del manager tras la finalización host-owned
  del takeover, no de texto de página.
- contentDigest se calcula sobre datos públicos saneados por el servicio
  existente; no contiene un hash público de los valores raw conocidos.

Estos campos no pasan por SensitiveRedactor. Los datos de página siguen
saneándose antes de IPC. La evidencia no inventa estados ni autoridad.

## Validación y preservación

Ambos tests reconciliados pasan en la corrida focal `nvr20` del candidato
registrado en `continuation_01/candidate_freeze.json`. Denominador focal:
47/47 PASS, 0 FAIL, 0 ERROR, 0 SKIP.
XML externo: `%TEMP%/nvr20.xml`, SHA-256 `67054bf97ea45bb699b3371548955ebc242fffd9bcec8d96dbe256043e049de2`.

La corrida completa del mismo candidato se registra por separado. La evidencia
focal no sustituye la regresión final, ni permite heredar PASS de otras pruebas.

Los manifests/resultados/XML anteriores no se editan ni reinterpretan; los SHA
anteriores, el plan previo a edición y los nuevos hashes permiten distinguir
los contratos históricos de esta reconciliación autorizada.
