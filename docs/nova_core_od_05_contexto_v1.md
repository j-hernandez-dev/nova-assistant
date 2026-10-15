# ADR — OD-05: contexto conservador y configurable V1

Estado: **aprobada y resuelta**, 2026-09-28. Fuente: elección explícita del usuario de alternativa A. Norma canónica: `NOVA_CORE_ARQUITECTURA_V1.md`, §17 y §29, en el directorio padre.

## Decisión

- Tokenizer/conteo real del adapter cuando esté disponible y sea fiable. Fallback: `ceil(bytes UTF-8 serializados / 3)`, incluyendo todo el prompt y los schemas, más 12 tokens/mensaje y 20 tokens/tool call o resultado. Fallo del tokenizer activa fallback y el margen correspondiente.
- Reserva de salida por defecto: `clamp(ceil(ventana * 0.125), 1024, 4096)`; configurable. Se respeta un máximo de salida informado menor y se limita la salida solicitada a la reserva.
- Margen fiable: `max(256, ceil(ventana * .05))`; estimado: `max(512, ceil(ventana * .10))`. Configurable desde el host.
- Presets V1: 4096, 8192, 16384, 32768, AUTO. AUTO elige el mayor preset dentro del mínimo de los límites verificados. Ante límites relevantes no verificados y modelo conocido, máximo 8192; modelo desconocido, 4096 bajo capacidad no verificada. Siempre se respetan otros límites conocidos.
- Manual: rechazar explícitamente cualquier exceso conocido; nunca reducir silenciosamente. Una selección con incertidumbre debe identificarla como tal.
- Caps de inyección: retrieval 15% de available; resultados de tools totales 30%; individual 15%; ambos combinados 40%. Se redondean hacia abajo. No son reservas y el espacio libre queda para working context.
- El mensaje actual, sistema obligatorio y continuidad de tool calls tienen prioridad. Los grupos antiguos pueden retirarse completos; resultados pueden truncarse sin eliminar el dato bruto del transcript. No se inventan IDs ni respuestas de tools para hacer caber un prompt.
- El cálculo presupuestado y el uso real, cuando esté disponible, se conservan como observaciones separadas sin publicar el prompt ni secretos.
- Windows usa `GlobalMemoryStatusEx`; fallos dan UNKNOWN con procedencia y tipo de error, nunca RAM=0.

## Frontera y configuración

Core contiene contratos/cálculo de contexto sin IO. Application compone la frontera común de inferencia y sus reportes; Infrastructure mide recursos. Desktop, server, CLI y subagentes no eligen algoritmos propios.

Configuración: `num_ctx` mantiene AUTO/0 y presets numéricos; `context_output_reserve`, `context_safety_margin`, `context_resource_limit` permiten límites explícitos del host. Variables equivalentes: `LOCAL_CLI_NUM_CTX`, `LOCAL_CLI_CONTEXT_OUTPUT_RESERVE`, `LOCAL_CLI_CONTEXT_SAFETY_MARGIN`, `LOCAL_CLI_CONTEXT_RESOURCE_LIMIT`. Se conserva CLI > environment > archivo > defaults.

Un límite de recursos configurado es evidencia/configuración del host, no una medición de VRAM/KV. Sin tal límite verificado permanece UNKNOWN; la RAM/VRAM nominal no habilita automáticamente 16K/32K. La calibración posterior puede refinar la policy sin cambiar contratos.

## Alcance excluido

**OD-06 continúa abierta**: no se cambian límites físicos de stdout, timeouts, deadlines, concurrencia, cuotas de ejecución ni gracia de cancelación. Estos caps sólo limitan la inyección al prompt. Tampoco se implementa fase 10, RAGService, memoria conversacional, multi-chat ni sandbox fuerte.

## Verificación

Tests de caracterización del adapter legacy; unit de UTF-8/overheads, reservas, incertidumbre, hard caps y materialización; probes Windows/Linux/macOS y fallo GPU; contratos de provider/sesión/server/subagentes y conservación del transcript. La evidencia de ejecución y limitaciones de plataforma se documenta en `nova_core_fase_9_resultados.md`.

## Addendum aprobado — contexto manual 64K (2026-10-06)

La lista original anterior documenta la decisión histórica. El contrato vigente
añade `65536` / `64K` como preset manual avanzado opcional. AUTO conserva
exactamente su catálogo 4K/8K/16K/32K y los fallbacks 8K/4K; no selecciona 64K.
Todo límite conocido menor produce `CONTEXT_LIMIT_EXCEEDED` antes de inferencia,
sin clamp. Límites desconocidos conservan `manual_unverified`, nunca soporte
verificado inventado. Config reconoce `64K`; el flag CLI mantiene sintaxis
numérica `--num-ctx 65536`. Budgeting/reservas/caps siguen siendo aritmética sobre
`N`; no se amplía MEMORY, SECURITY ni el catálogo a 128K. La evidencia histórica
permanece intacta; la nueva ampliación se registra separadamente en
`context64/resultados.md`.
