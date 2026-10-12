# V12-B6 â€” Snapshot e integraciÃ³n productiva

Estado prospectivo: **PASS**. Candidato de integraciÃ³n congelado; disponible para revisiÃ³n humana. B7 permanece pendiente.

```ini
V12_B6 = PASS
SAFE_TO_START_V12_B7 = true
ACTIVE_WEB_V1_2_FINAL = NOT_CERTIFIED
ACTIVE_WEB_CORE = NOT_READY
RELEASE_APPROVED = false
```

## ComposiciÃ³n productiva

CLI y JSONL/Desktop construyen `WebV12Factory` dentro de la misma `AgentSessionCoordinator`. `WebProductV12` conecta el catÃ¡logo a `ToolRuntime`, el `PolicyEngineV2` existente, `ApprovalGate` y el mismo `GrantIssuer`. El prompt JSONL se recompone con las tools realmente registradas. Los flags empiezan deshabilitados y se configuran mediante controles humanos autenticados.

`WebCapabilitiesV12`, schema `WEB_CAPABILITIES_V12_1`, mantiene dos ramas independientes. Es metadata sin grants, sesiones, refs, credenciales ni autoridad reutilizable. `activeWeb`/`BrowserCapabilitySnapshot V1` conserva su contrato histÃ³rico y no activa V1.2.

| Capability | Claim | Perfil / lÃ­mites |
| --- | --- | --- |
| Controlled Fetch | `networkEgressControl=ENFORCED`, `publicOnly=ENFORCED` en el perfil compatible | `CF_B2_GET_HEAD_HTTP11_WINDOWS_V1`; GET/HEAD, TEXT/HTML_STATIC/JSON; POST/auth/binary download/cookies no disponibles |
| Interactive Browser | `networkIsolation=NOT_PROVIDED`, `controlClass=HOST_UNISOLATED` | WebView2 SDK 1.0.4258.31, Runtime 154.0.4258.62, x64; IPC privado v6; .NET 10.0.7 fijado sin roll-forward |

La disponibilidad se calcula de nuevo con hashes de fuente/binario/configuraciÃ³n, runtime observado, protocolo, esquema, familia de Policy y composiciÃ³n. Un fallo conocido produce `KNOWN false` con razÃ³n tipada. `UNKNOWN` se reserva a observaciones realmente indeterminadas. La aceptaciÃ³n de riesgo habilita configuraciÃ³n; cada efecto remoto conserva su propio Approval/Grant.

## Routing y autoridad

La necesidad de informaciÃ³n se dirige a Controlled Fetch. Una peticiÃ³n humana explÃ­cita de investigaciÃ³n pÃºblica puede admitir URLs candidatas estÃ¡ticas sin query; el transporte conserva admission/DNS all-answer/S5/numeric pinning. Las URLs con query necesitan el alcance exacto de la peticiÃ³n humana y las conocidas como sensibles se rechazan.

Browser requiere una necesidad funcional validada del task humano, Ã¡mbito, disponibilidad y aceptaciÃ³n de riesgo. 401/403, timeout, truncation, private/mixed DNS, redirect prohibido, scheme, scope o texto de pÃ¡gina no conceden fallback. El ledger pertenece a la lineage web del AgentSession, estÃ¡ acotado a 256 entradas y 30 minutos, y compara objetivo canÃ³nico; denials de destino/DNS tambiÃ©n cubren el mismo origin. Su saturaciÃ³n falla cerrada. No es una blacklist global permanente ni un aislamiento del trÃ¡fico interno del browser.

El catÃ¡logo Browser utiliza exclusivamente acciones fijas certificadas y refs opacas. La navegaciÃ³n inicial aÃ±ade una seam privada v6 para un destino exacto host-owned; el modelo propone `web_access` y Application emite el binding/Grant. No hay JS, selector ni comando genÃ©rico del modelo. `FORM_SUBMIT=NOT_ENABLED`.

El picker host-owned liga el upload a la operaciÃ³n y ref actuales antes de pedir Approval de disclosure. Downloads conservan staging, digest, ownership, lifetime y descarte explÃ­cito, con provenance Browser separada de Fetch. El takeover pausa acciones; el finish autenticado requiere continuidad terminal/secretos, epoch nuevo y observaciÃ³n fresca. Una incertidumbre mutante bloquea nuevas mutaciones. El cierre de los adapters es idempotente.

La delegaciÃ³n elimina permisos Browser, scopes CF/IB y tools V1.2 del parent Grant. Metadata de capacidad no proporciona autoridad al subagent.

## Evidencia y verificaciÃ³n

- Suite focal: **173/173** (170 nuevos y 3 del guard reutilizado), sin failures/errors/skips.
- Desktop: **66/66** (34 nuevos y 32 reutilizados); TypeScript pasa.
- RegresiÃ³n afectada: **882 casos distintos PASS**. Incluye B1 completo, contratos B2, S5, Policy/Approval/Grant, Core/Session, refs/actions, transfers/terminal y primitives nativas focales B3/B4/B5.
- Total distinto aprobado: **1121**. Las repeticiones y los PASS histÃ³ricos no se suman.
- CLI y JSONL proyectan los cuatro estados desde Application real con el candidato WebView2 congelado. `DesktopApplicationClient` consume esos mismos frames y verifica cuatro proyecciones sin aÃ±adir autoridad. Esto no es el E2E de B7.
- El transporte Fetch atraviesa DNS UDP owned y TCP HTTP/HTTPS reales hacia un IPv6 global actualmente asignado. El trust TLS es exclusivo del proceso/fixture; no hubo modificaciÃ³n global de CA ni excepciÃ³n PUBLIC_ONLY.
- El browser demuestra read, Approval/effect, pre-effect denial, UNKNOWN/no retry, picker/upload, download/staging, takeover y secretos reales. Provider/scripted proposals sÃ³lo sustituyen la producciÃ³n de propuestas del LLM.
- Los tests se ejecutan con outputs en temporales owned, veto Python y DACL NTFS del harness. Los resultados se congelan despuÃ©s de restaurar ACL. La integridad conserva V1/V1.1 y B0â€“B5 byte-intactos; no se restaura evidencia histÃ³rica por hash.

## Incidencias preservadas y alcance

La primera expectativa de cero requests internos durante un redirect WebView2 fallÃ³: el engine contactÃ³ el destino. Se conserva el intento fallido. La comprobaciÃ³n correcta certifica `UNKNOWN` y ausencia de nueva autoridad/observaciÃ³n Nova del destino no confirmado. **No se certifica aislamiento de red del browser.**

La comprobaciÃ³n CI histÃ³rica detectÃ³ 99 funciones B1/B2 sin clasificaciÃ³n, ya presentes en el baseline. Su failure permanece registrado en los intentos y `ci_inventory_debt.json`; migrar ese inventario no es un gate de seguridad B6. Los 28 tests opt-in de la antigua campaÃ±a nativa S5 no ejecutados permanecen listados separadamente; el smoke productivo real B6 sÃ­ se ejecutÃ³. No se reejecutÃ³ la campaÃ±a 561 ni browser network hardening.

El harness agentic Browser usa ventana 32768 y provider sintÃ©tico de propuestas; no certifica calidad del LLM ni latencia E2E. Ventanas pequeÃ±as siguen sujetas al rechazo del ContextManager existente. Opt-in/risk acknowledgement vive en la configuraciÃ³n del Application actual, sin activar una release por defecto. La continuidad de staging estÃ¡ ligada a su owner/lifetime y no equivale a recuperaciÃ³n de artefactos tras un backend crash.

## Archivos

Ver [source_changes.json](source_changes.json) para los 18 archivos existentes modificados y sus SHA antes/despuÃ©s. Nuevas piezas: `bootstrap_web_v12`, `web_product_v12`, `web_routing_v12`, `web_capabilities_v12`, `web_discovery_v12`, codec/adapter privado productivo v6, `ProductiveProtocol.cs`, helper Desktop de controles humanos y corpus B6. El inventario completo estÃ¡ sellado por [integrity.json](integrity.json).

Los registros originales de B0â€“B5, V1/V1.1, Block05 PASS, Block06 bloqueado, CEF rechazado, source-controlled Chromium pendiente de prototipo y AW8 bloqueado permanecen intactos.

## Cleanup final

Se comprobaron 153 identidades UDF nuevas de los intentos, todas ausentes y sin auxiliares owned restantes. La ejecución focal final confirmó las 23 instancias instrumentadas. Los listeners HTTP/DNS, archivos TLS del fixture, staging y copias de upload se cerraron/retiraron según sus tests. Dos objetos de constructor sin PID se conservan en la evidencia original y se revalidaron sin UDF existente.

La revisión automática rechazó el borrado recursivo de los directorios temporales owned de la campaña con `blocked by policy`. Esos temporales de build/cache/fixture permanecen con `TEMP_CLEANUP=UNCONFIRMED_POLICY_BLOCK`; no se afirma que hayan sido borrados. Los resultados ya están congelados bajo B6. Esta retención de temporales no afecta los 14 gates de integración ni recalifica los cierres históricos. No se usó otro mecanismo para eludir el rechazo.
