# Bloque 3 — Búsqueda con navegador

Fecha: 2026-10-14. **Implementado en `nova-min/nova-assistant`.**

## Uso normal

El modelo dispone de `web_search(query, max_results?)` junto con navegación,
archivos, terminal y el fetch HTTP opcional. Una petición como «Busca una noticia
de hoy en México y resúmela con el enlace» no necesita comandos administrativos.
La búsqueda abre el buscador en el WebView2 incluido. No requiere SearXNG ni API key.

Bing es el buscador predeterminado. El humano puede elegir explícitamente:

```text
/search status
/search engine duckduckgo
/search engine google
/search engine bing
```

El comando figura en `/help`; los argumentos inválidos reciben un error en inglés.
Se guarda únicamente una elección explícita en `browser-search.json` del directorio
de estado de Nova. No se migraron ni modificaron preferencias personales.
`/fetch off` sigue desactivando sólo `web_fetch` HTTP; Browser continúa funcionando.

## Composición

```text
modelo → web_search → ToolRuntime → Policy → Grant exacto
       → servicio Browser compartido → WebView2/Playwright
       → títulos/URLs/extractos acotados
modelo → browser_navigate(URL elegida) → página realmente leída
modelo → respuesta con fuente
```

La operación de búsqueda revela la query al buscador y se clasifica como
`browser.DATA_DISCLOSURE`, con permiso `browser.navigate`. Policy puede denegarla.
La URL física la construye el host desde el buscador elegido y la query codificada;
el modelo no proporciona endpoint, selector, JavaScript, epoch ni Grant.
La query, destino, página y epoch quedan ligados a la operación exacta.
No se utiliza el broker HTTP/SearXNG por confundir el nombre histórico `web_search`.
Se mantiene la validación de clase de las herramientas Browser para impedir el
fallback a un ejecutor genérico con el mismo nombre.

La búsqueda usa el mismo worker y sesión que la navegación. No se añadieron router
léxico, fases semánticas de research, una segunda Policy, nuevos perfiles históricos
ni una allowlist de palabras. El modelo elige la secuencia de herramientas.
No hay importación automática a Memory/Knowledge. El estado de búsqueda está en
`Application.services.search`; el antiguo estado documental de proveedor pasivo
no se presenta como si fuese Browser.

Resultados: como máximo 5 por llamada, query de hasta 500 caracteres, título de 180,
extracto de 500 y URL completa de hasta 4096. Se descartan protocolos no web,
credenciales embebidas y duplicados. Cada resultado es `SEARCH_SNIPPET`,
`pageRead=false`; no prueba lectura del artículo. La proyección de contexto conserva
URLs completas, omitiendo filas enteras si hace falta. La fecha local del host está
disponible en el prompt compacto para formular queries con fechas relativas.

Los límites Browser existentes se conservan: 25 acciones y 10 navegaciones por turno.
Click/input ordinarios mantienen Approval; una búsqueda normal no simula múltiples
aprobaciones para teclear y enviar su query. No se modificaron los permisos de shell
ni el fetch HTTP. Browser conserva `HOST_UNISOLATED` / `networkIsolation=NOT_PROVIDED`.

## Verificación

- **577 casos portátiles focales aprobados**, cero fallos/skips: Browser bloques 1/2,
  nuevas pruebas de búsqueda, CLI/help/configuración, AgentLoop/contexto,
  Policy/Approval/Grant, fetch/S5 y el proveedor pasivo documental existente.
- **28 casos de Browser/búsqueda aprobados** en la comprobación posterior de la
  validación de clase y paridad administrativa CLI/JSONL/Desktop backend. Se solapan
  con la regresión anterior y no se suman como casos distintos.
- **Job Windows explícito `browser-block3`: 1 caso nativo aprobado**, sin skips,
  con WebView2 real, páginas propias y sin depender de Internet/Ollama.
- Corpus nativo: resultados generados por JS, lectores de Bing/Google/DuckDuckGo,
  metadatos de resultados con contenedor oculto, selección/apertura, redirect con
  query/fragment, lectura real, búsqueda con fetch desactivado, cero resultados,
  CAPTCHA, HTTP 403, layout desconocido y cleanup.
- Inventario CI: **3856 funciones clasificadas; cero sin clasificar**. Los tests de
  Browser nativo son manuales Windows; los de modelo real no se ejecutan en cada push.
- Smokes públicos separados: **Bing y DuckDuckGo devolvieron resultados reales**.
  Google mostró CAPTCHA en el diagnóstico; no se promete acceso sin bloqueos.
- Modelo instalado **qwen3.5:9b, Q4_K_M**, digest
  `c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a`.
  Perfil productivo: contexto 8192, temperature 0.6, top_p 0.95, top_k 20,
  think=false; reserva de salida existente, sin ampliarla.
- Último smoke de modelo: **2/2 peticiones ES/EN** hicieron
  `web_search → browser_navigate → resumen con marcador del artículo y enlace`,
  con fetch desactivado, catálogo mixto y sin terminal. Usó Application/CLI reales
  y un buscador/página owned; no es un benchmark general del LLM.

### Intentos y limitaciones preservados

Los recibos de desarrollo se mantienen bajo `runs/`, incluidos fallos:

1. El lector inicial descartaba resultados Bing porque comprobaba rectángulos
   visibles. Bing había entregado sus contenedores en DOM; se corrigió la lectura
   fija de metadatos de discovery, sin afirmar que el artículo hubiera sido leído.
2. Una primera respuesta del modelo omitió el enlace aunque leyó el artículo.
   Las peticiones posteriores especifican «incluye el enlace»; no se considera
   esa respuesta un PASS de citations.
3. Un smoke combinado excedió las 10 navegaciones al probar varios buscadores en
   un único turno. El runtime lo denegó correctamente. Los smokes públicos
   independientes ahora utilizan turnos independientes; no se elevó el límite.
4. En otro intento el modelo abrió la fuente, reconoció que la noticia era
   sintética y se negó a resumirla como noticia actual. Ese intento permanece FAIL.
   El último smoke completó ambas peticiones con honestidad sobre el contenido.
   La selección/redacción del LLM continúa siendo variable; no se afirma 100% de
   calidad ni veracidad de las noticias de un buscador externo.
5. La lectura del estado documental asumía que toda herramienta `web_search`
   tenía un proveedor SearXNG. Se separó esa proyección para que Browser no cause
   un AttributeError al abrir CLI/JSONL. Las pruebas cubren ambos roots.

Los sitios pueden cambiar su DOM, exigir consentimiento/CAPTCHA o rechazar
automatización. Se devuelven errores acotados y entendibles, sin inventar resultados
ni saltar a otro buscador ocultamente. La intervención humana visible corresponde
al bloque posterior. La selección de Chrome/Edge también queda para su bloque.

## Archivos principales

- `local_cli/core/browser_search.py`: configuración y resultados bounded.
- `local_cli/browser_search_config.py`: preferencia explícita y persistencia.
- `local_cli/tools/browser_search_tool.py`, `browser_tools.py`: catálogo y schema.
- `local_cli/infrastructure/browser/search.py`, `pages.py`: búsqueda/lectura fija.
- `local_cli/application/browser_navigation.py`, `tool_runtime.py`, `policy.py`:
  camino Browser existente, binding y despacho autorizado.
- `local_cli/bootstrap_passive_web.py`, `application/knowledge_host.py`:
  separación del proveedor HTTP antiguo y ausencia de selección obligatoria.
- `local_cli/application/commands.py`, `session.py`, `cli.py`: configuración,
  snapshot compartido, `/search` y `/help`.
- `local_cli/core/browser.py`, `prompts.py`: contexto/procedencia e instrucciones compactas.
- Tests, smoke y clasificación en `ci/pytest_contracts.json` / `ci/run_contracts.py`.

## Recursos e historia

Los recibos finales confirman cierre del host, job vacío, perfil eliminado y
listener detenido. No se intentó volver a borrar el perfil preliminar retenido
del bloque 2 ni recursos personales/históricos.

No hubo cambios nativos ni rebuild del componente:

- host DLL SHA256 `add85e2da7908b21d03e3bba2808a65ff22377ff597b024816e9388d61ff71ca`;
- runtime EXE SHA256 `46b3c6ac9169416cc2ee76b23ee3d9db0eb8daefb914b1d9cc0f5d2387b033ac`.

No se editaron evidencias de los bloques anteriores ni del proyecto antiguo.
Sin staging, commit, push, tag o release.

**BLOQUE_3_BUSQUEDA_CON_NAVEGADOR = IMPLEMENTADO**
