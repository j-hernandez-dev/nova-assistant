# Fixed Version app-local — decisión futura, no ejecución

**Técnicamente compatible de forma condicionada** con local-first y versionado congelado; no implementado, requerido, descargado ni instalado aquí.

Microsoft ofrece distribución Fixed Version empaquetada por app, seleccionada mediante browserExecutableFolder. No usa instalación del runtime en registro y requiere que la app gestione actualizaciones y tamaño adicional. La documentación excluye UNC/network locations y señala permisos AppContainer adicionales para unpackaged Win32 en Windows10 desde120; esa salvedad no aplica al Windows11 de este host. [Distribución oficial](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution).

Para Nova sería necesario: carpeta binaria local app-owned, hashes/arquitectura firmemente ligados a proof, actualizaciones explícitas con recertificación, UDF privado separado sin secrets en carpeta binaria, no fallback a Evergreen si ese folder falla y comprobación de overrides. ACLs de lectura AppContainer deben limitarse al runtime app-local; no implicar admin ni cambios globales. No se afirma que todos los modos de deployment/Windows10 puedan cumplirlo sin comprobar permisos del owner.

Fixed Version ayuda a controlar drift; **no añade** APIs de WebRTC-off/SW-off ni convierte flags en garantías. Empaquetar el mismo runtime no arregla el STUN directo observado. Por ello no se introduce como requisito silencioso ni como reparación en esta fase.

Los flags siguen sujetos a proof nativo y mantenimiento del perfil exacto. La documentación de Microsoft los describe como herramienta de desarrollo no estable; la aprobación humana aquí es condicional y no modifica ese contrato upstream. [Flags WebView2](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/webview-features-flags).
