# Bloque 5 — Intervención humana y archivos

Implementado en `C:\Users\joseh\Downloads\nova-min\nova-assistant`.

**Resultado funcional: PASS.** Las ejecuciones finales cerraron sus procesos,
Jobs, perfiles y listeners propios. Hay residuos de intentos de desarrollo con
**CLEANUP_UNCONFIRMED**, conservados y detallados abajo. No se presenta esa
limpieza anterior como confirmada.

## Uso

```text
/browser takeover
/browser resume
/browser close
/browser file "C:\ruta\archivo.txt"
/browser sensitive
/browser downloads
/browser discard <downloadId>
```

Nova también puede proponer `browser_request_takeover`, `browser_upload` y
`browser_download` desde una petición natural. `/help` incluye los comandos.
Los mensajes de la CLI están en inglés; no se impone idioma a las respuestas
del modelo. No se cambió la UI de Desktop.

### Login/CAPTCHA

Se muestra la ventana de la sesión propia actual. El humano interactúa ahí y
termina con `/browser resume`. Durante la pausa no se ejecutan herramientas del
agente ni comienza otro turno. Al volver se comprueba continuidad, se incrementa
el epoch real, se invalidan refs anteriores y se obtiene una observación nueva.
La ventana permanece abierta. Cerrar su ventana no concede resume automático.

La pausa tiene un límite de 15 minutos; una pérdida de conexión/checkpoint deja
el control bloqueado hasta cerrar el navegador. Dos ciclos consecutivos pasaron
en WebView2 y Edge, sin suponer que los epochs sólo puedan ser 0/1.

### Upload

Un archivo del workspace puede proponerse por ruta. Fuera del workspace requiere
selección humana explícita con `/browser file`; el modelo recibe un ref opaco y
metadata, no authority genérica sobre el sistema de archivos. La selección dura
cinco minutos y se consume al iniciar la carga. **Seleccionar no aprueba.**

El input debe ser un file input observado y fresco. Policy exige Approval y un
Grant exacto. Se comprueban identidad NTFS, revisión, tamaño, digest, owner y
target antes del efecto y después de Approval. Los handles niegan escritura y
reemplazo durante la captura; se entrega al browser una copia inmutable en
memoria, no una ruta mutable. Máximo 32 MiB.

Adjuntar ya revela datos a la página. El recibo confirma adjunto local, con
`remoteOutcome=UNKNOWN`; no inventa éxito remoto de formulario/negocio. Archivo
modificado durante Approval, ref stale y nodo equivocado dieron cero disclosures
en el canario nativo.

### Download

Una URL exacta requiere Approval y permiso de un uso. El engine queda en deny
fuera de esa operación. Una descarga drive-by no produjo staging. WebView2 usa
su evento nativo DownloadStarting y Completion; Edge/Chrome usan eventos CDP del
browser propio. No hay cliente HTTP alternativo para las transferencias.

Sólo `engine COMPLETE + archivo owned + tamaño comprobado + SHA256` emite un
artefacto completo. Nombre remoto, incluso `../../remote-untrusted.exe`, no
determina el path: el archivo es `download_<uuid>/payload.bin` bajo
`<state_dir>/browser-files`. No se abre, ejecuta ni importa automáticamente.
Límites: 32 MiB y 30 segundos por descarga. WebView2 compara el URL del evento
exactamente; si el servidor entrega un attachment desde otro URL tras redirects,
puede requerirse el URL final exacto.

El archivo completo sobrevive al cierre del browser. `/browser downloads`
revalida tamaño/digest y distingue pérdida o cambio. Hay expiry de recibo a
14 días, con discard explícito; expiry no significa borrado físico silencioso.
Una interrupción produjo UNKNOWN/PARTIAL o timeout con resultado incierto, nunca
COMPLETE. Otra propuesta del mismo turno fue denegada sin otra invocación de
descarga. Esto prueba ausencia de reintento de Nova; no afirma controlar los
reintentos HTTP internos del engine.

## Sensibles

Instrumentación fija durante takeover registra valores conocidos en password,
autocomplete sensible y `data-nova-sensitive`. `/browser sensitive` permite
declarar otro valor mediante entrada oculta, fuera del chat y del command log.
La sensibilidad conocida se conserva a través de navegación y cierre. El
redactor compartido protege ToolResult, contexto del modelo, snapshots y audit.

El fixture introdujo un secreto sintético, intentó reflejarlo y navegó a otro
documento: las observaciones públicas posteriores estaban redactadas. Si el
checkpoint se pierde, no se publica primero una observación nueva. Eventos
tardíos pueden conservar sensibilidad, nunca reanudar ni conceder authority.

Alcance: valores declarados/conocidos, no DLP universal, detección de cualquier
transformación, protección del sitio receptor o borrado forense. Campos de texto
ordinarios no se convierten automáticamente en secretos. No se importó el
protocolo histórico de TerminalSnapshot.

## Arquitectura y permisos

La selección de herramientas sigue siendo del modelo. No se añadieron intent
classifiers, lanes ni fases de workflow. ToolRuntime continúa mediando Policy,
Approval y Grant; los permisos Browser siguen separados de HTTP fetch.

CLI y JSONL/Desktop backend consumen una sola Application y BrowserExecutionService.
BrowserControl administrativo exige actor humano del host, distinto del actor
de Approval; JSON no autenticado no puede hacer takeover/resume/file selection.
La UI Desktop aún no incorpora controles nuevos: esta entrega es CLI y contrato
backend compartido, sin simular una UI completa.

Browser sigue `HOST_UNISOLATED`, `networkIsolation=NOT_PROVIDED`.

## Verificación

| Ejecución | Resultado |
|---|---|
| Regresión focal Python, runtime, sesión, Policy, Approval, Grant, S3 y redacción | 386/386 PASS |
| Regresión causal posterior de cierre, selección, popup y Block 5 | 53/53 PASS; solapa con la anterior, no se suma como denominador nuevo |
| Nuevos contratos Block 5 | 13 casos parametrizados, 10 funciones portables |
| Job nativo Block 5, runner oficial y entorno privado | 1/1 PASS, WebView2 y Edge reales |
| Job nativo navegación/búsqueda Block 4 sobre el paquete nuevo | 1/1 PASS |
| Proyección Desktop/backend y Approval host | 29/29 PASS |
| Inventario CI | 3,877 funciones, 0 sin clasificar |
| Smoke modelo real | PASS; qwen3.5:9b, perfil productivo 8192/0.6/top_p 0.95/top_k 20/think=false |

El modelo hizo navigate → upload → dos propuestas no útiles rechazadas/abortadas
→ download → respuesta con el path real retenido. Hubo Approval de upload y
download. Una navegación al attachment sin permiso no creó staging; el download
posterior tuvo su permiso propio y recibo completo. Es un smoke de funcionamiento,
no un benchmark ni una afirmación de selección perfecta del modelo.

Chrome no está instalado: no se descargó ni se afirma prueba nativa positiva.
Comparte implementación con Edge; disponibilidad y ausencia se mantienen honestas.

El paquete en `dist/browser/windows-x64` se reconstruyó con host self-contained,
SDK 1.0.4258.31, runtime FixedVersion 155.0.4283.45 y Playwright 1.64.0. Se preservó
el paquete anterior en `windows-x64-block4`. Ver `package_identity.json`.

## Incidencias y limpieza

Se conservaron los intentos fallidos en `runs/`. Se corrigieron causalmente:

- Tipo Path/string en el snapshot de upload.
- ShowInTaskbar recreaba el HWND y disponía WebView2; ahora la visibilidad no
  recrea la ventana. Al reanudar se conserva visible para acciones normales.
- Un override CDP de downloads evitaba DownloadStarting de WebView2; se restauró
  el control nativo de su permiso exacto.
- Edge crea targets vacíos transitorios durante ciertos downloads: ahora sólo
  un documento HTTP(S) real reemplaza la página actual. El smoke de popups previos
  sigue pasando.
- Tras una pérdida forzada, el Job puede quedar vacío antes de que el handle del
  proceso esté señalado. Se espera acotadamente esa identidad real y se permite
  una limpieza breve de locks transitorios del perfil actual.

El intento 7 usó `page.close()` directamente sobre el target embebido y bloqueó
el fixture. Sus procesos Python/Node fueron detenidos y el Job terminó sus hijos;
el recorder no alcanzó a producir su recibo original. Se documentó ese fallo,
sin fabricar un resultado nativo. Los intentos posteriores usan pérdida real del
Job propio. Una eliminación manual de su directorio fue **rechazada por revisión
automática** y no se repitió mediante otro mecanismo.

Directorio retenido:
`C:\Users\joseh\AppData\Local\Temp\nova-browser-block5-work-_a41emrh`.
Otros perfiles de intentos fallidos aparecen en `cleanup_receipt.json`; no se
reintentó su borrado ni se relabelaron como cerrados. Las ejecuciones finales sí
confirman limpieza de sus propios recursos. No se tocaron recursos históricos.

La extracción local no tiene `.git`. No se inicializó uno. No hubo staging,
commit, push, tag ni release, cambios a preferencias personales, instalación de
Chrome/Edge, campañas históricas ni escritura en evidencia de bloques previos.
