# SECURITY V1.2 — S8: adversarial / E2E

Estado de implementación: **PARTIAL**. Gate S8: **NO SATISFECHO**.
`NOVA_SECURITY_V1_2_READY = false`. Fecha de contexto: 2026-10-04.
No se implementó otra fase, no hubo commit/push ni cambios de GPU.

## Baseline y preservación

Se leyeron íntegramente Core V1 y SECURITY V1.2, y se inspeccionó el checkout
actual, no el proyecto/branch SECURITY deprecated. Branch `main`, HEAD
`158b60effa484cd34a58b991f3ee4ca3f808d924`, staging vacío. El working tree ya
contenía Core y S0–S7 sin commit, incluyendo eliminaciones previas de
README.easy-ja.md, README.ja.md y hello.py; se conservaron.

Snapshot previo: `s8_evidence/before.json`, 1.004 archivos, incluidos 648
archivos SECURITY históricos y siete de arquitectura. Los 149 pins de S7
coincidían antes de modificar. S0–S7 permanecen como evidencia histórica,
incluido el PASS manual de S3 y la evidencia con WinError 1314.

Baseline autorizado: 1.248 pruebas Python PASS, diez subtests PASS y doce Node
PASS; un smoke Ollama opt-in no solicitado en esa corrida y tres pruebas GPU
excluidas expresamente. Una primera ejecución restringida no pudo crear su
directorio temporal (WinError 5); fue un fallo de setup, no un resultado del
producto. Evidencia: `s7_evidence/s8_baseline_authorized_20261004/run.json`.

La revisión final conserva todos los archivos previos: sólo cambian respecto
al snapshot `local_cli/git_capability.py` y
`tests/test_nova_core_phase14_platform.py`. El staging y HEAD siguen intactos.

## Gate exigido

S8 exige los 28 SEC12-INV-001..028 en Windows soportado, cobertura adversarial,
FS alias/reparse nativo, shell destructivo con approval, stdin/output/lifecycle,
web_fetch, environment/secrets, audit, subagentes, CLI/Desktop sobre Application,
Ollama local, Git/RAG opcionales y regresión Core pertinente. Los límites por
superficie deben estar publicados. Una matriz de cobertura no es un PASS.

Se mantienen `AgentRuntime -> puertos Core`, ToolRuntime común, decisiones en
Application, adapters/brokers/launcher en Infrastructure y backend compartido.
No se añadieron schemas públicos, modelos de aislamiento ni dependencias de
seguridad. `HOST_UNISOLATED` no se presenta como confinamiento físico.

## Implementación y archivos

| Archivo creado/modificado por S8 | Trabajo |
|---|---|
| local_cli/git_capability.py | Ambos probes literales de consulta Git cierran stdin con DEVNULL y usan close_fds=True. |
| tests/test_nova_core_phase14_platform.py | Fixture nativa Unicode/cwd/exit usa locale compatible LANG y configura UTF-8 en su propio script; no exige herencia de variables internas/hook que S6 prohíbe. |
| tests/security_v12/run_s8.py | Corridas frescas, perfiles sin credenciales fuera del workspace, hashes, XML/logs, regresión, opt-in host/E2E, Node/build; no certifica PASS automáticamente. |
| tests/security_v12/test_s8_contracts.py | Cobertura exacta de los 28 invariantes, contratos y claims de producto. |
| tests/security_v12/test_s8_adversarial.py | Injection forzada, args extra, elevación/bloqueos, errores tipados, replay de efecto incierto sin reintento. |
| tests/security_v12/test_s8_git.py | Stdin/handles de probes y Git opcional ante timeout. |
| tests/security_v12/test_s8_host.py | Shell destructivo permitido/denegado en archivos fixture; spoof y frontera real shell/S3. |
| tests/security_v12/test_s8_e2e.py | Backend JSONL, proof canónico/spoof, CLI, Electron y Ollama instalado; criterio de copia literal sin mock. |
| tests/security_v12/s8_backend_entry.py | Entrada exclusiva de tests; composition productiva, sin probe GPU ni updater. |
| desktop/tests/electron_s8.cjs | Wrapper del harness Core actual con Electron/main/preload/React reales. |
| desktop/tests/finish_electron_s8.cjs | Finaliza sólo el artefacto generado de instalación Electron, con checksum de ZIP y executable verificados. |
| docs/security_v12/s8_limits.md | Publicación de claims limitados por superficie. |
| docs/security_v12/s8_matrix.json | Mapeo de 28 invariantes y familias obligatorias adicionales. |
| docs/security_v12/s8_resultados.md y s8_manifest.json | Resultados, criterios no cerrados y pins. |
| docs/security_v12/s8_evidence/** | Evidencia nueva, snapshot, incidentes de setup, intentos anteriores y verificación final. |

Los stacks nativos localizaron un bloqueo antes de GenerationStarted en
`capture_capabilities -> git --version -> subprocess.communicate`, con stdin
del pipe de control heredado. El cambio mínimo de los dos probes permite
alcanzar Ollama/tools y cerrar los E2E Desktop. No introduce un servicio Git
dedicado ni resuelve arbitrariamente SEC12-OD-06.

El test nativo Core previo suponía que NOVA_NATIVE_TEST/PYTHONIOENCODING se
heredaban deliberadamente. Se alineó con S6 autorizado, conservando Unicode,
quoting, cwd, stdout, stderr, exit 7 y ausencia de cambios globales. El pass
adicional exacto sigue cubierto por cuatro pruebas nativas de S6; no se amplió
el environment permitido para hacer pasar una fixture obsoleta.

Desktop: instalación local autorizada desde package-lock existente, 471 paquetes.
Sin modificar package.json/lock, empaquetar/publicar ni añadir infraestructura
SECURITY. Postinstall bloqueado/incompleto y deadlines de instalador quedan
registrados en `setup_incidents.json`. Electron 33.4.11 proviene del ZIP oficial
cacheado, validado contra checksums.json, con executable idéntico a su entrada
ZIP y módulo resuelto. TypeScript y Vite pasan.

## Pruebas y clasificación

No sumar varias corridas de una misma prueba como cobertura adicional.
Los valores definitivos y pins se encuentran en `s8_manifest.json`.

| Evidencia | Tipo real de prueba | Resultado |
|---|---|---|
| final_regression/s8_adversarial | Unit/contract/integration in-process; modelo y efectos sintéticos en injection | 50 PASS |
| final_regression/security_regression | 554 unit/contract/integration S1–S7; incluye disco JSONL real en fixtures, fallos y recuperación | 554 PASS |
| final_regression/core_regression | Regresión Core/mock/integration; no es E2E local implícito | 694 PASS, diez subtests PASS, un smoke Ollama opt-in skip, tres GPU deselected |
| final_regression/desktop_* | Node host/proyección/client con doubles; tsc y build reales | 28 PASS; tsc/Vite PASS |
| final_native/selected | Los mismos 50 S8 más ocho tests Git existentes | 58 PASS; ocho adicionales, no otros 58 únicos |
| final_native/s3_windows | Windows/NTFS y broker productivo; junction/alias/TOCTOU reales | 23 PASS; dos fixtures symlink FAIL por WinError 1314 antes del broker |
| final_native/s4_process | Launcher/lifecycle/stdin/output/procesos reales | 29 PASS |
| final_native/s5_network | HTTP/TLS/DNS/redirect/IPv4/IPv6 fixtures nativas; admisión/resolver fixture documentados | 28 PASS; no representa salida pública arbitraria ni firewall |
| final_native/s6_secrets | Root/child y environment reales; valores fixture, selección/approval de test | 4 PASS |
| final_native/s8_host | Shell destructivo real sobre hojas propias; actor aprobado/denegado de test y frontera shell/S3 | 3 PASS; no intervención humana UI nativa en estos tres |
| final_native/core_native | Shell/quoting/cwd/Unicode/exit/fallback Windows reales | 4 PASS |
| jsonl_canonical_final | Proceso JSONL/Application/Policy/Approval reales; inferencia scripted, proof host de test | 1 PASS: spoof rechazado, denegación exacta consumida |
| e2e_control_final/desktop_* | Electron/main/preload/React/backend reales; lifecycle con inferencia/embeddings scripted y respuesta Ollama real separada | 2 Desktop PASS; prueba JSONL antigua falló y fue reparada/repetida por separado |
| local_final_candidate/ollama_cli | CLI normal, Ollama 9B instalado y lectura/audit productivos | PASS |
| local_backend_diagnosed | Ollama 7B real, un Turn read/write/read, igualdad literal obligatoria | FAIL: placeholder, no copia literal |
| final_e2e/selected | Cinco casos definitivos: backend multi-tool, proof JSONL, CLI/Ollama, Desktop scripted y Desktop/Ollama | 4 PASS, 1 FAIL en 140,64 s; copy literal recibió `read(result.txt)` en lugar del marker |

La corrida conjunta definitiva de cinco casos está en `final_e2e`; su XML y
observaciones, no la evidencia candidata, gobiernan el criterio local actual.
CLI final utiliza qwen2.5:7b; Desktop real también utiliza ese modelo y PATH
real sin Git. La falta de Git no se simula en este caso Desktop. El backend
multi-tool usa el PATH normal con Git disponible y los probes corregidos.

### Fallos actuales: no se redujo el gate

1. **Symlink archivo y directorio:** WinError 1314 al crear las dos fixtures
   nuevas. No fueron creadas y por eso no ejecutaron el broker en esta corrida.
   Junction y los otros 23 casos pasan. El PASS manual previo de S3
   (`s3_evidence/after_symlink_permission`, 25 PASS) permanece intacto, pero no
   sustituye los dos casos requeridos de la nueva corrida S8.
2. **E2E multi-tool con Ollama:** el modelo 7B devuelve read/write/read en una
   única respuesta y escribe un placeholder antes de conocer el resultado de
   read. El transcript fixture muestra que read devolvió el marker correcto;
   write recibió el texto inventado del modelo y lo escribió; el Turn puede
   completar, pero la igualdad final falla. Esto no es un error denegado
   simulado como éxito: hay efectos fixture observados y una comprobación
   explícita del contenido. Con 9B hubo progreso real seguido de un request
   shell `ls -la` que quedó pendiente de approval y alcanzó el deadline; no se
   ejecutó ni aprobó automáticamente. No se presentó ninguno como PASS.

No se reemplazó el modelo real por uno scripted para cerrar multi-tool, no se
eliminó la comparación literal, no se cambió el lifecycle ni se alteraron GPU,
hardware, modelos o tuning del usuario. Nuevas corridas usan fixtures
independientes: no son retry automático de una operación incierta.

Errores iniciales de fixture (configuración de eventos, selector del modelo
scripted, ubicación `services.interactions.approvals` y command canónico con
`expectedRevision`) fueron reparados dentro de S8; sus fallos/raw logs no se
borraron. El intento interrumpido conserva `UNKNOWN_INTERRUPTED`, sin inventar
rollback/outcome ni detener Ollama. El watchdog del runner es 1.200 s para
permitir finalizar pruebas hijas con deadlines propios; no cambió límites
productivos ni el deadline E2E de 360 s.

## Criterios cumplidos y pendientes

Cumplidos: cobertura ejecutable de 28 invariantes; contratos/autoridad/grants/
attenuation/approval; denial tipado; launcher sin elevación/secretos/canales
deliberados; outcome_unknown sin retry; terminal único; web_fetch mediado;
audit/gaps; regressión Core unit/integration; CLI/Desktop sobre Application;
Desktop/Ollama y Git ausente real; RAG opcional con fixture de failure no fatal;
límites y claims honestos publicados. Ninguno implica aislamiento OS o
resistencia universal del modelo a injection.

Pendientes: certificación nativa completa de la familia S3, en particular los
dos symlinks; cierre del E2E real multi-tool/copia literal. SEC12-INV-008/010
quedan con evidencia host parcial; la matriz no los eleva a PASS por contar
pruebas unitarias. El review conservador mantiene además SEC12-INV-021/022/023
parciales porque sus mapeos incluyen la familia E2E fallida; no atribuye a esos
tres invariantes una violación específica de autoridad/terminal/dependencias
que el fallo de copia no demostró. Las otras 23 familias mapeadas pasan. El
criterio de producto local completo no queda cerrado.

Regresiones: no fallos en las 1.298 pruebas Python principales de regresión
(más ocho Git adicionales), diez subtests ni 28 Node; cuatro Core nativas PASS.
Sí queda un fallo explícito de compatibilidad/calidad local en el smoke
multi-tool equivalente al Core Phase14, además del impedimento de fixtures
WinError 1314. No se afirma «cero regresiones» del gate completo.

Deuda restante: resolver exclusivamente esos dos puntos de S8 y repetir sus
gates con evidencia nueva. Linux/macOS no se certifican aquí. No claims
preventivos de cuotas OS, firewall, confinamiento o bloqueo universal de
herencia en el árbol de procesos.

OPEN DECISIONS: ninguna decisión nueva de S8. SEC12-OD-01..05 conservan las
decisiones humanas previas; OD-06/07 siguen futuras, no resueltas aquí.
Siguiente paso lógico: cerrar S8 pendiente; sólo después evaluar READY.

## Reproducción del pendiente nativo

Desde este repositorio, en el contexto que el usuario autorice para crear
symlinks, sin cambiar la configuración global del sistema desde el agente:

```powershell
& 'C:\Users\joseh\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B tests/security_v12/run_s8.py --output docs/security_v12/s8_evidence/after_symlink_permission --host-real
```

El directorio debe ser nuevo. Esta corrida también repite la regresión y las
familias nativas; no salta a otra fase. Para E2E real independiente, conservar
el criterio actual y usar un directorio nuevo:

```powershell
& 'C:\Users\joseh\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B tests/security_v12/run_s8.py --output docs/security_v12/s8_evidence/local_recheck --tests tests/security_v12/test_s8_e2e.py --e2e --model qwen2.5:7b
```

No una declaración PASS por el exit code de una subcorrida aislada. Revisar
todas las familias, provenance, hashes y limitaciones antes de cerrar S8.
