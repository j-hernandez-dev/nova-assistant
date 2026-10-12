# Reconciliación prospectiva de expected outcomes

Decisión humana: HISTORICAL_EXPECTATION_REQUIRES_UNCONFIRMED_TERMINAL_INFERENCE = true. Sólo cambian expectativas/preparación diagnóstica de test para los paths equivalentes que pierden una generación sensible sin submit y sin checkpoint vivo. Producto congelado de continuation_03_retirement_lifecycle_only, sin cambios.

## Clasificación previa a medición

La clasificación inmutable está en classification_before_measurement.json, escrita antes de A. Los tres históricos se clasifican DENY_TERMINAL_CONTINUITY_UNCONFIRMED. Focal33: nueve denials y 24 expectativas positivas preservadas. Policy24: navigation/cross/history denials; otras 21 expectativas sin cambio. Supplemental y native-navigation-diagnosis comparten exactamente la misma precondición de pérdida de fuente terminal.

| Test/helper | Casos | Expectativa anterior | Nueva expectativa / prueba |
|---|---|---|---|
| native/nova-browser-host/tests/transient_policy_runner/Program.cs | native-navigation, native-cross, native-history | EndTakeover succeeds, Capture returns a fresh payload, terminal is COMMITTED | Prove observed/known value, retired generation without strong snapshot, exact continuity denial, paused state, no observation, known values retained and cleanup |
| native/nova-browser-host/tests/test_sensitive_continuity.py | test_native_document_and_world_lifetime[same-origin], [cross-origin], [immediate], [history], [iframe-destroy] | finish then new model observation / epoch increment | Prove actor and retired-generation metadata, typed denial, unchanged context epoch, paused Application, no model observation; unchanged same-document positive checks |
| native/nova-browser-host/tests/test_sensitive_disconnect_diagnostic.py | test_native_capture_exception_diagnostic[same-origin], [cross-origin], [immediate], [history] | delegated navigation scenario resumes | Same classification as underlying unchanged navigation scenario; test-only scalar evidence host build |
| native/nova-browser-host/tests/test_takeover_secret_navigation.py | test_declared_human_secret_not_projected_after_same_origin_navigation | post-document replacement resume/new model observation | Same lost-generation/no-submit security denial; all fixture/driver/navigation unchanged |
| native/nova-browser-host/tests/sensitive_runner/Program.cs | native-navigation-diagnosis | post-navigation resume/capture | Equivalent lost-generation path denies without publish and retains known sensitive values |

## Proof positivo de denial

El runner C# policy lee estado host-private: sensitive observado y conocido, current/revision de control real retirado, sin snapshot/commit ni documento vivo, reason interno de continuidad (no short), error público exacto, takeover aún activo, context epoch sin avance y capture bloqueado. El error se valida con serializer cerrado, result null, sin material literal.

Los históricos Python usan un build de harness con el mismo código productivo congelado. ContinuityProofSink observa únicamente los hooks escalares existentes de lifecycle/terminal/failure; el observador productivo permanece null. No CDP/input taps nuevos, raw secret, page text ni autoridad IPC. El sink es bounded (64 pares generación/control, overflow hace fallar la prueba), privado al UDF/host/owner y registra retiro, current revision/length, conteos de snapshots/commits y primer reason. Que el control retirado tenga current no vacío deriva del Observe/Add monotónico pinneado; el reason final correlaciona la misma generación/control/revision conservados. No se exporta el buffer.

El harness sigue probando actor/reflection host-native y completion humana con sus primitives existentes. Luego exige reason TERMINAL_CONTINUITY_UNCONFIRMED, error SECRET_BOUNDARY_UNCONFIRMED, Application pausada, epoch sin incremento, observations invalidadas y capture rechazado. Las assertions originales de ausencia permanecen en los paths que publican una observation. El path de denial no inventa una projection para ejecutar assertions post-resume incompatibles: prueba afirmativamente que ninguna puede publicarse. No es un pytest.raises aislado.

## Rama positiva y denial corto

Dos pruebas nativas aditivas ejercitan un form asociado real con submit observado/COMMITTED antes de takeover_end y un world vivo con checkpoint correlacionado. Exigen resume, incremento epoch, fresh capture y ausencia del valor, más cleanup. El antiguo native-submit no se presenta por sí solo como prueba de submit de un input que su fixture no asocia al form. Las tres pruebas nativas de committed corto genuino 1–3 permanecen byte-intactas y distinguen SHORT_COMMITTED_VALUE.

## Integridad del alcance

Valores/longitudes, HTML históricos, driver humano, secuencias, sleeps/timeouts y assertions de las ramas positivas sin cambio. No excepciones de redacción, nuevas autoridades terminales, skips, xfails ni retries selectivos. El build de proof es sólo test infrastructure; no capability, schema IPC ni tool. No mantenimiento sobre los 36 UDF históricos.

Before SHA se registró en reconciliation_before.json; after y nuevas pruebas se registran en candidate_freeze.json. Los FAIL anteriores siguen literales y no se recalifican. Se ejecutarán A → B → C (tres IDs ×5) → D (33) → E (directorio completo), deteniéndose ante cualquier mismatch nuevo.

