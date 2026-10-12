# AW1 — Dominio y lifecycle

`AW1 = PASS`. Fecha: 2026-10-09. Cierre exclusivamente contractual con adapter falso; no READY ni navegador real.

## 1. Fuente y preflight

Fuente normativa: [NOVA_ACTIVE_WEB_ARQUITECTURA_V1.md](../../architecture/NOVA_ACTIVE_WEB_ARQUITECTURA_V1.md), §35:

> ### AW1 — Dominio y lifecycle
>
> - BrowserSessionManager;
> - Page refs;
> - quotas;
> - fake BrowserPort;
> - cancel/cleanup.
>
> Cierre: lifecycle determinista con adapter falso.

Contexto: auditoría y findings AW-AUD-001/012/018/027/031. La autorización vigente fija N=1: se aplica AW1, no la plantilla AW0 anterior.

Branch `main`; HEAD `b0bf60f91956e4a5c17af02be5a6e241ec0363a7`; Nova 0.12.6. Working tree previo: dos modificaciones tracked y quince archivos untracked heredados de AW0/entradas/cierre aditivo; index vacío. [baseline_freeze.json](baseline_freeze.json) conserva estado, tags, pins de entradas/evidencia/componentes y agregado raw de 2181 archivos `297a732140956cd5f06f2237b61ef37dbc23c00ffd868054830f52912acaa9fe`.

AW0 conserva ejecución original PARTIAL y cierre normativo PASS, incluidos ambos manifests y resolución. Arquitectura intacta: SHA `e09eb2d7bfe8da8becec79f557c84db3696e8b8abff80e2a3286bf71ac5a098e`.

Antes de modificar producto se ejecutó AW0 + Core phase4/phase7 session + el caso HOME/USERPROFILE: **154 PASS / 1 FAIL / 0 ERROR / 0 SKIP**. El FAIL es la misma deuda heredada; no apareció incumplimiento nuevo que bloqueara este dominio.

## 2. Reutilización y delta mínimo

- Refs/enums AW0, IDs Core y CancellationToken sin modificaciones.
- CancellationController existente, incluidos parent/child tokens; cancel request no equivale a terminal ni rollback.
- Inventario/runner positivo CI existente; 37 contratos base AW1 aditivos en el job Core portable. Los 3821 registros previos, reglas y configuración de selección permanecen íntegros; ningún workflow nuevo.
- No segundo AgentLoop, AgentSession principal, grant issuer, Policy, browser tool ni ruta frontend.
- La auditoría ya registra CloseSession como DTO cuyo dispatch general no está implementado. No se altera ese baseline: AW1 ofrece el seam host `close_owner` para terminar recursos del owner; no anuncia soporte frontend de ese comando.

Nuevos módulos [core/active_web_lifecycle.py](../../../local_cli/core/active_web_lifecycle.py) y [application/active_web.py](../../../local_cli/application/active_web.py). El módulo AW0 core/active_web.py permanece byte-a-byte intacto.

## 3. Dominio y contratos

Core incorpora BrowserOwner, BrowserLimits, BrowserSession, BrowserPage, receipts de cancel/cleanup y BrowserPort; vistas/receipts emiten schemaVersion=1. No importan Playwright ni detalles del host. Los snapshots son inmutables y no contienen cookies, credentials, storage, paths de profile, selectors, grants ni approvals.

BrowserPort tiene únicamente create_context/create_page/cancel_page/close_page/close_context. No navega, observa ni ejecuta acciones. Su contrato exige contextos nuevos efímeros y deadlines/tokens; la confirmación exacta True de close_context significa cierre exhaustivo de sus recursos. Un false, valor truthy no booleano, error, trabajo pendiente o respuesta tardía no prueba cleanup.

BrowserSessionManager pertenece a Application. Emite y registra refs opacas, valida owner AgentSession/workspace y rechaza refs desconocidas o de otra sesión. Conserva el mismo contexto entre Turns; close_owner retira ese owner, shutdown no permite reopen, y una nueva instancia no interpreta refs anteriores como resume.

No se bootstrapea el gestor ni se exponen tools en CLI/JSONL/Desktop. Este alcance no afirma ejecución browser agentic, engine instalado, probe válido ni network broker disponible.

## 4. Cuotas, concurrencia y límites

§8.1 y §23.1 se implementan mediante reservas bajo lock:

- una BrowserSession no cerrada por AgentSession, incluso si cambia workspace;
- hasta tres páginas, contando creación/cleanup incierto; una página sólo libera cupo con confirmación;
- una operación admitida en vuelo por página y una con efecto remoto por BrowserSession;
- hasta 25 admisiones de acciones y diez navegaciones por Turn, no por Generation;
- hosts pueden reducir los ceilings, nunca aumentarlos;
- una OperationId finalizada no vuelve a admitirse.

El open de sesión/página inicial consume una admisión; crear páginas adicionales también. Los leases de scheduler no ejecutan acciones ni clasifican riesgo ni autorizan nada. El booleano de efecto/navegación es metadata de host para cuotas, no input público del modelo. La clasificación/Policy/approvals/dispatch corresponde a AW3 y posteriores.

Lifetime, action/navigation timeout y cleanup timeout son parámetros positivos finitos obligatorios del host; no se inventa configuración global. Los valores 120/10/20/5 segundos son fixtures, no defaults normativos. Los deadlines se limitan por host, request y expiración; se comprueban antes y después de llamadas. El port debe cumplirlos; AW1 no certifica preemption ni tiempos de un engine real.

## 5. Cancel, failure y cleanup

CancelTurn solicita cancelación de tokens/port, bloquea nuevas admisiones de ese Turn y conserva una sesión coherente para Turns posteriores. La reserva no se libera hasta que el worker declara terminal mediante finish_operation. Un receipt UNKNOWN de efecto remoto permanece intacto: cancel/close no lo convierte en NOT_STARTED ni NONE.

Los estados CREATING, ACTIVE, CLOSING, CLOSED, FAILED y CLEANUP_UNCONFIRMED se distinguen. Un crash reportado marca FAILED y cancela trabajo; no relanza ni reproduce acciones. Los fallos de creación, incluidas asignaciones parciales, intentan cleanup con presupuesto independiente.

Close es idempotente tras confirmación. La creación aún pendiente impide CLOSED; el worker al finalizar no publica una página activa tardía. Un cierre exhaustivo del contexto puede confirmar sus páginas aunque un cierre individual falló. Sin prueba válida se conserva CLEANUP_UNCONFIRMED y el cupo de sesión. Una nueva comprobación de cleanup requiere llamada host explícita; no hay polling/background relaunch/retry de acciones.

Expire y shutdown son seams host deterministas, no timers globales. La conexión efectiva a engine, exits de frontend, acciones, observation registry y auditoría browser se realiza en fases posteriores. No se presenta ese wiring como implementado.

## 6. Gate literal y trazabilidad

| Criterio | Estado | Componente → evidencia |
|---|---|---|
| BrowserSessionManager | PASS | Application manager → dominio/ownership, estados, lifetime, close_owner/shutdown |
| Page refs | PASS | Factories AW0 + registro host → unicidad, cross-session rejection, creación/cierre, cero late resurrection |
| Quotas | PASS | BrowserLimits + reservas → hard ceilings, cuotas por Turn, page/session serialization, reservas inciertas |
| Fake BrowserPort | PASS | tests/active_web_v1/fake_browser.py → adapter determinista sin browser/red/storage |
| Cancel/cleanup | PASS | CancellationController + receipts → cancel sin rollback, failure/timeout, cleanup confirmado/incierto, pending work |
| Lifecycle determinista con adapter falso | PASS | 59/59 instancias AW1 focales y las mismas 59 dentro de Core completo |
| Ausencia de regresiones introducidas | PASS | 0 newFailures / 0 newSkips / 0 newXfails; misma deuda Core previa y mismos skips |

AW-INV-001/009/016: owner Application y domain refs. AW-INV-010/011/046: contrato efímero/restart con fake, sin claim de profiles reales. AW-INV-031/032/033/047: no replay/rollback, UNKNOWN preservado y cleanup honesto en contratos fake. AW-INV-003/007/008/012/044/045/048/049/050: superficies/herencia preservadas y sin nuevas capabilities/authority paths.

No se certifican los 50 AW-INV runtime: element freshness, Policy/approval, broker, engine, projections, transfer/auth, audit y frontends permanecen en sus fases. El snapshot sigue UNKNOWN; tools browser no se anuncian. PASSIVE_WEB, MEMORY/Knowledge y sus resultados/certificaciones anteriores no cambian.

## 7. Tests, regresión e integridad

Runtime: Windows 11 build 26200 + NTFS local + HOST_UNISOLATED; Python 3.14.6/pytest 9.1.1 en el venv temporal offline ya existente de AW0; Node 24.16.0. Sin instalaciones ni cambios globales. Python 3.10 se comprobó sólo por AST, no por ejecución.

| Ejecución | PASS | FAIL | ERROR | SKIP |
|---|---:|---:|---:|---:|
| Baseline focal previo | 154 | 1 | 0 | 0 |
| AW1 inicial | 43 | 0 | 0 | 0 |
| AW1 + AW0 focal final | 187 (59 + 128) | 0 | 0 | 0 |
| Core final | 2926 | 1 | 0 | 7 |
| Security final | 615 | 0 | 0 | 0 |
| MEMORY final | 791 | 0 | 0 | 0 |
| Knowledge final | 1015 | 0 | 0 | 0 |
| Desktop | 68 | 0 | — | 0 |

Core suma además 53 subtests PASS. Total Python final aplicable: **5347 PASS / 1 FAIL / 0 ERROR / 7 SKIP**, más 53 subtests PASS. No se suma focused de nuevo. Se ejecutaron las cuatro selecciones ordinarias positivas completas; no es un replay de campañas históricas ni certificación host-real browser.

Los siete skips Core coinciden exactamente con AW0: privilegios symlink, bits POSIX y monitor legacy retirado. Sin nuevos filtros, skips, xfails ni retries. Desktop TypeScript --noEmit: exit 0.

El único fallo sigue siendo:

`tests/test_tools/test_bash_tool.py::TestBashToolEnvSanitization::test_non_sensitive_env_vars_available`

**PREEXISTING_CORE_HARNESS_DEBT / HARNESS_BUG / PREEXISTING**. HOME privado difiere de USERPROFILE y PowerShell $HOME usa el segundo. Reproducido antes/después de AW1, con test/assertion/shell/runner intactos. **Sigue FAIL, Core exit 1**, no se presenta como gate global verde. No bloquea el criterio literal AW1 porque no es una regresión introducida ni un fallo del lifecycle fake; no se dispensa ningún gate posterior.

[test_results.json](test_results.json) registra comandos, recibos, denominadores, IDs/skips, timestamps/duración XML y SHA de XML/logs/selecciones. Outputs y fixtures exclusivamente fuera de Git: `C:/Users/joseh/AppData/Local/Temp/nova-aw1-20261009T164424Z/`.

Se conserva la advertencia inicial return-in-finally; se corrigió antes del freeze final, sin alterar tests. La primera comprobación auxiliar de integridad falló por asumir espacios en JSON compacto: se corrigió sólo ese patrón de lectura y se exigió el mismo SHA raw original. [integrity.json](integrity.json) conserva el diagnóstico y demuestra reconstrucción exacta del baseline quitando únicamente la adición CI autorizada.

## 8. Archivos, limitaciones y detención

Modificado exclusivamente en esta fase: ci/pytest_contracts.json (37 entradas + una regla). Nuevos: core/active_web_lifecycle.py; application/active_web.py; tests/active_web_v1/{fake_browser.py,test_aw1_lifecycle.py}; docs/active_web_v1/aw1/{baseline_freeze.json,integrity.json,test_results.json,manifest.json,resultados.md}.

Arquitectura, AW0/closure y demás evidencia histórica intactas; tracked drift inesperado=0; tags/index sin cambios. No dependencias, workflows, herramientas browser, modelos, engine/broker, UI, grants, stores ni prompts nuevos/modificados.

No contradicción material ni OPEN DECISION necesaria para este gate. Las fases posteriores mantienen sus obligaciones: AW2 observation/refs; AW3 Policy/approvals/outcomes; AW4 red; AW5 engine; AW6 auth/transfers; AW7 integration/audit/frontends; AW8 certificación. No se implementan.

`AW1 = PASS`, limitado a dominio/lifecycle fake. Sin READY, commit, push, tag ni release. **Detención para revisión humana; AW2 no iniciado.**

