# GUI-B6 — Modelos en el modal de Nova

Fecha: 2026-10-16. Proyecto: `C:\Users\joseh\Downloads\nova-min\nova-assistant`.

## Resultado

El botón del cerebro abre el catálogo existente en un modal central con fondo oscurecido, borde ámbar, pestañas, filtro, lista desplazable y acciones explícitas. Se conservan las tres vistas y sus operaciones. La selección del compositor sigue siendo exclusivamente el inventario local de Ollama.

| Vista / función | Comportamiento |
|---|---|
| Para ti | Recomendaciones existentes, hardware observado, motivo y descarga o selección local. Se aclara que la recomendación no garantiza rendimiento. |
| Catálogo | Filtro por texto, categorías, instalados, parámetros, contexto, fecha, descripción, fortalezas y valoración existente. |
| Descubrir | Consulta existente a la biblioteca de Ollama, búsqueda, orden popular/tendencias/recientes y capacidades. Los resultados sólo disponibles en la nube no ofrecen descarga local. |
| Instalados | Contador de nombres únicos observados en Ollama. Si no hay una observación válida se indica indisponibilidad, no un cero inventado. |
| Seleccionar | Usa el nombre exacto instalado. Una familia con varias variantes conduce al filtro de instalados; nunca elige un tag arbitrario. Conserva el comando ChangeModel de Application, su receipt y snapshot posterior antes de confirmar/persistir la selección. |
| Descargar | Reutiliza pull_model. Progreso real, una mutación en curso, errores claros. Terminar una descarga no selecciona el modelo. |
| Eliminar | Reutiliza delete_model con confirmación en dos clics. El modelo activo no ofrece borrado. Cambiar de tag invalida la confirmación anterior. |
| Sincronizar | Reutiliza update_catalog. Un fallo de todas las consultas no se presenta como sincronización completada ni sobrescribe la caché. |
| Cerrar / reabrir | Clic exterior, Escape y botón de cierre. El estado de operaciones vive en App; cerrar la presentación no cancela ni repite una descarga. |

Las cifras aproximadas y estrellas se identifican como metadatos del catálogo, sin convertirlas en mediciones locales. Los textos propios conocidos se proyectan a ES/EN; los textos externos desconocidos conservan el original. Los nombres y tags no se traducen.

## Cambios de implementación

- `desktop/src/components/ModelPicker.tsx`: composición y acciones del modal.
- `desktop/src/styles.css`: estilos acotados al catálogo; cabecera y pie fijos, contenido desplazable, adaptación a ventana mínima.
- `desktop/src/i18n.tsx`, `model_catalog_locale.ts`, `model_catalog_presentation.ts`: mensajes ES/EN, metadatos propios y resolución exacta de variantes.
- `desktop/src/App.tsx`, `model_operations.ts`: ciclo de operaciones independiente del montaje del modal, correlación por request ID y validación de payloads antes del render.
- `desktop/electron/application_client.ts`, `main.ts`: errores auxiliares se representan una vez en su panel mediante ownership de solicitudes salientes. Errores generales y de Application siguen visibles.
- `local_cli/model_search.py`, `model_catalog.py`, `server.py`: modo estricto opcional para distinguir fallo de biblioteca de una búsqueda vacía, con errores sanitizados y correlacionados en JSONL. Los callers legacy conservan su comportamiento por defecto.
- Pruebas y registro en el inventario CI actual; no requieren GUI, Ollama, descargas ni Internet.

No se cambiaron el loop del agente, el prompt del modelo, permisos, Policy/Approval/Grant, Browser ni configuración personal. No hay autodescargas ni autoselección. No se crearon dependencias ni instaladores.

## Correcciones verificadas

1. Un tag instalado no hace seleccionable otra variante de la misma familia.
2. Respuestas antiguas de búsqueda no reemplazan la consulta más reciente.
3. Los errores terminan sus indicadores de carga y se muestran en el panel correspondiente.
4. Un receipt perdido no implica éxito ni habilita otra descarga/borrado: queda sin confirmar hasta evidencia posterior o un nuevo arranque observado.
5. Metadatos mal formados no llegan a JSX ni producen excepciones por objetos o listas inválidas.
6. Los temporizadores están vinculados al contexto global: se corrigió `Illegal invocation`, detectado en Chromium/Electron durante la comprobación visual.
7. Una indisponibilidad de la biblioteca no se transforma silenciosamente en «sin resultados» o «sincronizado».

## Verificación

| Comprobación | Resultado |
|---|---|
| TypeScript completo, sin emitir | PASS |
| Suites ordinarias Desktop | 215/215 PASS |
| Biblioteca, manager de modelos, readiness y subset proporcional de server | 95/95 PASS, incluidos 11 casos nuevos de biblioteca |
| Inventario estático CI | PASS; nuevas suites clasificadas explícitamente |
| Electron real, fixture local, 1280×820 y 600×400 | PASS; pestañas, lista, acciones y cierre accesibles |
| Filtro / Para ti / Descubrir / fallo de biblioteca | PASS con respuestas owned, sin Internet |
| Descarga simulada, cerrar y reabrir | PASS; se conserva 40 %, termina por receipt, refresca inventario y mantiene el modelo activo anterior |
| ES/EN | PASS; controles y mensajes propios localizados |
| Historial documental previo | 1627 archivos byte-intactos |

Regresión adicional: tres tests de `test_nova_core_phase7_server_legacy.py` fallan también en el checkout anterior a B6. La fixture `sudo echo hi` obtiene `AUTO_ELEVATION_DENIED` en este host Windows. Se registran como fallos previos; no se cambió ese gate para aprobarlos.

La comprobación visual usa el renderer real y DesktopApplicationClient con un backend owned de catálogo/operaciones. No acredita descargas reales desde Internet ni rendimiento de inferencia, y no alteró los modelos del usuario. El borrado se verifica determinísticamente y no se ejecutó sobre modelos personales. La selección y persistencia mantienen la regresión B2 existente.

## Preservación y entrega

Se mantuvieron intactos los documentos históricos de Active Web, HUX y los resultados GUI previos. Los archivos de fixtures visuales y logs permanecen fuera del repositorio, en el staging de trabajo. La limpieza se acotó a las ventanas owned y al PID/comando verificado del listener de este bloque. No se afirma que una instancia Desktop previa continúe abierta tras la recarga del código en desarrollo.

No se hizo staging Git, commit, push, tag, release, empaquetado ni compilación de ejecutables.

GUI_B6_MODELOS = PASS
