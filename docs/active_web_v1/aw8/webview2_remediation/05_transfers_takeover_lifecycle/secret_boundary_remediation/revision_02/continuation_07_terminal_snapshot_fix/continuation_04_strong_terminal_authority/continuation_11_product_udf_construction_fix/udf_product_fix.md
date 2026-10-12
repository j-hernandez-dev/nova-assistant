# Product UDF construction fix

La única modificación existente es la llamada de construcción en WebView2HostClient: tras conservar la validación del managed_root heredado, el UDF ya no se sitúa bajo el árbol largo de workspace/evidence/staging. Lo determina la nueva primitive Infrastructure productive_udf_path.

Root estable: Windows LocalAppData conocido por shell32, seguido de Nova/Wv. Nova ya utiliza LocalAppData/Nova para datos locales (audit_config.py). No se consulta una variable de entorno/modelo para elegir este root y no existe fallback al root anterior.

basename = nova_wv2_<session>_<instance>, conservando bws_ y bhi_ con exactamente 32 hex lowercase. LifecycleServer, NativePipe, marker .nova-owner, factory ACL, process Job Object y algoritmos de cierre/cleanup permanecen byte-intactos.

El presupuesto interno es 128 unidades UTF-16 para el path completo. B3 demuestra que esa construcción es viable, no que 128 sea un límite del engine. En este host el resultado es 119. Un profile/user path que no quepa falla cerrado antes de crear host; no se acorta un ID ni se prueba otro directorio.

Nova crea/valida un root privado al usuario con una única ACE protegida y un marker de versión/SID. Un root leaf ajeno existente no se reutiliza ni se cambia su ACL. Los ancestors, root y entradas top-level rechazan reparse/symlinks. Se comprueba writable con un archivo nuevo opaco retirado antes del setup. El root se limita a 1024 entradas; overflow falla cerrado sin borrar perfiles/audits existentes.

El root estable/marker y recibos durables pueden sobrevivir a sesiones; no se confunden con el UDF efímero ni con staging. No hay mantenimiento automático. El contrato histórico de UDF unowned conserva OWNERSHIP_MISMATCH/CLEANUP_UNCONFIRMED y nunca elimina foreign data. Las pruebas de ese contrato pueden dejar deliberadamente su sentinel; eso no se recalifica como cleanup confirmado.

No cambios a transfers, Perform, provider, headers, callbacks DownloadStarting, Approval/Grant, staging, outcomes, timeouts o retries. No se afirma subcausa parent path/longitud/namespace/profile initialization y no se continúa diagnosticándola.

Validación secuencial congelada: A nuevos contratos UDF; B cuatro downloads productivos; C lifecycle/ownership/guard/observations/actions/transfers/takeover-secret critical; D una única full del directorio nativo completo. Sin cambiar producto entre focal y full. El histórico 527/10 y toda la evidencia causal permanecen inmutables.
