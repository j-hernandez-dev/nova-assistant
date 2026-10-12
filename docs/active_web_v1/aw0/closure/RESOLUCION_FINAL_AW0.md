# Resolución final aditiva de AW0 — Freeze y contratos

Fecha: 2026-10-09. Alcance: cierre normativo de fase mediante evidencia existente; sin nuevas pruebas ni cambios de implementación.

```text
AW0 original execution verdict = PARTIAL
AW0 normative phase closure = PASS
AW0 = PASS
SAFE_TO_ADVANCE_TO_AW1 = true
```

Esta resolución no sustituye la ejecución original, no la recalifica y no convierte el fallo Core en PASS. Se conserva íntegro [resultados.md](../resultados.md), [manifest.json](../manifest.json) y sus artefactos. El flag de avance expresa elegibilidad normativa, no ejecución ni autorización automática de AW1.

## 1. Fuente normativa y fundamento del cierre

[NOVA_ACTIVE_WEB_ARQUITECTURA_V1.md](../../../architecture/NOVA_ACTIVE_WEB_ARQUITECTURA_V1.md), §35, AW0 — Freeze y contratos, establece literalmente:

> - freeze de baseline;
> - corpus de invariantes;
> - DTOs/enums;
> - capability snapshot;
> - CI contract inventory.

> Cierre: ninguna implementación browser todavía; contratos coherentes.

El criterio es contractual y de alcance. No exige implementar un browser ni sanear toda deuda previa de Core. Los cinco entregables y el cierre literal ya figuraban como PASS en la evidencia original.

§37 conserva literalmente estas obligaciones globales:

> 27. No se reabren resultados históricos Knowledge.
> 28. CI no usa skips/xfails nuevos para fabricar verde.
> 29. Regresión heredada Core/Security/Memory/Knowledge sigue aplicable.

Para AW0, demostrar ausencia de regresiones introducidas cumple la obligación de regresión aplicable: se comparó la misma selección heredada antes y después, se conservaron fallos y skips, y los contratos añadidos pasaron. No se encontró un requisito adicional en §35 que convierta toda deuda preexistente en bloqueo de AW0.

La fila original «full inherited current regression green before overall task closure» fue una condición operativa conservadora del informe de ejecución, no una cláusula del gate AW0. Permanece PARTIAL en aquel informe. Esta resolución separa ese veredicto de ejecución del cierre normativo, sin editar arquitectura, umbrales, selección, assertions ni resultados. No establece una exención general para fases futuras ni evalúa el READY global de §37.

## 2. Baseline e integridad verificados en sólo lectura

- Branch: `main`; HEAD: `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`.
- Estado recibido: dos modificaciones tracked de AW0 (`local_cli/core/contracts.py`, `ci/pytest_contracts.json`) y trece archivos untracked de entradas/evidencia/contratos AW0; index vacío. No limpieza ni restauración.
- Plataforma de la evidencia reutilizada: Windows 11 build 26200 + NTFS local + HOST_UNISOLATED; Nova 0.12.6; Python 3.14.6; Node 24.16.0.
- Arquitectura SHA-256: `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`.
- Manifest original SHA-256: `21a4a5b1a0af13e983873812dc78ac777f51b4c65c22427e7d3b1b1e7f0681f0`.
- Resultados originales SHA-256: `1f31b7a00bad32db77fa10899ba92a839d71fc047e88de5f92434b774ee14161`.
- Los catorce pins de artefactos/entradas originales coinciden. Al reconstruir el agregado con los SHA previos de las dos modificaciones AW0 declaradas, los 2181 archivos tracked producen nuevamente `b2b7c3c361e8dffdbc778e81b48fab90faf576f86d376733ce91dd99aaa72d1e`.
- Tags Core, Security, Memory, Memory V1.1 y Knowledge intactos; ningún drift inesperado. Se verificaron los XML existentes, sin ejecutarlos de nuevo.

[manifest_final.json](manifest_final.json) conserva los pins, paths, hashes XML, comparación de IDs y estado Git observado. La evidencia histórica y los intentos incompletos/de entorno siguen referenciados por [test_results.json](../test_results.json); no se elimina ninguno.

## 3. Gate literal AW0

| Requisito | Resultado | Evidencia existente |
|---|---|---|
| Freeze de baseline | PASS | baseline_freeze.json; integrity.json; agregado y pins preservados |
| Corpus de invariantes | PASS | invariant_corpus.json: 50 AW-INV literales; comprobación contra la arquitectura |
| DTOs/enums | PASS | Schemas V1 y codecs inmutables; 128 casos AW0 focused y los mismos 128 dentro de Core |
| Capability snapshot | PASS | UNKNOWN por defecto, compatibilidad legacy y contratos truthfulness |
| CI contract inventory | PASS | 3821 contratos base clasificados; 26 aditivos AW0; 3795 entradas previas intactas |
| Ninguna implementación browser todavía; contratos coherentes | PASS | DTO-only, inventario/integridad y contratos; ningún engine, adapter, manager, tool browser ni BrowserPort implementado |
| Ausencia de regresiones introducidas por AW0 | PASS | Mismo fallo y mismos siete skips Core antes/después; newFailures=0, newSkips=0, newXfails=0 |

El corpus de 50 invariantes es evidencia contractual de AW0, no certificación de cincuenta comportamientos browser runtime. Capability snapshot no crea autoridad ni anuncia una capability implementada. PASSIVE_WEB y ACTIVE_WEB permanecen separados; contenido web sigue siendo dato no confiable.

## 4. Regresiones reutilizadas, sin reinterpretación

| Corrida existente | PASS | FAIL | ERROR | SKIP | Exit code |
|---|---:|---:|---:|---:|---|
| Core baseline nativo aislado | 2739 | 1 | 0 | 7 | 1 |
| AW0 focused | 128 | 0 | 0 | 0 | No persistido separadamente |
| Core final | 2867 | 1 | 0 | 7 | 1 |
| Security final | 615 | 0 | 0 | 0 | 0 |
| Memory final | 791 | 0 | 0 | 0 | 0 |
| Knowledge final | 1015 | 0 | 0 | 0 | 0 |
| Desktop original | 68 | 0 | — | 0 | 0 |

Core baseline/final conservan además 53 subtests PASS. Python final suma 5288 PASS / 1 FAIL / 0 ERROR / 7 SKIP, más esos subtests; los 128 focused ya están incluidos en Core final y no se suman dos veces. TypeScript original `--noEmit`: exit 0.

Los siete skips coinciden exactamente en baseline/final: tres por privilegios de symlink, dos por bits POSIX y dos del monitor legacy retirado. No se añadió skip, xfail, filtro ni retry. Se reutilizan los gates ordinarios positivos aplicables; no se afirma un replay de todas las campañas históricas ni una nueva certificación Core/Security/Memory/Knowledge.

## 5. Deuda heredada no bloqueante para AW0

```text
tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available
test outcome = FAIL
historical classification = HARNESS_BUG / PREEXISTING
debt classification = PREEXISTING_CORE_HARNESS_DEBT
AW0 blocking status = NON_BLOCKING_FOR_AW0
```

El entorno privado asigna HOME y USERPROFILE a directorios distintos. El alias BashTool utiliza PowerShell nativo; `$HOME` es su variable automática derivada de USERPROFILE, no `$env:HOME`. El assertion compara el otro directorio. La evidencia original reproduce este mismo fallo antes y después de AW0.

Test, assertion, producto shell y runner asociados permanecen sin cambios; sus hashes se incluyen en el manifest aditivo y su conservación queda respaldada por el agregado original reconstruido. Core sigue teniendo un FAIL y exit 1: no se presenta como un job completamente verde.

La deuda queda abierta para mantenimiento con autorización separada. No se repara, oculta, excluye ni convierte en skip/xfail. Su condición no bloqueante se limita al cierre normativo contractual de AW0 y no altera certificaciones anteriores.

## 6. Resolución y límites

Todos los entregables y el criterio literal de §35 están demostrados; la evidencia comparativa demuestra cero regresiones introducidas. No se detectó contradicción normativa que impida el cierre aditivo:

```text
AW0 = PASS
SAFE_TO_ADVANCE_TO_AW1 = true
```

Se crearon exclusivamente esta resolución y su manifest. Cero nuevas pruebas, inferencias, launches browser, cambios de producto/tests/CI/harness/arquitectura o mutaciones de evidencia histórica. Sin commit, push, tag ni release.

No se declara ACTIVE_WEB_CORE=READY, engine/broker operativo, aislamiento del proceso host ni certificación de plataformas adicionales. AW1 no se implementó ni inició; queda pendiente revisión humana.

