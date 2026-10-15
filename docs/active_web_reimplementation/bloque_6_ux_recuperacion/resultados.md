# Bloque 6 — UX y recuperación

Estado: **PASS**. Implementado en `C:\Users\joseh\Downloads\nova-min\nova-assistant`.
Este bloque es implementación y regresión focal. No reabre Active Web/HUX ni
realiza el bloque 7 de distribución y aceptación final.

## Cambios de producto

- La CLI normal presenta estados del host en inglés y conserva el idioma de las
  respuestas del modelo. Los resultados JSON, argumentos y eventos internos
  quedan en `--debug`; los eventos tipados siguen disponibles en Application.
- `/browser status` muestra estado, control humano y disponibilidad de página;
  los errores administrativos muestran un mensaje de uso sin traceback.
- El catálogo del modelo se actualiza en cada generación según instalación y
  estado real de sesión. Las acciones sobre página no se anuncian antes de tener
  una página abierta. No se introdujo clasificación lingüística de intenciones.
- Runtime ausente, referencias stale, página perdida, bloqueo de buscador,
  cancelación y timeout producen resultados estructurados con orientación de
  recuperación. Esa orientación no concede permisos.
- Un fallo de búsqueda no deshabilita herramientas locales ni prohíbe otras
  navegaciones permitidas. Un resultado posterior correcto limpia el error viejo.
- Después de perder una página, una **nueva propuesta** de navegación puede
  cerrar la sesión owned anterior y crear un binding nuevo antes de Policy/Grant.
  Cleanup incierto impide reemplazarla. No se parchea un Grant anterior.
- Cancelación/timeout después del comienzo conserva `UNKNOWN` cuando corresponde.
  Una sesión que no responde queda bloqueada para acciones Browser hasta cierre
  confirmado. Las herramientas locales permanecen disponibles.
- Tres llamadas consecutivas fallidas fuerzan una explicación final sin tools;
  un resultado correcto reinicia el contador. Una respuesta vacía tiene sólo la
  recuperación acotada existente y después un mensaje explícito.
- La representación normal deduplica eventos repetidos y la misma respuesta
  final ya transmitida. No imprime además el mismo fallo como JSON crudo.

## Comandos sin redundancia

| Se conserva | Se retira | Motivo |
|---|---|---|
| `/fetch [on\|off\|status]` | `/web fetch ...` | Mismo control de Fetch |
| `/exit` | `/quit` | Misma salida de CLI |

Los alias retirados ya no ejecutan acciones y tampoco aparecen en `/help`.
Se conservaron comandos con funciones distintas: `/save` guarda conversación y
`/checkpoint` crea un checkpoint Git; `/knowledge` y `/source` gestionan datos
distintos; `/models` selecciona interactivamente y `/model <name>` cambia por
nombre. Browser, búsqueda y Fetch conservan controles administrativos separados.

## Permisos y composición

Policy, Approval y Grant continúan siendo obligatorios después de la propuesta
del modelo. Omitir una herramienta del catálogo no sustituye sus validaciones.
La prueba directa de una propuesta oculta mantiene el rechazo antes del efecto.
El clic aprobado con pérdida posterior conserva `UNKNOWN`, un único efecto real
y ningún reintento. No se cambia UNKNOWN por éxito remoto.

No se cambió el host C#, protocolo IPC, runtime empaquetado, Policy ni las
primitives de transfers/secretos. `pages.py` añade comprobación de conexión antes
de acceder a la página; `browser_navigation.py` modifica ciclo de vida y
recuperación Python. Las identidades comparadas están en
`historical_preservation.json`. Se mantienen los claims del Browser:
`networkIsolation = NOT_PROVIDED`, `controlClass = HOST_UNISOLATED`.

CLI y JSONL/backend consumen el mismo Application y los mismos resultados.
No se cambió la lógica ni el idioma de Desktop. Sus 29 pruebas de contrato
pasaron usando la dependencia TypeScript ya instalada, sin instalar otra copia.

## Validación

| Verificación | Resultado |
|---|---|
| Regresión Python final: AgentLoop, CLI, sesión, Browser, archivos, Policy/Approval/Grant/redacción | 604 passed, 0 failed, 0 skipped |
| Casos nuevos UX incluidos en esa regresión | 16 instancias / 12 funciones |
| Inventario CI | 3890 funciones, 0 sin clasificar |
| Job manual Windows `browser-block6` | PASS, 1 prueba nativa recogida y ejecutada |
| Regresión nativa navegación/búsqueda WebView2 + Edge | PASS |
| Regresión nativa takeover/secretos/upload/download WebView2 + Edge | PASS |
| Desktop: Application client y Approval host | 29 passed |
| Smoke manual `qwen3.5:9b` + WebView2 + lectura local | PASS |

Los 604 casos ya incluyen los 16 nuevos: no se suman otra vez. Los jobs nativos
son tres entry points distintos que contienen checks focales; esos checks no se
inflan como tests independientes. Las ejecuciones repetidas de desarrollo y del
modelo no aumentan el denominador de regresión.

El smoke de modelo usó el perfil productivo de `qwen3.5:9b`, contexto 8192,
temperature 0.6, top_p 0.95, top_k 20, think=false. El modelo eligió
`browser_navigate` y `read`, obtuvo ambos marcadores owned y respondió en español.
Es un smoke funcional, no una medición de calidad general del LLM.

Los fixtures no dependen de buscadores públicos: verifican popup gestionado,
resultados vacíos, HTTP 403, cierre de ventana humana sin resume automático,
cancelación antes del efecto, pérdida real tras clic, barrera UNKNOWN y nueva
navegación. Los dos primeros intentos nativos fallaron por calibración del fixture
(cuerpo HTTP 403 vacío y cierre encolado detrás del pump humano); sus receipts se
conservan con FAIL. El intento corregido, los jobs y el smoke de modelo pasaron.

Después de esos smokes se precisó únicamente el texto de recuperación de cleanup
incierto: no sugiere observar una sesión sin cierre confirmado. La regresión
final de 604 casos incluye esa precisión. No se atribuye el smoke anterior a una
nueva campaña de certificación.

## Limpieza y límites

Los receipts de este bloque confirman host finalizado, job vacío, perfiles owned
retirados, directorios de trabajo retirados y listeners detenidos. Los archivos
de reportes temporales se conservaron como evidencia de pruebas; no son perfiles
activos. No se borraron recursos del usuario.

El cleanup incierto histórico del bloque 5 conserva exactamente su estado
`UNCONFIRMED_POLICY_BLOCK`. No se intentó otra eliminación ni se reinterpretó como
confirmado. Se compararon 82 archivos de evidencia anterior sin modificaciones;
no se usó restore-by-hash.

Chrome no está instalado en esta máquina: se verificó el negativo sin fallback;
los smokes positivos opcionales usan Edge. Windows es la plataforma validada.
Los buscadores externos pueden seguir imponer CAPTCHA o bloqueos: Nova los
explica y permite intervención/configuración explícita, sin prometer evadirlos.
La presentación limita ruido; no garantiza la calidad semántica de toda respuesta
de un modelo arbitrario. El bloque 7 queda pendiente de solicitud.

No se ejecutó staging, commit, push, tag ni release. La carpeta es una extracción
sin `.git`; no se inicializó un repositorio.
