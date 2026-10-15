# Ampliación opcional de contexto 64K — cierre

Estado: **PASS**. Fecha: 2026-10-06. Alcance: catálogo manual de contexto,
configuración y caracterización M0; **M1 no iniciado**. No MEMORY productiva,
extracción, embeddings nuevos, consolidación ni recall. No commit ni push.

## Baseline e inventario previo

- Branch `main`, HEAD `468d213ede2fa52f6b2588ebaa1191b83669ccb8`, sin cambiar HEAD.
- Tags relevantes: `nova-core-v1-stable`, `nova-security-v1.2-ready`.
- Working tree inicial: sin modificaciones tracked; preexistían como untracked
  las arquitecturas/auditoría MEMORY y `docs/memory_v1/`, `tests/memory_v1/`.
  Se conservaron; sólo se ampliaron los archivos M0/arquitectura necesarios.
- Nova `0.12.6`, Python `3.14.6`, Windows 11 build 26200 / NTFS,
  Node `v24.16.0`, TypeScript existente del checkout.
- Baseline nativo privado: **3359 passed, 11 skipped, 53 subtests passed**,
  227.51 s. Inventario completado antes de editar; detalle en `inventory.json`.

| Superficie | Suposición encontrada / tratamiento |
|---|---|
| Core ContextSelection | Catálogo, aliases y error enumeraban hasta 32K; AUTO compartía catálogo. Se separa catálogo AUTO inalterado y manual con 64K. |
| ContextManager | Ya calcula sobre tokens numéricos; sin branches por preset. No cambia algoritmo, caps, reservas ni prioridad. |
| Config | Aliases hasta `32k`; números ya se parseaban. Se reutiliza el mapping Core con `64k`. |
| CLI / composition | Flag numérico, `/context` y configuración ya numéricos. Sólo cambia ayuda del flag y se prueba su recorrido. |
| Application API | Selección, frontera común, reportes y lifecycle numéricos. Tests de aceptación, rechazo y cambio a modelo menor; sin cambios de producto. |
| Desktop / server | Backend compartido y DTOs numéricos, sin selector de presets en renderer. Se prueban snapshot, handler de contexto, cliente y error tipado. No nueva UI. |
| Providers / capabilities | Límites positivos observados y UNKNOWN explícito, sin clamp 32K. Se prueba metadata sintética, cada límite y opciones de los tres adapters. |
| Snapshots / DTOs | Campos numéricos/records existentes; ningún nuevo campo o schema/version. |
| context_sizing legacy | Techo/tier 32K es AUTO histórico, no límite manual. Intacto; explicit 65536 y AUTO máximo 32768 probados. |
| Tests Core | 64K figuraba como preset inválido. Se sustituye por 128K, manteniendo rechazo de bool/negativos; config agrega 64K. |
| Harness M0 | Matriz de cuatro ventanas y casos de ceilings. Se agrega quinta ventana y matriz complementaria sintética. |
| Normas / ADR | Referencias a presets hasta 32K. Cambios de referencias necesarios y addendum, sin reabrir decisiones/fases. |
| Históricos / otros números | Auditorías, cierres M0/Core/Security, catálogo nativo de modelos y buffers no representan el techo configurable vigente. Intactos. README no contiene techo/preset obsoleto. |

## Contrato final

`AUTO / 4K / 8K / 16K / 32K / 64K`, con `64K = 65536`.

- 64K es **manual avanzado opcional**, no recomendación automática. Config
  admite `64K`, `64k`, `65536`; CLI conserva `--num-ctx 65536` y `--num-ctx 0`
  para AUTO. La ayuda describe tokens numéricos; no se introduce alias string
  en el flag históricamente entero.
- Con límites conocidos suficientes, devuelve exactamente 65536. Cualquier
  límite conocido de modelo/provider/recursos menor devuelve el error tipado
  `CONTEXT_LIMIT_EXCEEDED`, antes de inferencia; no clamp ni fallback a 32K.
- La semántica vigente ante incertidumbre se conserva: selección manual
  `manual_unverified` / `selection_verified=false`, nunca soporte verificado
  inventado. Sólo los tres límites conocidos permiten `manual_verified`.
- AUTO conserva 4K/8K/16K/32K, techo 32768 con los tres límites conocidos,
  máximo 8192 bajo incertidumbre relevante con modelo conocido y 4096 con
  modelo desconocido. Incluso con capacidad 64K/128K/256K no selecciona 64K.
- El presupuesto opera sobre `N`. No 128K; se prueba su rechazo.
- SECURITY sigue `HOST_UNISOLATED`, sin aislamiento de procesos. No se cambian
  policies, grants, approvals, brokers ni parámetros operacionales SECURITY.

## Resultados por ventana

Valores por defecto con el estimador Core, no tokens medidos por un LLM real.
El ceiling MEMORY es sólo el oracle M0 de §19, **no enforcement MEMORY**.

| Preset | N | Output reserve | Safety margin estimado | Ceiling MEMORY teórico | Escenarios |
|---|---:|---:|---:|---:|---|
| 4K | 4096 | 1024 | 512 | 327 | 9/9 PASS |
| 8K | 8192 | 1024 | 820 | 655 | 9/9 PASS |
| 16K | 16384 | 2048 | 1639 | 1024 | 9/9 PASS |
| 32K | 32768 | 4096 | 3277 | 1024 | 9/9 PASS |
| 64K | 65536 | 4096 | 6554 | 1024 | 9/9 PASS |

45 escenarios: usuario pequeño/mediano/grande, historial grande, retrieval,
ToolResults, MEMORY sintética, ausencia de memoria relevante y espacio opcional
cero. Se usa exclusivamente un **proxy test-only** bajo la categoría retrieval
Core existente, acotado previamente por el oracle M0; no se implementa categoría
`memory`, MemoryCapsule ni política de selección MEMORY productiva.

- Usuario actual exacto en todas las combinaciones; sistema y continuidad de
  ToolResults conservados. Entrada obligatoria imposible produce
  `CONTEXT_BUDGET_EXCEEDED`, sin truncamiento silencioso.
- Sin memoria relevante y sin espacio opcional: **0 tokens** de proxy en cada
  ventana. Proxy relevante pequeño: **99 tokens** en cada ventana; no rellena
  el ceiling y no aumenta cantidad de elementos con 64K.
- En 64K, caso sin espacio opcional: prompt estimado 54886 + salida 4096 + margen
  6554 = **65536**. Todos los prompts respetan N y los caps compartidos Core.
- Budgeting y prompt repetidos son idénticos; canonical input no se modifica.
- Sin embeddings: toda la matriz funciona, sin descargar modelos ni inferencia.
  El baseline lexical y semantic/RAG existente se vuelve a caracterizar sin
  confundir RAG documental con MEMORY personal.
- Historial de 10000 mensajes: con retrieval/tools grandes, Core retiene 387
  mensajes en 64K; en el escenario complementario sin tools retiene 548 de
  10004 y el proxy MEMORY consume cero. No se inyecta el transcript completo.
  **No claim de carga diferida/RAM acotada:** Core aún recorre/copia el historial
  fuente completo; esta ampliación no optimiza ese comportamiento.
- En la caracterización de crecimiento (3 muestras), 64K/10000:
  mediana 90.981 ms, peak trazado 22582733 bytes. Son observaciones sintéticas
  descriptivas, no un SLA ni benchmark de latencia de inferencia.

## Archivos creados/modificados

Producto (sólo tres):

- `local_cli/core/context.py`: manual 64K, AUTO separado, mapping compartido.
- `local_cli/config.py`: aliases desde el mapping Core.
- `local_cli/cli.py`: ayuda numérica del flag.

Tests/harness:

- `tests/test_context_64k.py` (nuevo): 41 contratos unit/mock e integración.
- `tests/test_nova_core_phase9_context.py`: expectativa inválida pasa a 128K.
- `tests/test_nova_core_phase9_integration.py`: alias config 64K.
- `desktop/tests/application_client.test.cjs`: dos contratos de proyección/error.
- `tests/memory_v1/context_baseline.py`: quinta ventana.
- `tests/memory_v1/test_m0_evaluation.py`: ceiling 64K, sin incrementar hard cap.
- `tests/memory_v1/advanced_context.py` y `test_advanced_context.py` (nuevos):
  matriz/oracle/proxy test-only y equivalencia de compactación 32K/64K.
- `tests/memory_v1/run_m0.py`: exporta la caracterización complementaria.
- `tests/memory_v1/run_regression.py`: modo dirigido `context64`, mismo entorno
  privado; no cambia selecciones/exclusiones de HEAD/M0 existentes.

Documentación:

- `docs/architecture/NOVA_CORE_ARQUITECTURA_V1.md`: referencias del preset y
  aclaración de AUTO inalterado, sin cambiar otras decisiones Core.
- `docs/architecture/NOVA_MEMORY_ARQUITECTURA_V1.md`: targets locales/avanzados,
  principio N, cap idéntico y 128K+ fuera del alcance requerido; sólo referencias
  necesarias a la ampliación en fases/gates existentes.
- `docs/nova_core_od_05_contexto_v1.md`: addendum; decisión histórica conservada.
- `docs/context64/`: este cierre, inventario, manifest y evidencia separada.

Los 19 archivos de `docs/memory_v1/` preexistentes siguen idénticos por SHA-256,
igual que corpus, auditoría MEMORY y arquitectura SECURITY. No se actualizan los
hashes ni se reinterpreta el cierre histórico M0 a partir de la nueva corrida.

## Regresión y fallos conservados

| Ejecución | Resultado |
|---|---|
| HEAD antes, nativo privado | 3359 passed / 11 skipped / 53 subtests, 227.51 s |
| Context64 dirigido final | 396 passed / 3 skipped, 22.56 s |
| HEAD después, nativo privado | 3452 passed / 11 skipped / 53 subtests, 213.20 s |
| Node Desktop con transformación TS | 30 passed / 0 skipped / 0 failed |
| TypeScript `--noEmit` | exit 0, sin diagnostics ni artefactos de build |
| M0 metrics | 26 casos, 34 fuentes, 20 mediciones de crecimiento, 45 escenarios |
| `git diff --check` | PASS |

Los 93 casos pytest adicionales corresponden a 41 contratos 64K, 46 tests de
matriz/compactación, cinco parámetros M0 y un alias config. Los 11 skips finales
son **exactamente los mismos** del baseline (`evidence/unchanged_skips.json`).
No nuevo skip/xfail, reducción de gates ni modificación del workflow.

Fallos iniciales, no ocultados:

1. Baseline directo restringido: 2 failed / 244 passed / 60 setup errors por
   PermissionError/OSError creando fixtures en TEMP restringido. Se repite
   con el harness de perfil privado y permisos nativos antes de editar; PASS.
   No existe raw log completo de aquella invocación; la salida truncada del
   tool es la evidencia observada, no se fabrica un log.
2. `focused_1`: collection error por parámetro pytest reservado `request` en
   el fixture nuevo. Renombrado a `requested`, sin tocar producto.
3. `focused_2`: 1 failed / 395 passed / 3 skipped; fixture nuevo construyó
   coordinator sin EventBufferConfig, requerido para adapter con eventos.
   Se configura el fixture normal; `focused_final` pasa sin relajar assertions.
4. Node sin transformación TS: 28 passed / 2 failed en los dos tests SECURITY
   preexistentes con import dinámico y parameter properties. Node 24 strip-only
   no soporta esa sintaxis. Se usa `--experimental-transform-types`; 30/30.
   No cambios de SECURITY, TS productivo, dependencias o package.json. Avisos
   experimentales/module-type de Node permanecen visibles.

Evidencia completa de las corridas privadas y métricas en `evidence/`; manifiesto
con hashes y alcance en `manifest.json`. XML originales permanecen en los
directorios privados de ejecución, fuera del repositorio.

## Reproducción

Desde el root, usando directorios **nuevos** para no sobrescribir evidencia:

```powershell
python -B -m tests.memory_v1.run_regression --mode context64 --output <nuevo-directorio-dirigido>
python -B -m tests.memory_v1.run_regression --mode head --output <nuevo-directorio-head>
python -B -m tests.memory_v1.run_regression --mode metrics --output <nuevo-directorio-metricas>
```

Desde `desktop/`, sin instalar ni empaquetar:

```powershell
node --experimental-transform-types --test tests/*.test.cjs
node node_modules/typescript/bin/tsc --noEmit
```

## Alcance, incompatibilidades y UNKNOWN

No incompatibilidad observada de schemas públicos, lifecycle, provider switching,
CLI/Desktop sobre Application, ToolRuntime, Core o SECURITY. No nuevos permisos
ni claims de aislamiento. Se preservan las exclusiones históricas de CI.

Tests nuevos son unit/mock/contrato y una integración del backend Application
real con provider sintético, además de proyección Desktop/handler server reales.
La regresión HEAD incluye sus smokes nativos preexistentes. No se vuelve a
certificar host-real SECURITY/NTFS, Electron E2E o modelo Ollama a 64K: no fueron
necesarios para cambiar un preset numérico y no se presentan como ejecutados.
Linux/macOS nativos no ejecutados aquí; no se amplía soporte SECURITY POSIX.

Capacidad efectiva, KV/RAM/VRAM y latencia de un modelo local concreto a 64K:
**NO VERIFICADOS por esta tarea**. Cuando faltan límites, siguen UNKNOWN. La
calidad MEMORY sigue NOT_IMPLEMENTED; no se resuelven OPEN DECISIONS posteriores.
Siguiente fase lógica: M1, **sin iniciar ni implementar**.
