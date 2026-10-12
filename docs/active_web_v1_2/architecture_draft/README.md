# Active Web V1.2 — borrador para revisión humana

Fecha de decisión y borrador: **11 de octubre de 2026**.
Fase exclusiva: `ACTIVE_WEB_V1_2_ARCHITECTURE_DRAFT`.

```ini
ACTIVE_WEB_V1_2_ARCHITECTURE = READY_FOR_HUMAN_REVIEW
IMPLEMENTATION_AUTHORIZED_BY_THIS_DRAFT = false
PRODUCT_MODIFIED = false
```

La decisión humana abandona por ahora mantener un fork de Chromium: la evaluación anterior
requiere source prototype, un patch set grande, 22 gates conceptuales y mantenimiento muy alto.
La decisión responde al coste/beneficio de Nova; no declara imposibilidad técnica. No se ejecuta
`RTC_P2P_HARD_DISABLE`, se construye Chromium ni se retoma esa certificación.

V1.2 propone dos capacidades independientes: **Controlled Fetch** para HTTP(S) controlado
y **Interactive Browser** para interacción real con páginas. La primera podrá certificar
enforcement de sus conexiones y destinos públicos; la segunda declarará inequívocamente
`networkIsolation = NOT_PROVIDED`, con controles fuertes sobre la autoridad y acciones de Nova.

Leer en este orden:

1. [Arquitectura, contratos y routing](architecture.md).
2. [Threat model y alcance de los claims](threat_model.md).
3. [Reutilización de cada garantía de Block05](block05_reuse.md).
4. [Roadmap V1.2 y decisiones mínimas](roadmap.md).
5. [Manifest prospectivo](manifest.json) y [verificación de preservación](integrity.json).

Los textos son propuestas normativas para una aprobación posterior. Los ejemplos de snapshots
certificados describen estados futuros, no disponibilidad actual ni resultados de tests.
`baseline.json` fija los documentos, fuentes y configuración preexistentes; `integrity.json`
comprueba que ninguno cambió en esta fase. No se ejecutan suites de producto ni pruebas nativas.

El repositorio con la evidencia de Active Web es
`C:/Users/joseh/Downloads/nova-local-cli/nova-assistant`. El directorio inicial
`C:/Users/joseh/Downloads/nova-assistant` corresponde al histórico previo B19 y no se modifica.
La tarea y conversación permanecen las mismas.

Historia preservada, sin recalificación:

```ini
Active Web V1.1:
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
WEBVIEW2_BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

El PASS final de Block05 corresponde a la composición WebView2 evaluada con **561 PASS**.
Los documentos anteriores BLOCKED/PARTIAL permanecen como evidencia de sus propios intentos.
V1.2 cambia prospectivamente el alcance; no convierte V1.1 en PASS ni en disponible.

No se inicia Block07 histórico ni AW8 E2E histórico. Sin cambios de producto, contratos ejecutables,
CI, dependencias o configuración; sin commit/push/tag/release. Sin mantenimiento sobre perfiles CEF,
los 36 UDF históricos ni otros recursos de campañas previas. Se detiene para revisión humana.
