<h1 align="center">Nova</h1>

<p align="center">
  <strong>Local-first AI coding assistant. Desktop and CLI, powered by one backend.</strong>
</p>

<p align="center">
  <a href="https://github.com/j-hernandez-dev/nova-assistant/actions/workflows/nova_core_v1.yml"><img src="https://github.com/j-hernandez-dev/nova-assistant/actions/workflows/nova_core_v1.yml/badge.svg?branch=main" alt="Nova Core and Security contracts"></a>
  <a href="https://github.com/j-hernandez-dev/nova-assistant/actions/workflows/nova_memory_v1.yml"><img src="https://github.com/j-hernandez-dev/nova-assistant/actions/workflows/nova_memory_v1.yml/badge.svg?branch=main" alt="Nova Memory contracts"></a>
  <a href="https://github.com/j-hernandez-dev/nova-assistant/actions/workflows/nova_knowledge_v1.yml"><img src="https://github.com/j-hernandez-dev/nova-assistant/actions/workflows/nova_knowledge_v1.yml/badge.svg?branch=main" alt="Nova Knowledge and Desktop contracts"></a>
</p>

<p align="center">
  <a href="#what-is-nova">Overview</a> &nbsp;·&nbsp;
  <a href="#features">Features</a> &nbsp;·&nbsp;
  <a href="#project-status">Status</a> &nbsp;·&nbsp;
  <a href="#quick-start">Quick Start</a> &nbsp;·&nbsp;
  <a href="#desktop-app">Desktop App</a> &nbsp;·&nbsp;
  <a href="#security-and-limits">Security</a> &nbsp;·&nbsp;
  <a href="#documentation">Documentation</a> &nbsp;·&nbsp;
  <a href="#development-and-tests">Development &amp; CI</a>
</p>

---

## What is Nova?

Nova is an AI assistant for working with code and local projects. Describe a task in natural language, and it can inspect files, search a codebase, propose changes, run commands, and work through tool results with you.

[Ollama](https://ollama.com) is the primary local model runtime. The local workflow does not require a cloud API or subscription. Other provider adapters are available, but using a remote provider changes where inference happens; local-first does not mean every operation is offline.

Desktop is the main interface. The CLI is a supported technical interface to the same Nova Core backend—not a separate agent implementation.

Nova builds on Local CLI. The Python package, module, and executable still use `local-cli` / `local_cli` for compatibility; there is no `nova` command to substitute in the examples below.

---

## Features

- **Work with real project tools.** Read, write, and edit files; search paths and contents; run host-shell commands; and fetch public web pages.
- **Keep the model and execution separate.** The model proposes tool calls. Application services evaluate policy, request approval when needed, and return actual tool results.
- **Use one backend across interfaces.** Desktop and CLI use the same Application services for session management, model selection, tool execution, approvals, and persistence.
- **Carry relevant memory between sessions.** MEMORY Core stores scoped preferences and facts locally, retrieves them through exact/lexical search, and supports explicit correction and forgetting. Retrieved memory is bounded context, not execution authority.
- **Use documents as scoped evidence.** Knowledge Inputs imports local documents and public URL snapshots into explicit session/workspace scopes, retrieves exact/lexical evidence, and carries source/revision/locator provenance into bounded context and citations. Documents do not become user assertions, execution authority, or automatic Memory writes.
- **Support local models.** A deterministic harness helps recover malformed tool calls, detect repetition, and manage context. It does not guarantee that a model will complete every task correctly.
- **Add project context when needed.** Optional RAG provides project retrieval. It is not long-term conversational memory, and its absence does not prevent normal chat.
- **Track work and delegate within scope.** Task lists, user questions, and capability-gated subagents use the same execution and authority rules.
- **Keep Git optional.** Conversation, native shell execution, and supported file tools do not require Git or Git Bash.
- **Make lifecycle observable.** Session persistence, operation status, cancellation reporting, and a local security audit support diagnosis without presenting uncertain effects as success.

The current Core V1 scope has one main active agent session. Multiple concurrent main chats, voice, and external connectors are not part of this stage. Persistent MEMORY, documentary Knowledge, the conversation transcript, and legacy project RAG remain separate domains.

---

## Project status

Repository version: **0.12.6**. Nova Core V1 is implemented; **SECURITY V1.2**, **MEMORY Core V1**, and **Knowledge Inputs Core V1** are **READY** within their published scope.

```text
MEMORY_CORE=READY
SEMANTIC_PROFILE=NOT_CERTIFIED
KNOWLEDGE_CORE=READY
NOVA_KNOWLEDGE_INPUTS_V1_READY
DOCUMENT_SEMANTIC_PROFILE=NOT_CERTIFIED
OCR_PROFILE=NOT_CERTIFIED
```

The validated scope is **Windows 11 + local NTFS + `HOST_UNISOLATED`**. Linux and macOS are **not certified** by this evaluation. This is a scoped product-quality gate, not an external security certification or a guarantee about future changes.

MEMORY Core covers local persistence, subject/workspace scopes, correction/supersession, forgetting with no-resurrection, conflicts/temporal handling, secret/sensitivity policy, and bounded MemoryCapsules. Real local-model E2E was validated at 4K/8K/16K on the published model and host. Advanced 32K/64K budgeting contracts are tested; real LLM inference at those sizes is not certified. Semantic and cross-language recall are not certified, and embeddings are not required for exact/lexical memory.

The historical single-turn `qwen2.5:7b` failure remains recorded as a non-blocking model-behavior limitation. A passing gate does not mean every prompt or model behaves reliably. See the [Security READY evaluation](docs/security_v12/nova_security_v12_ready.md) and [Memory READY evaluation](docs/memory_v1/memory_v1_ready_resultados.md) for the evidence and limitations. CI regression on Linux/macOS does not extend the certified host-real scope.

Knowledge Core covers explicit source/revision lifecycle, session/workspace isolation, local document acquisition and extraction, public URL snapshots, exact/FTS retrieval without embeddings, bounded coexistence with Memory, and structurally validated citations. Supported acquisition paths include TXT/Markdown/code, JSON/CSV, HTML, textual PDF, and DOCX. Passive web search is capability-gated; Active Web and browser automation remain outside this scope. Structural citation validity does not guarantee that a model's claim is true or entailed by a source.

The [Knowledge READY closure](docs/knowledge_inputs_v1/ready_closure/CIERRE_FINAL_KNOWLEDGE_INPUTS_V1_READY.md) records **40 SATISFIED / 0 NOT_EVIDENCED / 0 BLOCKED** against the normative READY criteria in architecture §64. It reuses accepted evidence and an additive normative resolution of the raw source-conflict Turn; it does **not** relabel frozen scorer or campaign results. These historical results remain unchanged:

```text
K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14
K8 POST-CERT REMEDIATION PARTIAL
4K historical quality = 10/15
KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS
K8 CERTIFICATION V2 FAIL
SOURCE_CONFLICT_FOCAL_E2E = FAIL
SOURCE_CONFLICT_FOCAL_R2_E2E = FAIL
```

Knowledge works within the existing shared retrieval budget; 4K does not guarantee complete simultaneous multi-source admission. The accepted supplemental 8K operational profile demonstrates complete comparison of up to three evidence units under its evaluated conditions, not arbitrary source capacity or a universal minimum context window. See [Knowledge Context Capability Resolution V1](docs/architecture/NOVA_KNOWLEDGE_CONTEXT_CAPABILITY_RESOLUTION_V1.md).

> Nova does not provide a sandbox or process isolation. Commands run with your account's normal permissions. Review proposed actions and verify their results.

---

## Quick Start

### Requirements

For the currently validated workflow:

- Windows 11 and a project on a supported local NTFS filesystem.
- Python 3.10 or newer, as declared in the package metadata.
- Ollama running locally, with a model already installed that can handle tool use and fits your available resources.
- Node.js and npm if you want to develop or run Desktop from source; ordinary Desktop CI uses Node **24.19.0**.

The base Python installation includes **`pypdf==6.19.0`** for real textual PDF extraction. MEMORY Core uses the standard-library SQLite/FTS adapter. The optional `memory-semantic` extra adds NumPy for vector contracts and infrastructure, not a certified Semantic Profile. Document semantic retrieval and OCR are optional, uncertified profiles; Nova does not automatically download their models. Ollama is still a required runtime for local inference; Desktop has its own dependencies.

### Get the source

```powershell
git clone https://github.com/j-hernandez-dev/nova-assistant.git
cd nova-assistant
```

Git is needed for this clone command, not for normal chat. You can also work from an existing checkout.

### Run the CLI

From the root of your checkout, using your chosen Python environment:

```powershell
python -m pip install -e .
python -m local_cli --select-model
```

The model selector lets you choose an installed Ollama model rather than relying on the configured default.

The editable installation also provides the `local-cli` command. Start it from the project directory you want to work in:

```powershell
Set-Location "C:\path\to\your\project"
local-cli --select-model
```

If the executable is not on `PATH`, use `python -m local_cli --select-model` with the same Python environment.

Start with a small task, such as:

```text
Read the project README and explain how the application is organized.
Do not modify any files yet.
```

Review file changes and command results before relying on them. Natural-language instructions are not a substitute for execution policy.

### Useful commands

| Command | Purpose |
|---|---|
| `/help` | Show the available interactive commands. |
| `/status` | Inspect the current model and session status. |
| `/models` | Open the model selector. |
| `/model <name>` | Request a model change between turns. |
| `/memory help` | Show memory inspection, remember, correct, forget, and proposal commands. |
| `/exit` | Leave the CLI. |

Use `python -m local_cli --help` for startup options. Model and provider changes are rejected while a main turn is active; they do not silently interrupt ongoing work.

### Configuration

Configuration precedence is **CLI arguments → environment variables → config file → defaults**.

Common settings include `--model`, `LOCAL_CLI_MODEL`, and `OLLAMA_HOST`. The default config file is `~/.config/nova/config`. The supported settings and defaults live in [local_cli/config.py](local_cli/config.py).

---

## Desktop App

Desktop uses Electron, React, and Vite. Its host starts the Python backend; the renderer presents state and interactions rather than running its own agent loop.

Complete the Python setup above, keep Ollama running, and make sure `python` is available on your Windows `PATH`. From the repository root:

```powershell
cd desktop
npm ci
npm run dev
```

This starts the local development app. These instructions do not imply a published installer, a packaged release, or validation on additional operating systems.

---

## Security and Limits

Nova separates consent, policy, and mediated tool access from the permissions of the operating system:

- **Processes are `HOST_UNISOLATED`.** Shell commands and their descendants use normal account permissions. A workspace, approval, or logical grant is not a physical filesystem or network boundary.
- **Approvals are exact and one-shot.** Model output, retrieved text, and ordinary chat replies cannot grant execution authority. `--yes` does not bypass required human approval or turn a denial into permission.
- **Direct file tools are broker-mediated.** `read`, `write`, `edit`, `glob`, and `grep` enforce their supported local NTFS contract and deny unsupported paths or aliases. This does not mediate file access performed inside shell commands.
- **`web_fetch` has a separate public-only contract.** It allows public HTTP(S) destinations and revalidates DNS and redirects. Private, loopback, link-local, special destinations, and `file://` are denied. This is not a firewall for shell, Git, or provider traffic.
- **Environment handling and audit have explicit limits.** Nova filters deliberate environment inheritance and redacts known secrets. Audit is local and durable, but not tamper-proof against the host account or a record of every effect inside a shell process.
- **Cancellation is best-effort.** Requesting cancellation does not prove termination or rollback. Uncertain outcomes remain uncertain and are not automatically retried.
- **Memory remains untrusted data.** Memories cannot issue grants or override system/security instructions. Forgetting removes Nova-owned memory and invalidates its retrieval, not source conversations, security audit, external logs, or backups. It is not secure erase or universal encryption.
- **Knowledge remains evidence, not authority.** Document instructions cannot grant tool/security permissions or write Memory automatically. The citation registry validates IDs against actually admitted source/revision/chunk/locator evidence; it does not certify truth or entailment. Remote search and remote document forwarding require separate controls and consent.

Output limits, timeouts, and concurrency limits are operational controls—not OS quotas or isolation. See [product limits](docs/security_v12/s8_limits.md) for the full, surface-specific contract.

---

## Documentation

This README is the project entry point. Detailed architecture, decisions, and validation evidence stay in their own documents.

| Document | What it covers |
|---|---|
| [Nova Core V1](docs/architecture/NOVA_CORE_ARQUITECTURA_V1.md) | Backend boundaries, session lifecycle, providers, tools, and shared interfaces. |
| [SECURITY V1.2](docs/architecture/NOVA_SECURITY_ARQUITECTURA_V1_2.md) | Security contracts, implementation stages, and the normative gate. |
| [MEMORY V1](docs/architecture/NOVA_MEMORY_ARQUITECTURA_V1.md) | Memory identity/scope, persistence, policies, retrieval, budgeting, and profile gates. |
| [Knowledge Inputs V1](docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md) | Source/revision lifecycle, formats, scope, retrieval, context, citations, and the normative READY criteria. |
| [Knowledge Context Capability Resolution V1](docs/architecture/NOVA_KNOWLEDGE_CONTEXT_CAPABILITY_RESOLUTION_V1.md) | Distinct 4K limitations and the supplemental 8K operational profile. |
| [Product limits](docs/security_v12/s8_limits.md) | What is enforced on each surface—and what is not. |
| [Security READY evaluation](docs/security_v12/nova_security_v12_ready.md) · [Manifest](docs/security_v12/nova_security_v12_ready_manifest.json) | Security scope, evidence, historical failures, and traceability. |
| [Memory READY evaluation](docs/memory_v1/memory_v1_ready_resultados.md) · [Manifest](docs/memory_v1/memory_v1_ready_manifest.json) | MEMORY Core certification, Semantic Profile limitations, and M0-M8 evidence. |
| [Knowledge READY closure](docs/knowledge_inputs_v1/ready_closure/CIERRE_FINAL_KNOWLEDGE_INPUTS_V1_READY.md) · [Manifest](docs/knowledge_inputs_v1/ready_closure/manifest.json) · [Final matrix](docs/knowledge_inputs_v1/ready_closure/ready_criteria_matrix_final.json) | The 40 READY criteria, accepted evidence, limits, and unchanged historical results. |
| [Source-conflict normative resolution](docs/knowledge_inputs_v1/ready_closure/RESOLUCION_NORMATIVA_CRITERIOS_35_Y_1.md) | Why raw E2E evidence satisfies criteria 35/1 without rescoring either focal FAIL. |
| [External evidence index](docs/knowledge_inputs_v1/git_closure/revision_02/bundle_manifest.json) · [Archive receipt](docs/knowledge_inputs_v1/git_closure/revision_02/bundle_receipt.json) | SHA-indexed raw archive prepared outside Git; original files preserved, publication separate from ordinary CI. |
| [Current CI contracts](ci/README.md) · [Positive selection manifest](ci/pytest_contracts.json) | Per-function classification, job/platform responsibilities, and the distinction from historical certification artifacts. |

The detailed architecture and validation documents are currently written in Spanish.

---

## Development and Tests

GitHub Actions uses three workflows with explicit current-regression responsibilities:

| Workflow | Ordinary jobs | Scope |
|---|---|---|
| [Nova Core V1 contracts](.github/workflows/nova_core_v1.yml) | `core-contracts`, `security-contracts` | Windows, Ubuntu, macOS; platform-specific contracts are positively assigned to their supported hosts. |
| [Nova Memory V1 contracts](.github/workflows/nova_memory_v1.yml) | `memory-contracts` | Current Memory contracts on all three hosts; NumPy enables synthetic vectors, not model inference. |
| [Nova Knowledge V1 and Desktop contracts](.github/workflows/nova_knowledge_v1.yml) | `knowledge-contracts`, `desktop-contracts` | Windows Knowledge contracts; seven ordinary Desktop suites plus TypeScript checking. |

The Core workflow also provides `security-native-manual`, an explicit Windows/NTFS host job enabled only through manual dispatch with `native_security=true`. It is separate from ordinary push/PR regression and does not launch a model campaign.

Python CI uses **3.14**. Desktop CI uses **Node 24.19.0**, runs `npm ci`, and executes `application_client`, `approval_host`, `security_audit`, `memory_control`, `memory_maintenance`, `knowledge_control`, and `knowledge_k7` `.test.cjs` suites with `--experimental-transform-types`, followed by `npx --no-install tsc --noEmit`. It does not run Electron GUI E2E, packaging, or publishing.

The [positive selection manifest](ci/pytest_contracts.json) classifies each pytest contract by function/node-id as `CURRENT_PORTABLE_CI`, `CURRENT_LOCAL_EVIDENCE_ONLY`, `HISTORICAL_CERTIFICATION_ARTIFACT`, or `SPECIAL_INFRASTRUCTURE_ONLY`, with reasons and evidence/infrastructure references. Mixed files retain their portable functions, and all parameter instances of a selected function run. Static validation rejects new unclassified contracts; collection verifies the declared scope before fixture setup. This is not a blanket `pytest tests` invocation followed by additional ignores.

For local current-contract validation, use Python 3.14 and a **new output directory outside every Git workspace**. From the checkout root:

```powershell
python -m pip install -e ".[memory-semantic]" pytest pytest-subtests
python -B ci/contract_inventory.py
$contractRun = Join-Path (Resolve-Path ..).Path ("nova-contracts-" + [guid]::NewGuid().ToString("N"))
python -B ci/run_contracts.py --job knowledge --collect-only --output $contractRun
```

This example checks collection only: no test functions or fixtures execute. The sibling output path is rejected if it belongs to another Git working tree; choose a different external location in that case. To execute ordinary current regression, omit `--collect-only` and use another fresh output directory. The ordinary Python job choices are `core`, `security`, `memory`, and `knowledge`; Knowledge's declared CI platform is Windows. Process-local profile/config/state and pytest output remain under the private output directory; this is fixture isolation, not an OS sandbox.

Historical Memory runner modes and K8/SCF artifacts remain preserved for traceability; they do not define today's ordinary CI selection. Existing freezes, ledgers, scorer results, and certification evidence must not be rewritten to make regression or a badge green.

The workflow selections live in [.github/workflows](.github/workflows). Desktop checks live under [desktop/tests](desktop/tests), and Python tests under [tests](tests).

Ordinary CI does not require Ollama, a local model, historical machine/Temp paths, `AUTHORIZED`, quality ledgers, or external raw archives. It does not download the prepared evidence bundle or repeat READY certification, K8/SCF campaigns, or real-model quality measurements. Model/GUI/host-special evidence has separate prerequisites and authorization. Memory semantic, document semantic, and OCR profiles remain `NOT_CERTIFIED`; passing synthetic adapter contracts does not certify those profiles. Consult the READY evaluations for the distinction between unit, contract, integration, host-real, and real-model E2E results.

When contributing, keep execution decisions in Application, preserve the shared CLI/Desktop backend, and include tests for the behavior you change. New platforms or security claims need their own validation.

---

## License

MIT. See [LICENSE](LICENSE) for the license text.
