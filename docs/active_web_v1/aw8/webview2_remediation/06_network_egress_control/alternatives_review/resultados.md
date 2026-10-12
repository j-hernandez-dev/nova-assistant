# Block06 — revisión de alternativas: resultados

```ini
RECOMMENDATION = REPLACE_WINDOWS_BROWSER_ENGINE
RECOMMENDED_ALTERNATIVE_CLASSIFICATION = PLAUSIBLE_REQUIRES_NATIVE_PROOF
```

Se propone evaluar un host separado CEF/Chromium **con fuentes/gates nativos propios y binario fijado**, no stock Playwright/Electron/CEF ni el renderer Desktop. No hay alternativa certificada en esta revisión, ni se autoriza implementar ese host.

Windows no proporciona aquí una receta demostrada de único broker para todos los children WebView2 sin dependencias excluidas. Además, containment de paquetes no cumple por sí solo SW-disabled/RTC-disabled. El transport host-mediated para páginas reales requeriría una arquitectura fetch/rewrite amplia y no sustituye la frontera nativa. Fixed Version estabiliza una versión, no repara los canales demostrados.

La propuesta conserva broker DNS/IP/PUBLIC_ONLY, HTTPS estándar sin MITM, guard pre-effect, HOST_UNISOLATED y ausencia de admin/mutaciones globales. Requiere revisión normativa prospectiva y pruebas nativas nuevas; no traslada certificaciones del engine histórico.

Ver [análisis completo](architecture_alternatives.md), [matriz de decisión](decision_matrix.json), [mecanismos Windows](os_containment_matrix.json), [engines](engine_matrix.json), [compatibilidad](compatibility_map.json) y [fuentes primarias](sources.json).

## Preservación

```ini
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

- Block05 aceptado: 561 PASS / 0 FAIL / 0 ERROR / 0 SKIP; no se reejecutó.
- Perfil bloqueado Runtime 154.0.4258.62 X64 / SDK 1.0.4258.31: evidencia UDP/STUN y SW conservada, sin hardening nuevo.
- Cero builds, probes nativos, tests, instalaciones o operaciones de maintenance. Arquitecturas V1/V1.1 y producto byte-intactos.
- Los 36 UDF históricos siguen CLEANUP_UNCONFIRMED, sin acción sobre ellos.
- Sin Block07, AW8 E2E, commit/push/tag/release.

La integridad verificable se entrega en [integrity.json](integrity.json). Se detiene para revisión humana.
