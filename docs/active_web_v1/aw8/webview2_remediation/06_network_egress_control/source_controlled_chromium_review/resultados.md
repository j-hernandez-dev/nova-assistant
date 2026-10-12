# Resultado — source-controlled Chromium architecture review

```ini
SOURCE_CONTROLLED_CHROMIUM = REQUIRES_SOURCE_PROTOTYPE
ACTIVE_WEB_WINDOWS_ENGINE_DIRECTION = SOURCE_CONTROLLED_CHROMIUM_CEF
PATCH_SET = LARGE_PATCH_SET
CONCEPTUAL_GATES = 22
MAINTENANCE_COST = VERY_HIGH
```

Hay fronteras concretas para RTC, Service Workers, socket/resolver/proxy y external protocols. No hay aún evidencia compilada de su integración, independencia o cobertura exhaustiva. Se necesita un source prototype; no se declara engine viable/certificado ni imposibilidad universal de Chromium.

## Hallazgos decisivos

- **RTC:** constructor Blink denegable antes de factory + backend P2P independiente. Existe GN `is_p2p_enabled`; su integración con CEF/Blink y prueba de capa B siguen pendientes.
- **SW:** gates separados de registro, activación/controller/restore y startup antes de ejecutar/importar. Un perfil vacío o unregister posterior no cumple el requisito.
- **Red:** endpoint TCP exacto owned, UDP y resolver útil directo denegados, proxy sin DIRECT/PAC/WPAD; PUBLIC_ONLY sigue únicamente en BrowserEgressBroker. No se atribuye aislamiento de red a Job Objects.
- **HTTPS:** CONNECT opaco y validación estándar; no MITM/CA permanente. Cada origin nuevo requiere fresh admission y CONNECT; propuesta de prohibir coalescing cross-origin para que el broker valide también B.
- **External protocols:** deny en dispatch y en sink Windows, independiente de UI/gesto/Approval. El cierre completo de callsites aún no está demostrado.
- **Mantenimiento:** 22 gates independientes, ocho cross-cutting y diez de churn alto. Es un fork de seguridad grande/caro, no “pocos flags”. Reproducibilidad Windows y requisitos toolchain deben comprobarse, no presumirse.

Inspección: Chromium `154.0.8037.98` / CEF `154.0.34+g14c5a08+chromium-154.0.8037.98`, commits fijados en `sources.json`. 80 fuentes fijadas obtenidas; ocho rutas no disponibles se conservan como gaps, no prueba de ausencia. No checkout completo, descarga/instalación de binarios, build, patch o test nativo en esta fase.

El stock rechazado y WebView2 bloqueado conservan su evidencia histórica. Block05 PASS pertenece sólo a WebView2; Application/Policy/Approval/Grant/DTOs/BrowserPort se reutilizan como contratos, no como certificación automática del nuevo engine.

## Única continuación propuesta

```ini
NEXT_PROTOTYPE = SC-PROTOTYPE-01 / RTC_P2P_HARD_DISABLE
PROTOTYPE_EXECUTED = false
```

Requiere otra autorización. Debe demostrar PeerConnection inutilizable, ICE ausente, STUN hits=0 y owned UDP bypass=0 en secure context, incluyendo TURN TCP/UDP/data channels y ambas capas independientes. No incluye implementar los otros gates, el adapter productivo o V1.2.

## Artefactos

- [Arquitectura y perfil](source_gate_architecture.md), [inventario completo](patch_inventory.json), [frontera de red](network_boundary_design.md).
- [Compatibilidad Block05](block05_compatibility.json), [pipeline de build](build_pipeline_assessment.json), [actualizaciones](update_model.json), [coste](maintenance_cost.json).
- [Fuentes primarias/hash/anchors](sources.json), [manifest](manifest.json), [integridad](integrity.json).

## Estados preservados

```ini
WEBVIEW2_REMEDIATION_BLOCK_05_FINAL = PASS
WEBVIEW2_BLOCK06_ARCHITECTURE = BLOCKED_ARCHITECTURAL_ENFORCEMENT_LIMIT
CEF_CHROMIUM_STANDARD_CANDIDATE = REJECTED
networkEgressControl = UNKNOWN
publicOnly = UNKNOWN
available = UNKNOWN
AW8 = BLOCKED
ACTIVE_WEB_CORE = NOT_READY
```

Los tres perfiles nuevos CEF siguen `CLEANUP_UNCONFIRMED`; no se hizo mantenimiento sobre ellos ni sobre los 36 UDF históricos. V1/V1.1, producto y evidencia anterior se mantienen byte-intactos, ver comparación de hashes en `integrity.json`.

Sin V1.2, Block07, AW8 E2E, commit/push/tag/release. **Detención para revisión humana.**
