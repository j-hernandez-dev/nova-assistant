# V12-B7 — Certificación E2E final Active Web V1.2

## Resultado

```ini
V12_B7 = PASS
ACTIVE_WEB_V1_2_FINAL = PASS
ACTIVE_WEB_V1_2 = READY
READY_FOR_HUMAN_RELEASE_DECISION = true
RELEASE_APPROVED = false
ACTIVE_WEB_CORE = NOT_READY
```

El candidato actual es `AW_V12_B7_c538cc9c1a7f2e2d25ba`. Pasaron **56 casos B7**, **234 casos de regresión**, **34 comprobaciones causales** y **66 tests Desktop**: **376 casos distintos**, sin sumar repeticiones. Los resultados del candidato anterior están en `attempts/`, incluidos los fallos y sus errores de teardown. No pertenecen al candidato actual.

## Reparación causal y freeze

La prueba de usar un `downloadRef` como `ElementRef` encontró una excepción Core que escapaba al resultado tipado. `browser_actions_v12.py` convierte ahora ese rechazo previo al efecto en `PolicyInputError(INVALID_BROWSER_BINDING)`. No concede autoridad ni cambia acciones. `bootstrap_web_v12.py` carga el nuevo artefacto host-owned B7; B6 y sus evidencias permanecen intactos. Tras el nuevo freeze se ejecutaron las comprobaciones afectadas y nuevamente el corpus E2E y la regresión focal. El host DLL sigue siendo `8a80a8987d081c750f39b598e1db5f00f58ef622e0310b7bd1c5670147f3a4a6`, SDK `1.0.4258.31`, Runtime `154.0.4258.62`, X64, .NET `10.0.7`, IPC v6.

## Fronteras demostradas

- CLI y JSONL reales atraviesan AgentLoop, ToolRuntime, Policy/Grant, DNS por paquetes, pin numérico y el transporte HTTP/TLS certificado. La confianza TLS adicional es exacta y sólo del proceso de test.
- WebView2 real demuestra observación/ref opaca, aprobación exacta, denegación antes del efecto, pérdida real después de STARTED, UNKNOWN, una única acción y barrera de incertidumbre.
- Upload host-owned, download autorizado/staging/digest, drive-by sin archivo, interrupción por límite y takeover con secreto sintético pasan por la composición productiva.
- El smoke calibrado de protocolo externo tiene un handler positivo fuera de la ventana protegida y cero launches dentro. No se ejecutó una campaña de red de WebView2.
- Los cuatro estados de disponibilidad son independientes. Desktop proyecta la misma Application/backend; se verificó el bridge y se compilaron sus raíces. No se afirma una campaña GUI Electron completa ni una certificación de instalador.
- Controlled Fetch conserva GET/HEAD, TEXT/HTML_STATIC/JSON y el perfil `CF_B2_GET_HEAD_HTTP11_WINDOWS_V1`. Browser conserva `NOT_PROVIDED`/`HOST_UNISOLATED`. POST/auth/binary/cookies y FORM_SUBMIT siguen indisponibles.

## Limpieza y disposición explícita del recibo retenido

La revisión automática rechazó `Remove-Item` sobre el journal owned del primer smoke del guard, antes de ejecutar la orden, con el motivo **`blocked by policy`**. El archivo de 1.079 bytes conserva SHA-256 `7b7d1f9298719e8c7b5f7282c44d82a347553352ec23eeb8c5d9e87a04c1b968`. No se reintentó su eliminación ni se usó otro mecanismo. Sólo se obtuvo una copia de lectura para revisión. La auditoría distingue procesos/listeners/UDF/TLS/staging cerrados de journals de auditoría retenidos. El staging de 36 bytes dejado por un test fallido y su raíz vacía sí se retiraron mediante operaciones literales sobre recursos nuevos owned.

La reauditoría confirma 172 UDF ausentes, cero procesos/listeners owned, staging vacío, seis fixtures TLS limpiados, dos canaries desregistrados y 341 pins compatibles sin referencias a Temp. El journal del candidato actual se archivó y retiró mediante una operación literal separada, sobre su identidad nueva; el journal cuyo retiro fue rechazado permanece intacto.

**No se declara eliminación de todos los archivos**. El runtime cleanup exigido queda CONFIRMED. El recibo de auditoría inerte de 1.079 bytes conserva CLEANUP_UNCONFIRMED / UNCONFIRMED_POLICY_BLOCK, con causa e impacto explícitos. La sección 24 de la solicitud permite esa disposición por causa real y no exige forensic erasure. Por ello la fila CLEANUP es PASS dentro de ese contrato; no afirma eliminación del recibo ni aislamiento adicional. La revisión interna de alcance confirmó esta interpretación, sin introducir un gate de ausencia universal de archivos. Se conservan también los temporales B6 `UNCONFIRMED_POLICY_BLOCK`, comprobados inertes; no se intentó borrarlos.

## Preservación y límites

La deuda CI histórica de **99 funciones B1/B2** permanece sin cambios y no causó los fallos del candidato. El inventario global legado sigue con drift; no se anuncia PASS de esa CI. Las fuentes B7 nuevas tienen ejecución local explícita, sin fingir clasificación CI ya aprobada.

`ACTIVE_WEB_CORE` es el agregado histórico V1/V1.1, no un switch V1.2. Permanece `NOT_READY`; `AW8=BLOCKED` y el Block06 histórico permanecen byte-intactos. El namespace B7 es aditivo. Los guards de evidencia estuvieron activos y sus ACL fueron restauradas, sin restore-by-hash.

No hubo commit, push, tag, release, ampliación de capabilities ni mantenimiento de perfiles históricos. La certificación final se detiene para revisión humana.
