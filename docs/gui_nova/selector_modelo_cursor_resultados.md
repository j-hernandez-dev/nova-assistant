# Selector de modelo y cursor de escritura

## Cambio de modelo

Se reprodujo una carrera entre la aceptación de `ChangeModel`, la llegada del snapshot con la identidad nueva y una comprobación de disponibilidad todavía pendiente. La cancelación local de la comprobación anterior no liberaba su petición en el backend, por lo que podía lanzarse otra consulta antes de tiempo o presentarse un resultado de la identidad anterior.

- La comprobación espera a que Application confirme el modelo y la revisión correspondientes.
- Una comprobación anterior conserva su lugar hasta finalizar; su resultado queda descartado si pertenece a una observación invalidada.
- La consulta de la identidad nueva se lanza después de finalizar la anterior. No se repite el cambio de modelo ni una tarea del usuario.
- Se retiran las comprobaciones redundantes del selector y del cambio de proveedor en React. El host coordina la disponibilidad después del snapshot.
- Una indisponibilidad real de la comprobación actual sigue mostrándose como tal. Durante el cambio no se ofrecen acciones de configuración basadas en el modelo anterior.

## Cursor

El cursor estaba colocado después del contenedor Markdown, lo que lo situaba debajo de los bloques. Ahora forma parte del último fragmento renderizado: línea de párrafo, encabezado, elemento de lista, bloque de código o celda de tabla. Su tamaño se adapta a la tipografía del fragmento.

El cursor se retira al finalizar o interrumpir la respuesta y no se presenta en mensajes de usuario ni en llamadas a herramientas. El Markdown original y su copia permanecen separados del indicador visual.

## Validación

- Las dos nuevas reproducciones de la carrera fallaron antes de la corrección y pasan con ella.
- 97 pruebas Node correctas: disponibilidad, cambio y persistencia del modelo, Markdown, mensajes, actividad, historial y ajustes.
- TypeScript y `build:source` correctos.
- Electron real en Windows, con perfil y proveedor simulados: cuatro cambios desde el selector mientras una consulta anterior seguía pendiente, sin avisos falsos ni cambios duplicados.
- Medición geométrica del cursor respecto al último carácter en párrafos de varias líneas, código en línea, encabezados, listas, bloques de código y tablas. Captura de la vista de párrafos revisada visualmente.

La comprobación de Windows no carga modelos reales ni modifica el perfil personal. Los casos de indisponibilidad actual se conservan en las pruebas para evitar ocultar una desconexión real.
