# SECURITY V1.2 — cierre S1

Fecha: 2026-10-03. Estado: **PASS** del gate S1 de SECURITY V1.2 §29.

Se implementaron desde cero los contratos de autoridad lógica Core y `GrantIssuer` host en Application. No se reutilizó código SECURITY deprecated. S2 no se inició y el runtime productivo conserva su comportamiento anterior. Este PASS no certifica aislamiento de procesos ni enforcement filesystem S3.

## Baseline y alcance

- Repo: `C:\Users\joseh\Downloads\nova-local-cli\nova-assistant`.
- HEAD/main: `158b60effa484cd34a58b991f3ee4ca3f808d924`.
- Nova 0.12.6; Python 3.14.6; pytest 9.1.1; Windows 11 build 26200.
- Working tree inicial: 72 entradas preexistentes, incluido S0. No se revirtió ninguna.
- 305 archivos preexistentes de código/tests/Desktop/documentación fijados y comprobados byte-identical después de S1.
- Antes de modificar: 71 tests PASS, 10 subtests PASS, 2 casos nativos deselected.
- Normas leídas: Core V1 y SECURITY V1.2. Sus hashes están fijados en el manifest.

Estado previo de S1: contratos SECURITY V1.2 y emisor confiable pendientes. Core ya tenía ExecutionContext, ToolInvocation, lifecycle, cancellation, policy/approval anteriores y transporte compartido CLI/Desktop; se conservaron.

## Archivos creados

| Archivo | Implementación |
|---|---|
| `local_cli/core/security.py` | Permission/scope/clase/capability/ceiling/subject/lifetime/request/grant, algebra, digest v1 y errores. |
| `local_cli/application/grants.py` | Issuer/ledger host, issue/derive/claim/revoke/cancel/revisions, deduplicación y one-shot concurrente. |
| `tests/security_v12/test_s1_contracts.py` | 101 casos de contratos/algebra/bindings/compatibilidad. |
| `tests/security_v12/test_s1_issuer.py` | 80 casos de emisor/lifecycle lógico/linaje/concurrencia. |
| `tests/security_v12/run_s1.py` | Harness reproducible S1 + regresión pertinente, salida nueva y estado temporal privado. |
| `docs/security_v12/s1_contratos_y_autoridad.md` | Semántica explícita, límites e integración futura. |
| `docs/security_v12/s1_resultados.md` | Este cierre. |
| `docs/security_v12/s1_manifest.json` | Baseline, procedencia, hashes, resultados y alcance. |
| `docs/security_v12/s1_evidence/` | Evidencia nueva de baseline, bloques/final, schemas, parse y preservación. |

Archivos preexistentes modificados por S1: **ninguno**. No se cambió Core AgentRuntime, Application API, ToolRuntime, schemas, CLI, Desktop, Infrastructure ni los documentos normativos. No commit/push.

## Gate S1

| Criterio | Estado | Evidencia |
|---|---|---|
| Todos los contratos de §29 implementados | PASS | Core security + Application grants. |
| grant ⊆ ceiling / child ⊆ parent | PASS | Inclusión/intersección conservadora, constraints, lifetime y linaje. |
| Inmutabilidad/binding/requestDigest versionado | PASS | Snapshot profundo; cada campo relevante invalida claim. |
| stale / revisions / one-shot / revoke / cancel / expiry | PASS | Unit y concurrencia; consumo y cancel/expiry sticky. |
| Renderer/model no emiten grant | PASS del contrato S1 | Sin endpoint público; DTO falso/copias/issuer ajeno rechazados. La composición runtime se hará en S2. |
| HOST_UNISOLATED distinto de broker enforcement | PASS | Restricción constructiva de capabilities de procesos y tests negativos. |
| Schemas públicos sin cambios | PASS | Snapshot exacto S0 y regresión Core; archivos previos byte-identical. |
| Core sin imports concretos de Application/Infrastructure | PASS | Regresión arquitectura + inspección de imports nuevos. |
| Sin implementación S2 ni seguridad externa | PASS | Sólo módulos internos nuevos; cero cambios de composición. |

## Tests y regresión

| Ejecución | Resultado | Categoría |
|---|---|---|
| Baseline previo | 71 passed + 10 subtests; 2 deselected | Unit/contract/integration pertinentes. |
| Bloque inicial contratos | 63 passed | Unit/contract incremental. |
| Contratos tras ajustes acotados | 101 passed | Unit/contract. |
| Issuer inicial | 78 passed | Unit/contract/concurrencia. |
| Final S1 | **181 passed** | 101 contratos + 80 issuer. |
| Final regresión Core | **326 passed + 10 subtests**, 1 skipped, 2 deselected | Contract/integration/mock smoke; 22 módulos pertinentes. |
| Snapshot público S0 | **1 passed** | Mock; descriptor shell sintético, sin launch shell. |
| AST/compile cinco archivos Python nuevos | PASS | Offline, sin bytecode ni import/executor real. |

Final agregado: **508 tests passed + 10 subtests**, 1 skipped, 2 deselected. El test adicional de snapshot no se incluyó en los 326 de regresión. El skip es el smoke nativo opt-in de Ollama; los dos casos excluidos son `native_shell` y `windows_cancellation`, ajenos al gate S1. No se ejecutaron inferencia real, GUI ni experimentos de seguridad host-real. Algunas regresiones Core usan hijos Python de fixtures de integración; no representan pruebas de enforcement OS.

Comandos y JUnit exactos: `s1_evidence/baseline`, `s1_evidence/final`, `s1_evidence/public_schema`. Reproducible: `python -B tests/security_v12/run_s1.py --output <directorio_nuevo>`. El snapshot público puede ejecutarse por separado mediante `tests/security_v12/test_s0_surfaces.py::test_public_base_tool_schemas_match_s0_snapshot`, usando estado temporal privado.

### Incidencias instrumentales conservadas

No se ocultaron intentos incompletos:

1. Un permiso del TMP predeterminado impidió configurar el primer harness antes de pytest. Se configuró un directorio temporal privado.
2. Dos errores de setup/teardown surgieron porque pytest incorporó un string sintético de 65 537 caracteres al test ID y excedió el límite de la variable Windows `PYTEST_CURRENT_TEST`. Se asignaron IDs breves explícitos; el input oversized y su rechazo permanecen probados. La suite corregida pasó.
3. Una regresión final restringida quedó incompleta por `PermissionError` al restaurar el cwd del checkout. No se declaró PASS para esa corrida; se repitió el mismo criterio con acceso local autorizado, obteniendo el resultado final completo.

`development_incidents.json` conserva estados y SHA-256/procedencia de esos artefactos. El log de setup que incluyó diagnósticos de entorno no se publica en el repo; se conserva en el directorio instrumental original. Las corridas finales son evidencia nueva y no reescriben las fallidas. Los mensajes instrumentales de shutdown del runtime restringido no se presentan como fallos del producto.

## Límites y deuda posterior

- S1 es autorización lógica en memoria. No implementa todavía PolicyEngine V2 ni ApprovalGate nuevo; tampoco bloquea las tools actuales hasta componer S2.
- `CapabilityGrant` no es bearer serializado. El issuer se mantiene interno; el host confiable instala ceiling/revisions y cancellation ports.
- Scopes FS son léxicos, no object/handle binding. Reparse/alias/TOCTOU/UNC y enforcement real corresponden a S3.
- Restricciones son conjunciones opacas de igualdad; cualquier futura semántica tipada debe ser explícita y versionada, no inferida por nombres.
- Duración y reusable delegation son inputs host explícitos; no se fijaron defaults de política de futuras fases.
- Ledger local y bounded derivation: no persistencia/crash recovery, auditoría S7 ni protección ante ejecución arbitraria dentro del propio proceso host.
- Claims de `HOST_UNISOLATED` describen qué request Nova autoriza, no qué recursos permitirá Windows al proceso.

OPEN DECISIONS: `SEC12-OD-01`…`SEC12-OD-07` permanecen OPEN. Ninguna impide el gate de contratos S1. No se tomaron decisiones de aprobación shell, límites de output, environment productivo, red privada, journal audit, Git o elevación.

## Estado final y siguiente fase

**S1=PASS.** Contratos/servicio interno implementados y validados; archivos y evidencia preexistentes conservados. Sin Sandboxie, launch de seguridad, migración deprecated ni cambios de aislamiento.

Siguiente fase lógica: **S2 — PolicyEngine V2 + ApprovalGate**. Deberá conectar el digest/grant a ToolRuntime y a la autoridad host compartida CLI/Desktop. No está implementada por esta solicitud.
