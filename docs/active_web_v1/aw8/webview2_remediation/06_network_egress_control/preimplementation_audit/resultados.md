# Block06 — auditoría previa, sin implementación

`BLOCK06_ARCHITECTURE = REQUIRES_ARCHITECTURE_REVIEW`

La arquitectura define correctamente dos fronteras independientes, pero el perfil WebView2 actual no contiene una frontera exclusiva de red. El broker existente es reutilizable; su existencia no controla los sockets del engine. No se ha demostrado una imposibilidad de WebView2 y no se declara `BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT`.

La revisión pendiente es focal: elegir y justificar un mecanismo engine-owned de deshabilitación de service workers/WebRTC y un contrato verificable de configuración efectiva/versionado para proxy, DNS y UDP. No basta copiar flags de Playwright ni usar navegación/intercepción HTTP como firewall. Las decisiones y alternativas condicionadas están en [architecture_analysis.md](architecture_analysis.md); cobertura y pruebas futuras en los JSON adjuntos.

## Hallazgos determinantes

- El host crea un Environment evergreen con cuatro flags generales; no configura proxy ni integra BrowserEgressBroker. Su metadata contiene argumentos solicitados, no una prueba de configuración efectiva.
- El broker ya autentica, clasifica todas las respuestas DNS y conecta a una IP numérica validada. CONNECT permite TLS end-to-end sin MITM, pero no inspecciona HTTP cifrado, redirects ni WebSocket dentro del túnel.
- Las primitivas inspeccionadas para workers/IP handling no equivalen a deshabilitar esas superficies. Falta especificar una primitive suficientemente fuerte para §18.2; no se afirma que no pueda existir.
- Microsoft advierte que los browser flags no son un contrato estable para producción. Un perfil certificado dependiente de ellos requiere decidir cómo congelarlo, detectar overrides/cambios y retirar su autoridad; no se sustituye por configuración global. [Documentación oficial](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/webview-features-flags).

## Ejecución e historia

Sólo inspección estática, consulta de documentación oficial y verificación de hashes/JSON. Cero builds, tests de producto o probes nativos ejecutados. No se abrió ni modificó Block05; se conserva su cierre aceptado `PASS` y la corrida histórica 561 PASS / 0 FAIL / 0 ERROR / 0 SKIP. No es evidencia de red.

Se generaron únicamente los siete artefactos de este preflight. V1/V1.1, producto, tests y evidencias anteriores permanecen intactos según [integrity.json](integrity.json). No se realizó mantenimiento sobre los 36 UDF históricos.

```ini
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
SAFE_TO_ADVANCE_TO_BLOCK_06 = true
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

El permiso para iniciar este preflight no autoriza implementar su plan ni avanzar a Block07. Sin AW8 E2E, commit, push, tag o release. Trabajo detenido para revisión humana.

