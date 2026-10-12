# Auditoría CI prospectiva

| Selección oficial | Estado local actual | Casos pasados |
|---|---|---:|
| core | PASS | 3416 |
| security | PASS | 615 |
| memory | PASS | 791 |
| knowledge | PASS | 1015 |
| active-web | PASS | 672 |
| web-v12 | PASS | 329 |
| web-v12-windows | PASS | 363 |
| web-v12-windows-native | PASS | 6 |

Cada fila corresponde al último intento de esa selección y exige coincidencia con los selectors actuales, ejecución completa, colección no vacía y cero skips. No se suman reintentos ni se infiere un run remoto de Actions.

Desktop: **PASS**; tests, TypeScript y Vite tienen receipts independientes. El build termina antes del instalador/publicación.

## Ajustes causales de CI

- Core conserva el golden histórico; compara por separado el prompt host-owned del catálogo V1.2.
- La prueba JSONL espera la pareja asíncrona EventGap → SessionSnapshot en orden.
- K6 comprueba el catálogo V1.2 y conecta ScriptedHTTPPort al constructor privado de adquisición host-owned tras retirar la ruta legacy; no cambia Approval.
- El perfil privado de CI tiene rutas cortas, ownership y lifetime bounded; no usa el perfil humano ambiental.
- El selector C# se trasladó a la selección Windows con sus prerrequisitos; no se eliminó cobertura.
- Las 99 funciones B1/B2 antes omitidas quedaron clasificadas positivamente.

Estos cambios preparan regresión prospectiva. No cambian ni rescoring de evidencias certificadas históricas.
