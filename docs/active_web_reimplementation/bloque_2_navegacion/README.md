# Bloque 2 — Navegación productiva

Las herramientas Browser se instalan automáticamente en Windows cuando está
presente el paquete del Bloque 1 en `dist/browser/windows-x64/`. El motor sólo
arranca cuando el modelo solicita navegar. No se necesita un comando `/web`,
selección de carril, SearXNG ni una modificación de preferencias personales.

Catálogo: `browser_navigate`, `browser_observe`, `browser_click`, `browser_type`,
`browser_press_key`, `browser_back`, `browser_forward`, `browser_reload` y
`browser_close`. Archivos, terminal y fetch permanecen en el catálogo normal.

Navegar devuelve texto renderizado y referencias opacas a elementos. El modelo
usa esas referencias para actuar; no proporciona JavaScript, selectores, epochs
ni IDs internos. Una referencia retirada o cambiada requiere observar de nuevo.
La página actual vive en Application entre turnos y tiene su propio perfil.
Este bloque administra una página: enlaces `target=_blank` y `window.open`
HTTP(S) continúan en esa misma vista, conservando sus controles y su cierre.
La observación se pagina mediante `nextElementOffset` cuando no caben todos
los controles. La proyección de contexto conserva referencias y URLs completas.

Policy evalúa cada operación. Clic, escritura y teclas requieren Approval y Grant
exactos. `--yes` no satisface esa Approval. La etiqueta del elemento sólo informa
al humano; no demuestra que su efecto sea lectura. Un receipt de interacción
local no confirma una compra ni otro resultado remoto. La pérdida después del
dispatch produce UNKNOWN y bloquea nuevas mutaciones hasta una nueva petición
humana y una observación fresca. Browser mantiene `HOST_UNISOLATED` y no promete
aislamiento de red.

## Probar desde Nova

Desde esta copia de nova-min, con el Python de Nova compatible con el paquete:

```powershell
& $novaPython -m local_cli --provider ollama --model qwen3.5:9b --num-ctx 8192
```

En `You>` se puede pedir abrir una URL, leer su contenido renderizado y seguir
un enlace. El modelo puede solicitar aprobación para interactuar con la página.
Las solicitudes y errores de la interfaz están en inglés; la respuesta del
modelo conserva el idioma de la conversación.

## Verificación de desarrollo

```powershell
& $novaPython -m pytest -q tests/test_browser_product.py
& $novaPython scripts/smoke_browser_block2.py
& $novaPython scripts/smoke_browser_block2.py --real-model --model qwen3.5:9b
```

La última ejecución usa Ollama real y una página HTTP propia. El actor de
prueba aprueba únicamente las interacciones inocuas de su fixture; no convierte
un JSON del modelo en aprobación productiva. No descarga modelos ni escribe
configuración personal. El resultado se guarda en un temporal nuevo o, mediante
`--output`, en un archivo nuevo de este bloque. Los intentos no se sobrescriben.

La regresión Windows nativa es manual, con paquete real; no depende de Internet
público y no se omite silenciosamente si falta el motor. Las campañas con Ollama
son explícitas y quedan fuera de CI ordinario.

El host continúa oculto. Credenciales, transferencias, intervención humana y
selección de otros navegadores corresponden a los bloques posteriores. Los
resultados concretos y las limitaciones del modelo se registran en `resultados.md`.
