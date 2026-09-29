# Nova Core — cierre de fase 9

Fecha: 2026-09-28. Alcance: **CapabilitySnapshot y ContextManager**, exclusivamente. Fuentes normativas: `NOVA_CORE_ARQUITECTURA_V1.md` (§16, §17, §29) y `AUDITORIA_ARQUITECTONICA_NOVA_CORE.md` (fase 9), ambas en el directorio padre. **OD-05 resuelta por aprobación explícita de A; OD-06 permanece abierta. No se inició fase 10.**

## 1. Estado inicial y caracterización

Se preservaron los cambios existentes de fases anteriores y se inspeccionaron sus tests antes de modificar producción. El baseline relevante pasó: **362 passed, 1 skipped, 10 subtests passed**. Se añadieron y ejecutaron primero dos tests de caracterización del resolver legacy y del adapter de inferencia: **2 passed**.

El fallo Windows quedó reproducido antes del cambio: la API nativa medía **16.619.384.832 bytes** de RAM total, mientras `context_sizing._system_ram_gb()` y `system_info.get_system_info()` devolvían cero. No se modificó el PATH del sistema; el Git de pruebas se habilitó únicamente en el entorno de los comandos de verificación.

## 2. Decisiones implementadas

1. El conteo preferido es el hook explícito del adapter `count_tokens(model, serialized_payload)`, cuando existe y devuelve un conteo válido. Los adapters incorporados no exponen actualmente tokenizer local: usan el fallback aprobado. Un tokenizer que falla provoca recálculo completo con fallback y margen de estimación.
2. Fallback: representación JSON UTF-8 a `ceil(bytes / 3)`, más 12 tokens por mensaje y 20 por llamada/resultado de tool. Se cuentan sistema, schemas, instrucciones, skills, argumentos y resultados; también se incluye el contenedor estructural. Los componentes se cuentan conservadoramente antes de materializar el prompt.
3. Salida por defecto: `clamp(ceil(ventana * .125), 1024, 4096)`. Margen fiable: `max(256, ceil(ventana * .05))`; estimado: `max(512, ceil(ventana * .10))`. Se limita `num_predict` en Ollama y `max_tokens` en Claude/llama-server a la reserva, respetando máximos menores informados.
4. Presets: 4K/8K/16K/32K/AUTO. AUTO usa el mayor permitido cuando todos los límites están verificados; bajo incertidumbre relevante y modelo conocido, máximo 8K; modelo desconocido, 4K no verificado. Un manual que excede un límite conocido falla con código tipado; nunca se reduce silenciosamente.
5. Los caps de inyección son 15% retrieval, 30% tools totales, 15% por resultado y 40% combinados, calculados sobre `available`. No son reservas. El espacio libre queda para working context. La continuidad mínima y el mensaje actual tienen prioridad.
6. RAM/VRAM detectada no se convierte automáticamente en límite KV/contexto. El límite de recursos permanece UNKNOWN hasta disponer de configuración/evidencia explícita del host. No se calibraron ni se fijaron nuevas cuotas operativas.
7. Transcript y working context quedan separados en sesión, CLI y server. Las representaciones recortadas no sustituyen el dato bruto persistido. Los grupos antiguos se eliminan completos; IDs explícitos incompletos o inconsistentes fallan de forma tipada. El guard de seguridad de instrucciones de proyecto se conserva al recortar su cuerpo.
8. Se conserva `bash`, los schemas públicos, las confirmaciones, el rechazo OD-04 durante Turn activo y el enfoque local Ollama 7B–9B. No se incorporan multi-chat, memoria, sandbox fuerte ni capacidades futuras.

## 3. Arquitectura final de esta fase

```text
Sesión / bridge CLI / bridge server / subagente
    ↓
BoundModelRuntime (snapshot inmutable de ProviderManager)
    ↓
InferenceContext — Application
    ├── ContextManager / ContextSelection / ContextBudget — Core sin IO
    ├── RuntimeCapabilitySnapshot — contrato Core
    │      ↑
    │   probes Windows/Linux/macOS + NVIDIA + modelo/shell/Git — Infrastructure
    └── reportes de presupuesto y uso observado
    ↓
adapter de provider → inferencia
```

La frontera se aplica antes de cada inferencia, incluida la ruta no streaming. Un hijo recibe su snapshot y policy pero no el callback ni la identidad de entrada del padre. Los errores de presupuesto preceden a la petición al provider. Los reportes contienen contadores, procedencia e incertidumbre, no prompts ni credenciales; Application los correlaciona con el Turn/Generation, y los bridges legacy los registran. `/context` muestra el presupuesto común después de una inferencia; el formato anterior sigue disponible para contextos legacy sin reporte.

Hay dos cambios puntuales en `agent.py`: delegar truncación a ContextManager cuando la inferencia está gestionada, y evitar truncación legacy que rompería grupos al fallar un resumen gestionado. El modo summarize sigue disponible. No se alteraron el flujo de iteraciones, la ejecución de tools ni las otras guardas/retries; `harness.py` no se modificó en esta fase. Se comprobó mediante AST que Core no importa Application, Infrastructure, CLI ni server.

El resolver numérico histórico se conserva como adapter legacy caracterizado; **CLI/server de producto ya no lo usan para seleccionar contexto**. Sus antiguas reglas no constituyen la policy de Nova V1.

## 4. Archivos modificados en fase 9

Esta lista identifica sólo esta fase; el árbol contenía cambios anteriores que no se revirtieron.

| Archivo | Cambio |
|---|---|
| `local_cli/core/context.py` — nuevo | Contratos, estimador/tokenizer, presets, presupuestos, caps y materialización determinista. |
| `local_cli/core/contracts.py` | Snapshot añade límite de provider/recursos y revisión técnica de provider, manteniendo UNKNOWN explícito. |
| `local_cli/core/models.py` | Observaciones inmutables de contexto del provider, salida, cuantización y digest real del modelo. |
| `local_cli/infrastructure/__init__.py` — nuevo | Paquete lógico de adapters. |
| `local_cli/infrastructure/capabilities.py` — nuevo | GlobalMemoryStatusEx, /proc, sysctl, NVIDIA y composición de snapshot con shell/Git separados. |
| `local_cli/application/context.py` — nuevo | Frontera común de inferencia, policy de configuración, reportes y WorkingMessages. |
| `local_cli/application/providers.py` | Aplicación del contexto/salida a adapters, conservación de uso real y clones independientes. |
| `local_cli/application/session.py` | Capability snapshot actualizable, contexto de ejecución, reportes correlacionados y snapshot de observabilidad. |
| `local_cli/application/legacy_runtime.py` | Propagación del código tipado de ContextError al outcome del Turn. |
| `local_cli/application/legacy_interactions.py` | Acepta el snapshot común para ExecutionContext de tools. |
| `local_cli/agent.py` | Dos guardas puntuales para que truncación/resumen fallback gestionados respeten continuidad. |
| `local_cli/cli.py` | Consume la frontera común, separa retrieval legacy para budgeting, preserva transcript y renderiza observaciones. |
| `local_cli/server.py` | Misma frontera, snapshot para tools, transcript intacto, errores tipados y consulta de presupuesto. |
| `local_cli/config.py` | Presets y configuración de reservas/margen/límite de recursos con precedencia existente. |
| `local_cli/context_sizing.py` | Proyección de la sonda común; fallo RAM devuelve None y no cero. Resolver legacy preservado. |
| `local_cli/system_info.py` | Misma fuente de hardware; ausencia de evidencia no recomienda modelos como compatibles. |
| `local_cli/session_log.py` | Persiste presupuestos y conteos observados separados. |
| `local_cli/providers/llama_server_provider.py` | Conserva usage no streaming y frames usage posteriores al finish; terminal streaming único. |
| `desktop/src/components/ModelPicker.tsx` | Cambio mínimo: RAM puede ser null y se muestra `RAM unknown`. |
| `tests/test_nova_core_phase9_characterization.py` — nuevo | Compatibilidad previa del adapter y aislamiento del resolver legacy. |
| `tests/test_nova_core_phase9_context.py` — nuevo | Conteo, reservas, presets, incertidumbre, prioridades, caps y continuidad. |
| `tests/test_nova_core_phase9_capabilities.py` — nuevo | Probes por plataforma, fallo seguro y Windows nativo. |
| `tests/test_nova_core_phase9_integration.py` — nuevo | Providers, sesión, hijos, CLI/server, logs, RAG legacy y transcript. |
| `../NOVA_CORE_ARQUITECTURA_V1.md` | §16 precisión de evidencia/revisión; §17 policy aprobada; §29 OD-05 resuelta. |
| `docs/nova_core_od_05_contexto_v1.md` — nuevo | ADR de la decisión explícitamente aprobada. |
| `docs/nova_core_fase_9_resultados.md` — nuevo | Este cierre y evidencia. |

No se modificó la auditoría aprobada ni se movieron físicamente módulos anteriores.

## 5. Configuración

Se conserva la precedencia CLI > environment > config file > defaults. Ejemplo de configuración opcional, no una afirmación de que ese hardware soporte 16K:

```ini
num_ctx=auto
context_output_reserve=1200
context_safety_margin=820
context_resource_limit=16384
```

`context_resource_limit` es un límite explícito del host; no se rellena usando VRAM nominal. Defaults de las tres opciones nuevas: ausencia de override. Variables: `LOCAL_CLI_CONTEXT_OUTPUT_RESERVE`, `LOCAL_CLI_CONTEXT_SAFETY_MARGIN`, `LOCAL_CLI_CONTEXT_RESOURCE_LIMIT`. `LOCAL_CLI_NUM_CTX` continúa soportada; el archivo admite 4K/8K/16K/32K/AUTO y el flag numérico existente admite sus tamaños. Se rechazan límites no positivos y presets incompatibles, sin ampliar permisos.

## 6. Tests y resultados finales

| Verificación | Resultado |
|---|---|
| Baseline antes de producción | 362 passed, 1 skipped, 10 subtests passed. |
| Caracterización añadida antes de producción | 2 passed. |
| Cuatro archivos específicos de fase 9, versión final | **82 passed**, 0.48 s. |
| Regresión dirigida de runtime/proveedores/tools/subagentes, corte intermedio | 597 passed. Posteriormente cubierta por la suite final. |
| Suite completa final con Git disponible sólo en PATH del comando | **2569 passed, 8 skipped, 53 subtests passed**, 96.85 s. |
| CLI `--help`, compileall y dependencias inward AST | Correctos. |
| `git diff --check` | Correcto. |
| Desktop: TypeScript `--noEmit` y Vite build | Correctos, incluidos main y preload. |
| Empaquetado completo `npm run build` / electron-builder | **No completado**: el fallo previo de privilegios Windows al extraer symlinks de winCodeSign se reprodujo. TSC/Vite habían pasado. No se elevaron permisos ni se cambió configuración de packaging. |

Cobertura específica: modelos 4K/8K/32K y límites de provider/recursos; rechazo manual antes de IO; AUTO desconocido; UTF-8, emoji, schemas y overhead; tokenizer fiable/fallido, incluso fallo tardío; caps individuales/totales/combinados; skills/instrucciones/retrieval grandes; mensajes actuales y IDs; raw results intactos; salida acotada y usage; providers consistentes; clones; snapshot al cambiar modelo; errores y terminales; Windows nativo y mocks de cada plataforma.

## 7. Smoke real y límites de evidencia

- **Windows RAM real:** 16.619.384.832 bytes totales; ambos consumidores legacy dejaron de devolver cero por fallo. RAM disponible también se midió con la API.
- **GPU real:** NVIDIA GeForce RTX 4060; NVIDIA reportó 8.585.740.288 bytes de VRAM total. La medición no se convirtió en cap KV/contexto y el límite de recursos siguió UNKNOWN.
- **Sesión real con Ollama `qwen2.5:7b`:** nueve tools base disponibles y confirmación conservada; ejecutó `read` sobre un archivo temporal con acento y emoji, terminó correctamente en dos generaciones y conservó Unicode. Ventana AUTO 8192, reserva 1024, margen 820, selección no verificada por límite de recursos desconocido. Conteos de prompt estimado/real: **4362/2853** y **4511/2905**. Esto es observabilidad, no calibración de la policy.
- **Server legacy real:** `_handle_chat` sobre Ollama y ReadTool terminó sin error, emitió tool call/result, stream y done, y `/context` devolvió presupuesto común 8192. El transporte/reader sigue además cubierto por regresión; este smoke invocó el handler real, no un nuevo proceso Electron.
- **CLI REPL real:** entrada/read/respuesta, `/context` y `/exit`; reporte `2254 / 8192`, estimado, reserva 1024 y margen 820. Los logs conservaron conteo presupuestado y uso real. Entrada automatizada en un workspace temporal, sin conversación real del usuario ni modificaciones al proyecto.
- **Shell Windows real:** backend nativo seleccionado por el host ejecutó `Write-Output 'NOVA_PHASE9_SHELL_OK'` mediante la tool pública compatible `bash`.
- **Linux/macOS:** probes cubiertos con mocks y errores; no hubo ejecución nativa en esos SO en esta máquina. NVIDIA es opcional; AMD/Intel y VRAM no medible permanecen UNKNOWN.
- **Claude/llama-server:** contratos y mocks; no se usaron servicios reales. El hook de tokenizer fiable se comprobó con un adapter de test, no se afirma que los adapters incorporados tengan tokenizer local.
- **Desktop:** compilación comprobada; no se abrió la GUI ni se hizo E2E Electron en esta fase.

## 8. Regresiones encontradas y corregidas

La integración reveló referencias/imports faltantes en bridges y un slot faltante para la proyección de presupuesto CLI; se corrigieron y se añadió un test que recorre el REPL y su callback real. El smoke CLI confirmó después la corrección. La primera prueba de transcript también corrigió una expectativa de longitud del fixture, no el contrato del producto.

La revisión encontró tres problemas de comportamiento: el logger ignoraba las métricas nuevas; el fallback legacy podía retirar tool calls manteniendo resultados; y llama-server perdía usage, particularmente frames posteriores al finish. Se corrigieron dentro de esta fase con tests específicos. Los reportes de hardware ya no confunden un fallo con RAM cero ni RAM de sistema con VRAM. No quedan regresiones conocidas de fase 9 en los gates ejecutados.

El error de packaging winCodeSign es una limitación previa del entorno, ya registrada en fase 8, y sigue pendiente. No se intentó corregirlo mediante elevación o cambios adyacentes.

## 9. Criterios de salida y deuda

| Criterio de salida de fase 9 | Estado |
|---|---|
| OD-05 explícitamente aprobada, documentada y testeada | Cumplido. |
| Snapshot común con procedencia y UNKNOWN | Cumplido; límites operativos de OD-06 siguen UNKNOWN. |
| Windows RAM corregida, real + mocks de fallo | Cumplido. |
| Presets/hard caps/reservas por presupuesto | Cumplido. |
| Skills/RAG/tools grandes no desplazan mensaje actual ni rompen IDs | Cumplido por contratos; prompts imposibles fallan explícitamente. |
| Working compaction no borra transcript en sesión/CLI/server | Cumplido. |
| Provider/model snapshots y tools/approvals compatibles | Cumplido por regresión; bash y schemas preservados. |
| Suite final y smokes relevantes | Cumplido en Windows y Ollama local. |
| Pruebas nativas Linux/macOS y servicios Claude/llama-server reales | No ejecutadas en este entorno; no se atribuye evidencia nativa a mocks. |
| Empaquetado distribuible Electron | No cumplido; deuda previa, fuera del gate funcional de fase 9. |

Deuda deliberada: calibración posterior VRAM/KV; sondas adicionales de GPU; retención/formatos de persistencia y límites operativos según decisiones abiertas; fase 10 (puertos de persistencia/RAGService); migración completa server/CLI/Desktop en sus fases; matriz nativa de plataformas y E2E Electron. RAG sigue usando su motor legacy en CLI: se clasificó su inyección para aplicar presupuesto, no se implementó RAGService ni un rediseño interno.

**La fase 9 funcional está completada. NOVA CORE V1 STABLE no se declara:** faltan gates de fases posteriores. OD-06 no se cerró, no se cambiaron stdout máximo, timeouts, concurrencia, cuotas físicas ni gracia de cancelación y no se avanzó a fase 10.
