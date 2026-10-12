<h1 align="center">Nova</h1>

<p align="center">
  <strong>Local-first AI coding assistant. Desktop and CLI, one backend, explicit execution boundaries.</strong>
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
  <a href="#active-web-v12">Active Web</a> &nbsp;·&nbsp;
  <a href="#security-and-limits">Security</a> &nbsp;·&nbsp;
  <a href="#documentation">Documentation</a> &nbsp;·&nbsp;
  <a href="#development-and-tests">Development &amp; CI</a>
</p>

---

## What is Nova?

Nova is a local-first AI assistant for working with code, files, projects, documents, memory, and controlled web capabilities. Describe a task in natural language and Nova can inspect a codebase, search files, propose edits, run approved tools, retrieve scoped evidence, and work through the actual results with you.

[Ollama](https://ollama.com) is the primary local model runtime. The local workflow does not require a cloud inference API or subscription. Other provider adapters are available, but using a remote provider changes where inference happens; **local-first does not mean every operation is offline**.

Desktop is the main interface. The CLI and JSONL/backend paths use the same Application services and authority model rather than separate agent implementations.

Nova builds on Local CLI. The Python package, module, and executable still use `local-cli` / `local_cli` for compatibility; there is no `nova` command to substitute in the examples below.

---

## Features

- **Work with real project tools.** Read, write, edit, glob, grep, inspect project files, and run host-shell commands through Nova's tool/runtime layer.
- **Separate model intent from execution authority.** The model proposes actions; Application services validate scope and policy, request approval when required, issue bounded grants, and return actual tool results.
- **Use one backend across interfaces.** Desktop, CLI, and JSONL/backend paths share the same session, policy, approval, tool, capability, and persistence services.
- **Carry relevant memory between sessions.** MEMORY Core stores scoped preferences and facts locally, retrieves them through exact/lexical search, and supports explicit correction and forgetting. Retrieved memory is bounded context, not execution authority.
- **Use documents as scoped evidence.** Knowledge Inputs imports local documents and public URL snapshots into explicit session/workspace scopes, retrieves exact/lexical evidence, and carries source/revision/locator provenance into bounded context and citations.
- **Use the web through two explicit capabilities.** Controlled Fetch performs tightly bounded public HTTP(S) retrieval; Interactive Browser uses WebView2 for real browser interaction under a different, explicitly weaker network threat model.
- **Support local models.** A deterministic harness helps recover malformed tool calls, detect repetition, and manage context. It does not guarantee that a model will complete every task correctly.
- **Add project context when needed.** Optional RAG provides project retrieval. It is separate from long-term conversational memory and Knowledge Inputs.
- **Track work and delegate within scope.** Task lists, user questions, and capability-gated subagents use the same execution and authority rules. Subagents do not inherit browser authority by default.
- **Keep Git optional for ordinary use.** Conversation, native shell execution, and supported file tools do not require Git or Git Bash.
- **Keep outcomes honest.** Session lifecycle, cancellation, remote-effect states, audit records, and uncertainty barriers are designed to avoid reporting ambiguous effects as success.

The current Core V1 scope has one main active agent session. Multiple concurrent main chats, voice, and external connectors are not part of this stage. Persistent MEMORY, documentary Knowledge, the conversation transcript, Active Web, and legacy project RAG remain separate domains with separate authority and data contracts.

---

## Project status

Repository version: **0.12.6**.

Nova Core V1 is implemented. The currently closed READY stages are **SECURITY V1.2**, **MEMORY Core V1**, **Knowledge Inputs Core V1**, and **Active Web V1.2** within their published scope.

```text
MEMORY_CORE = READY
SEMANTIC_PROFILE = NOT_CERTIFIED

KNOWLEDGE_CORE = READY
NOVA_KNOWLEDGE_INPUTS_V1_READY
DOCUMENT_SEMANTIC_PROFILE = NOT_CERTIFIED
OCR_PROFILE = NOT_CERTIFIED

ACTIVE_WEB_V1_2_FINAL = PASS
ACTIVE_WEB_V1_2 = READY
READY_FOR_HUMAN_RELEASE_DECISION = true
RELEASE_APPROVED = false
```

`ACTIVE_WEB_CORE = NOT_READY` is intentionally preserved as the historical V1/V1.1 aggregate. It is **not** the readiness switch for Active Web V1.2. Historical `AW8=BLOCKED` and the V1.1 Block06 architectural limit also remain frozen as historical evidence.

The validated product/security scope remains centered on **Windows 11 + local NTFS + `HOST_UNISOLATED`**. Linux and macOS are not certified by the host-real evaluations described here. These READY states are scoped engineering gates, not external security certifications and not guarantees about future code changes.

### Memory

MEMORY Core covers local persistence, subject/workspace scopes, correction/supersession, forgetting with no-resurrection, conflicts/temporal handling, secret/sensitivity policy, and bounded MemoryCapsules. Real local-model E2E was validated at 4K/8K/16K on the published model and host. Advanced 32K/64K budgeting contracts are tested; real LLM inference at those sizes is not certified. Semantic and cross-language recall are not certified, and embeddings are not required for exact/lexical memory.

The historical single-turn `qwen2.5:7b` failure remains recorded as a non-blocking model-behavior limitation. A passing gate does not mean every prompt or model behaves reliably.

### Knowledge Inputs

Knowledge Core covers explicit source/revision lifecycle, session/workspace isolation, local document acquisition and extraction, public URL snapshots, exact/FTS retrieval without embeddings, bounded coexistence with Memory, and structurally validated citations. Supported acquisition paths include TXT/Markdown/code, JSON/CSV, HTML, textual PDF, and DOCX.

Active Web is a separate capability family: Knowledge treats admitted documents and snapshots as evidence; it does not inherit browser authority, web grants, cookies, sessions, or mutation permission. Structural citation validity also does not guarantee that a model's claim is true or entailed by a source.

The [Knowledge READY closure](docs/knowledge_inputs_v1/ready_closure/CIERRE_FINAL_KNOWLEDGE_INPUTS_V1_READY.md) records **40 SATISFIED / 0 NOT_EVIDENCED / 0 BLOCKED** against the normative READY criteria. Historical scorer/campaign results remain frozen rather than being relabeled:

```text
K8 PARTIAL — FINAL CERTIFICATION RESULT: 13/14
K8 POST-CERT REMEDIATION PARTIAL
4K historical quality = 10/15
KNOWLEDGE CONTEXT CAPABILITY RESOLUTION V1 PASS
K8 CERTIFICATION V2 FAIL
SOURCE_CONFLICT_FOCAL_E2E = FAIL
SOURCE_CONFLICT_FOCAL_R2_E2E = FAIL
```

Knowledge works within the existing shared retrieval budget; 4K does not guarantee complete simultaneous multi-source admission. The accepted supplemental 8K operational profile demonstrates complete comparison of up to three evidence units under its evaluated conditions, not arbitrary source capacity or a universal minimum context window.

### Active Web V1.2

Active Web V1.2 is fully certified for its current product scope and is split into two independent capabilities:

| Capability | Certified scope | Important limit |
|---|---|---|
| **Controlled Fetch** | `GET` / `HEAD`, HTTP/1.1, `TEXT`, `HTML_STATIC`, `JSON`; `networkEgressControl=ENFORCED`; `publicOnly=ENFORCED` under evidence profile `CF_B2_GET_HEAD_HTTP11_WINDOWS_V1` | No POST, auth, binary download, cookies, browser rendering, or browser-session import |
| **Interactive Browser** | WebView2; structured observations; opaque refs; exact Policy/Approval/Grant authority; guarded mutations; upload/download staging; human takeover; known-value secret boundary; external-protocol deny guard | `networkIsolation=NOT_PROVIDED`; `controlClass=HOST_UNISOLATED`; not a hostile-site network sandbox |

The final V1.2 E2E candidate passed its closing certification and is `READY`, but no release has been approved by this repository state. Product capability availability is derived from compatible host/runtime/configuration evidence and human configuration, not from model output or page content.

> Nova does not provide a general OS sandbox or process isolation. Commands and browser processes run with the permissions of your account. Review proposed actions and verify their results.

---

## Quick Start

### Requirements

For the currently validated workflow:

- Windows 11 and a project on a supported local NTFS filesystem.
- Python 3.10 or newer, as declared in the package metadata.
- Ollama running locally, with a model already installed that can handle tool use and fits your available resources.
- Node.js and npm if you want to develop or run Desktop from source; the current Desktop CI contract uses Node **24.19.0**.
- WebView2 Runtime on Windows for Interactive Browser support. Availability is still derived by Nova's compatibility checks rather than assumed from nominal installation alone.

The base Python installation includes **`pypdf==6.19.0`** for real textual PDF extraction. MEMORY Core uses the standard-library SQLite/FTS adapter. The optional `memory-semantic` extra adds NumPy for vector contracts and infrastructure, not a certified Semantic Profile. Document semantic retrieval and OCR are optional, uncertified profiles; Nova does not automatically download their models.

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

Active Web V1.2 uses the same Application/backend from Desktop. Controlled Fetch and Interactive Browser expose separate capability states. Interactive Browser requires the product's human-controlled enablement/risk acknowledgement and retains normal per-action Policy/Approval/Grant checks; acknowledging browser risk does not authorize remote mutations or transfers.

---

## Active Web V1.2

Nova intentionally separates passive web retrieval from full browser interaction.

### Controlled Fetch

Controlled Fetch is the default route for ordinary public information retrieval. Its certified profile is intentionally small:

```text
GET / HEAD
HTTP/1.1
TEXT / HTML_STATIC / JSON
networkEgressControl = ENFORCED
publicOnly = ENFORCED
```

The capability canonicalizes destinations, validates every DNS answer, pins an admitted numeric endpoint, revalidates redirects, enforces bounded responses and deadlines, and does not use browser cookies or ambient authentication. Private, loopback, link-local, special, mixed-DNS, and otherwise non-admitted destinations fail closed under the certified profile.

Controlled Fetch does **not** currently certify POST, authentication, binary downloads, cookies, OAuth flows, JavaScript rendering, or browser emulation.

### Interactive Browser

Interactive Browser uses the existing WebView2 host for real page interaction. It provides structured observations and opaque element references rather than model-supplied selectors or arbitrary JavaScript. Agentic actions remain subject to exact Policy/Approval/Grant bindings, freshness/epoch checks, bounded lifecycle, and truthful remote-effect outcomes.

Interactive Browser also recertifies browser uploads/downloads, owned staging, human takeover, known-value secret redaction/continuity, and `ExternalProtocolGuard = DENY_ALL` at Nova's host boundary.

Its network claim is deliberately different:

```text
networkIsolation = NOT_PROVIDED
controlClass = HOST_UNISOLATED
```

Nova does not claim to mediate every WebView2 socket, globally disable WebRTC/Service Workers, or turn the browser into a hostile-site network sandbox.

### Routing and no-bypass rule

Ordinary public research prefers Controlled Fetch. Interactive Browser is selected only when a host-validated task genuinely requires rendering or interaction.

A Controlled Fetch denial does **not** automatically escalate to Interactive Browser. Private destinations, mixed/private DNS, prohibited redirects or schemes, and policy/scope denials remain denials for that objective. Likewise, a page telling the model to "use the browser" does not create browser authority.

---

## Security and Limits

Nova separates consent, policy, and mediated tool access from the permissions of the operating system:

- **Processes are `HOST_UNISOLATED`.** Shell commands, browser processes, and their descendants use normal account permissions. A workspace, approval, or logical grant is not a physical filesystem or network boundary.
- **Approvals are exact and one-shot where required.** Model output, page text, retrieved documents, memory, and ordinary chat replies cannot grant execution authority. An existing Grant does not turn Policy `DENY` into `ALLOW`.
- **Direct file tools are broker-mediated.** `read`, `write`, `edit`, `glob`, and `grep` enforce their supported local NTFS contract and deny unsupported paths or aliases. This does not mediate file access performed inside shell commands.
- **Controlled Fetch has a scoped public-only network contract.** Under its certified GET/HEAD profile, its own HTTP(S) data connections use public-destination admission, all-answer DNS validation, numeric pinning, redirect revalidation, TLS validation, and bounded I/O. This is not a firewall for shell, Git, providers, the browser engine, or the entire OS.
- **Interactive Browser does not claim network isolation.** WebView2 is used for interaction under `HOST_UNISOLATED`; Nova mediates its own authority, actions, transfers, secret projection, and external-protocol boundary, but does not claim exhaustive control of browser-internal networking.
- **Mutations preserve uncertainty.** Once an effect may have started, timeout, crash, or IPC loss does not become "no effect" by assumption. Ambiguous outcomes remain `UNKNOWN`/`PARTIAL` as appropriate and are not automatically retried.
- **Takeover does not bypass authority.** Human takeover pauses agentic browser actions. Returning from takeover invalidates stale refs/epochs and requires the configured continuity checks before Nova resumes.
- **Secret protection is scoped, not universal DLP.** Nova protects declared-sensitive/known values from its public projections within the certified boundary. It does not guarantee detection of arbitrary transformed secrets, secure erase, or protection from a website to which the human deliberately sends data.
- **Memory remains untrusted data.** Memories cannot issue grants or override system/security instructions. Forgetting removes Nova-owned memory and invalidates its retrieval, not source conversations, audit records, external logs, or backups.
- **Knowledge remains evidence, not authority.** Document instructions cannot grant tool/security permissions or write Memory automatically. Citation validation confirms admitted provenance, not truth or entailment.

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
| [Active Web V1.2 architecture approval](docs/active_web_v1_2/v12_b0_architecture_threat_model/resultados.md) | Approved split between Controlled Fetch and Interactive Browser, threat model, WebView2 decision, and roadmap. |
| [Active Web V1.2 final E2E](docs/active_web_v1_2/v12_b7_final_e2e/resultados.md) | Final integrated certification, candidate scope, product-root parity, failure semantics, cleanup, and preserved historical limits. |
| [Product limits](docs/security_v12/s8_limits.md) | What is enforced on each surface—and what is not. |
| [Security READY evaluation](docs/security_v12/nova_security_v12_ready.md) · [Manifest](docs/security_v12/nova_security_v12_ready_manifest.json) | Security scope, evidence, historical failures, and traceability. |
| [Memory READY evaluation](docs/memory_v1/memory_v1_ready_resultados.md) · [Manifest](docs/memory_v1/memory_v1_ready_manifest.json) | MEMORY Core certification, Semantic Profile limitations, and M0-M8 evidence. |
| [Knowledge READY closure](docs/knowledge_inputs_v1/ready_closure/CIERRE_FINAL_KNOWLEDGE_INPUTS_V1_READY.md) · [Manifest](docs/knowledge_inputs_v1/ready_closure/manifest.json) · [Final matrix](docs/knowledge_inputs_v1/ready_closure/ready_criteria_matrix_final.json) | The 40 READY criteria, accepted evidence, limits, and unchanged historical results. |
| [Source-conflict normative resolution](docs/knowledge_inputs_v1/ready_closure/RESOLUCION_NORMATIVA_CRITERIOS_35_Y_1.md) | Why raw E2E evidence satisfies criteria 35/1 without rescoring either focal FAIL. |
| [Current CI contracts](ci/README.md) · [Positive selection manifest](ci/pytest_contracts.json) | Per-function classification, job/platform responsibilities, and the distinction from historical certification artifacts. |

The detailed architecture and validation documents are currently written primarily in Spanish.

---

## Development and Tests

The repository keeps ordinary regression CI separate from historical/final certification evidence. A green workflow means the selected current regression contract passed on that runner; it does **not** automatically recertify a frozen host-real evidence profile such as the final Active Web V1.2 candidate.

At the time of this README update, the checked-in GitHub Actions organization includes the existing Core/Security, Memory, and Knowledge/Desktop workflows. The pre-commit CI inventory should remain the source of truth for which current contracts run on push/PR and which host-special/native checks remain manual or evidence-only.

| Workflow | Ordinary responsibility |
|---|---|
| [Nova Core V1 contracts](.github/workflows/nova_core_v1.yml) | Current Core and Security regression contracts, with platform-specific selection. |
| [Nova Memory V1 contracts](.github/workflows/nova_memory_v1.yml) | Current Memory regression contracts. |
| [Nova Knowledge V1 and Desktop contracts](.github/workflows/nova_knowledge_v1.yml) | Current Knowledge contracts and Desktop checks. |

Python CI uses the repository's positive-selection inventory rather than a blanket `pytest tests` command. The [positive selection manifest](ci/pytest_contracts.json) classifies pytest functions by current CI responsibility, local-evidence-only status, historical certification status, or special-infrastructure requirements. Static inventory validation should reject newly unclassified current contracts rather than silently skipping them.

For local contract validation, use Python 3.14 and a **new output directory outside every Git workspace**. From the checkout root:

```powershell
python -m pip install -e ".[memory-semantic]" pytest pytest-subtests
python -B ci/contract_inventory.py
$contractRun = Join-Path (Resolve-Path ..).Path ("nova-contracts-" + [guid]::NewGuid().ToString("N"))
python -B ci/run_contracts.py --job knowledge --collect-only --output $contractRun
```

This example checks collection only. To execute an ordinary current regression job, omit `--collect-only` and use another fresh external output directory. Consult [ci/README.md](ci/README.md) for the currently supported job names and platform requirements after any CI refresh.

Desktop checks should use the scripts declared by `desktop/package.json`. The current Desktop contract includes dependency installation, test execution, and TypeScript checking; ordinary CI does not imply Electron GUI E2E, installer certification, packaging, or release publication unless a workflow explicitly says so.

Active Web V1.2 has additional Windows/WebView2 host-real evidence under `docs/active_web_v1_2/`. Ordinary CI should preserve representative regression coverage without pretending to recreate the exact frozen B7 certification candidate on an arbitrary runner. Missing prerequisites for a job that promises to execute must fail explicitly rather than producing a misleading green run through silent skips.

Historical Memory, Knowledge, Security, and Active Web campaign artifacts remain preserved for traceability; they do not define today's ordinary regression selection and must not be rewritten to make a badge green.

The workflow selections live in [.github/workflows](.github/workflows). Desktop checks live under [desktop/tests](desktop/tests), and Python tests under [tests](tests).

When contributing, keep execution decisions in Application, preserve the shared CLI/Desktop backend, and include tests for the behavior you change. New platforms, capabilities, or stronger security claims require their own validation rather than being inferred from existing READY states.

---

## License

MIT. See [LICENSE](LICENSE) for the license text.
