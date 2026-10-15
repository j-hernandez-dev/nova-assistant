# Harness focalizado de cierre Knowledge Inputs V1

Código aditivo para las correcciones R1/R2 aceptadas. No es V2-R5 ni una nueva
campaña. No importa el runner/adaptador/scorer V2 ni contiene un proveedor LLM.

- `observe_tool`: correlaciona ToolRequested/ToolStarted/terminal por operationId
  con el ToolResult real. Distingue solicitud, rechazo, ejecución observada,
  efectos de files/Memory y cambios de autoridad. Un grant legítimo emitido por
  ToolRuntime no se atribuye al documento. Una atribución documental necesita
  evidencia de host independiente con source/revision y referencia de audit;
  un cambio de autoridad sin provenance queda UNRESOLVED, no seguro/PASS.
- `IsolationFixture`: un SQLiteKnowledgeStore/KnowledgeLease físico compartido
  por servicios de acceso distintos. Recovery precede la siembra; todos los
  contexts permanecen vivos durante las comprobaciones. Import usa adquisición
  local y extractor productivos. Retrieval usa KnowledgeService/DocumentRetriever
  reales, sin admisión al contexto ni modelo. El cierre pertenece al fixture,
  no a cada servicio compartido.
- `test_focused.py`: seis tests R1 y cuatro R2. Incluye rechazo real de búsqueda
  deshabilitada, HTTP sintético pasivo sin sockets, cambios/evidencia sintéticos
  explícitos, SESSION isolation, WORKSPACE sharing/foreign isolation y rechazo
  vigente de un segundo propietario. No ejecuta casos K8.
- `run_focused.py`: salida fresca fuera del checkout, sin Temp nuevo, pytest
  sin plugins externos/cache/bytecode, red real bloqueada por los tests,
  preservación SHA antes/después y verificación read-only de los 629 pins R4.
  Reutiliza en lectura el árbol de dependencias ya congelado de K3; no instala.

Estas APIs quedan disponibles para futura evidencia focalizada autorizada.
No sustituyen retrospectivamente los adaptadores congelados ni sus scores.
