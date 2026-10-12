# C07 continuation_02 — leaf boundary repair + cross diagnosis

## Resultado

`C07-C-SECRET-LEAF-001 = REPAIRED / FOCAL_PASS`
`CROSS_TERMINAL_ROOT_CAUSE = IDENTIFIED`
`FIRST_CAUSAL_BRANCH = RETIRE_CONTROL_CURRENT_REVISION_MISMATCH_NO_CURRENT_TERMINAL_SNAPSHOT`

Gate C real: **23 PASS / 1 FAIL cross / 0 ERROR / 0 SKIP**.
No es PASS del gate ni de Block05.

Persisten BLOCK05_SECRET_BOUNDARY_REMEDIATION_REV02=PARTIAL, WEBVIEW2_REMEDIATION_BLOCK_05_FINAL=BLOCKED, SAFE_TO_ADVANCE_TO_BLOCK_06=false.
El C07 PARTIAL y el 22/24 de continuation_01 permanecen históricos, byte-intactos.

## Fix funcional autorizado de leaves

Flujo implementado:

bounded raw page-derived leaves
→ redacción host-side por leaf
→ separadores/agregación segura
→ BrowserObservation existente.

ObservationScripts.Summary ya no concatena texto antes de entregar su frontera original al host.
Entrega sólo title propio, lista privada de TEXT leaves y marcador explícito truncated=false.
La metadata de names/labels conserva LABEL fragments privados (aria-label, aria-labelledby, labels y texto de nombre).
PageDerivedTextLeaves valida y redacta cada leaf antes del join.
Los IDs/capabilities/epochs/kind públicos quedan fuera del redactor.
Ningún nuevo leaf/DOM/selector/backend ID/coordenada/CDP object se publica al modelo.

Title, state/role/kind, labels/form names y dialogs mantienen frontera individual; href/url y transfer metadata conservan su saneamiento host-side.
[Auditoría por superficie](leaf_boundary_evidence.json).
No se modificaron reglas TRANSIENT/COMMITTED ni ceilings del registry.

### Bounds y truncation

- 1024 leaves, 32768 UTF-16 por leaf y por Summary/world.
- 65536 UTF-16 agregado raw/safe; payload privado máximo 262144 bytes UTF-8.
- Title 16384; nombre/label fragments total 16384.
- Treewalk 20000 nodos Summary / 4096 por extracción de label.
- Exceso raw: rechazo tipado/fail-closed, no slicing previo a redacción.
- truncated=false obligatorio; la salida pública sólo se trunca después de sanear.
- Los separadores host-owned se añaden después de la evaluación sensible del leaf.
- Sin DOM dump alternativo ni DLP universal.

## Tests de leaves y gate C

| Suite | Resultado |
| --- | --- |
| Nuevos leaf-boundary | 21 PASS: 15 contract + 6 WebView2 nativos |
| short-exact original focal | 1 PASS, sin tocar assertion/valor/fixture |
| Original policy 24, sin plugin diagnóstico | 23 PASS / 1 FAIL cross |
| Cross instrumentado | 1 FAIL capturado, diagnóstico causal identificado |

No skips/xfails ni quality retries.
No se modificaron tests históricos, valores, HTML/driver/sleeps/timeouts o assertions.
Los nuevos nativos comprueban text/title/label/fragments/joins y la ausencia de campos privados nuevos en el payload público.
Los contratos prueban igualdad corta exacta, substring permitido en leaf mayor, separación de leaves y rechazo de bounds.
No se presentan doubles como WebView2 real.

Python absoluto 3.14.6 / pytest 9.1.1, .NET SDK 10.0.203, WebView2 SDK 1.0.4258.31; Windows/NTFS/AMD64, offline.
[Tests/command/timestamps/exit/XML/output hashes](test_results.json).
Outputs externos: `C:/Users/joseh/AppData/Local/Temp/nova-c07-leaves-20261010T222823Z`.

La ejecución cross original dentro del gate 24 es distinta del intento instrumentado, permitido por la validación del gate.
No se usa su PASS/FAIL para seleccionar/rerun de calidad ni se excluye del denominador.

## Cross: diagnóstico sin reparación

Se añadió sólo observer interno de metadata scalar, default null en producto.
Hooks acotados a recepción/creación/rechazo de terminal, Retire y Commit; no logging de valores/input, nueva llamada CDP, URL, DOM ni hash de credential.
La colección del harness vive en memoria; máximo 1024 records, overflow invalida evidencia.
El sink se compila sólo en el ejecutable original del policy test mediante import de test y guarda metadata **al ProcessExit**, fuera de la acción.
No hay nueva authority/debug command/model field.

La instrumentación no cambia decisiones de documento/generation/revision/TerminalSnapshot/Commit/Retire ni el denial de short committed.
Puede afectar timing por su overhead de metadata; no se reclama perturbación cero.

Se ejecutó cross instrumentado **una sola vez** (máximo autorizado cinco) y se detuvo al encontrar rama inequívoca.
[Ocho eventos, preguntas y hash](cross_terminal_diagnosis.json).

### Orden observado y primer branch

1. document_2/control_1 confirma CHECKPOINT rev2, length0.
2. Ese snapshot vacío llega a COMMIT_BEGIN mientras current también es rev2/len0.
3. Antes de retirar document_2, current ya es rev5/len32.
4. RETIRE_CONTROL ve terminal confirmado rev2/len0, no current.
5. Rechaza promoción con CURRENT_REVISION_MISMATCH; RETIRE_END.

No hay recepción PAGEHIDE en esa traza antes ni después del retiro.
**No se afirma que el engine nunca lo emitiera.**
No se creó un snapshot terminal largo válido ni se despachó Commit de ese largo.
No aparece un COMMIT_REJECTED por owner/generation del largo: el primer punto causal es **ausencia de prueba terminal vigente al retirar**, no un error al ejecutar un Commit largo.

El snapshot y current son del mismo document_2/control_1; no confusión cross-generation demostrada.
Retire comprueba mismatch antes de limpiar/deactivar current; no consume un snapshot válido porque no lo hay.

Retire hace correctamente la reducción fail-closed: no inventa terminal desde current.
La ausencia upstream de un snapshot terminal largo es el defecto de continuidad por resolver.
El mecanismo más profundo de por qué no se recibió PAGEHIDE antes de perder el world sigue sin probarse.

### Propuesta para revisión, no implementada

Obtener una prueba terminal genuina y correlacionada antes/alrededor de pérdida del world, respetando revision/generation y ownership.
No permitir un stale snapshot vacío, promover pending ni escoger longest para satisfacer COMMITTED.
Se necesita autorización posterior de cross funcional.
No se tocaron su fixture, assertion ni protocolo terminal.

## Preservación y estados

Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.
[Baseline](baseline_freeze.json), [candidato congelado antes de medir](candidate_freeze.json), [integridad](integrity.json).
Candidato SHA: `7a44190861df37f2903b2f7b562f08e6ef580ce580fe24d84cd217051ed0558c`.
87 pins finales sin drift; 275 históricos, 18 tracked previos, 57 outputs históricos y dos pins del harness C06 sin drift.
Before/after registrados para los cambios funcionales y los hooks diagnósticos.

V1/V1.1, AW0–AW8, todas las remediaciones/resultados anteriores permanecen byte-intactos.
HOME/USERPROFILE y FAIL JSONL bloque03 no se reparan ni reclasifican.
La versión 22/24 no se sobrescribe con la nueva 23/24.

Todos los hosts/UDF/staging nuevos cerraron; final read-only: 0 procesos/directorios owned pendientes.
36 UDF históricos siguen CLEANUP_UNCONFIRMED, no inspección/mantenimiento/borrado.
No material sensible ni hashes de credenciales persistidos en evidencia/logs/XML.
Chequeo acotado del patrón completo del driver: 0 coincidencias, no claim universal.

networkEgressControl/publicOnly/available=UNKNOWN; AW8=BLOCKED; ACTIVE_WEB_CORE=NOT_READY.
D históricos×5, E focal33, F full, Block06 y AW8 E2E **no ejecutados**.
Sin READY, commit/push/tag/release.
**Detenido para revisión humana antes de cualquier fix cross o nueva campaña.**
