<h1 align="center">Nova</h1>

<p align="center">
  <strong>Local-first AI coding assistant. Desktop and CLI, powered by one backend.</strong>
</p>

<p align="center">
  <a href="#what-is-nova">Overview</a> &nbsp;·&nbsp;
  <a href="#features">Features</a> &nbsp;·&nbsp;
  <a href="#quick-start">Quick Start</a> &nbsp;·&nbsp;
  <a href="#desktop-app">Desktop App</a> &nbsp;·&nbsp;
  <a href="#security-and-limits">Security</a> &nbsp;·&nbsp;
  <a href="#documentation">Documentation</a>
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
- **Support local models.** A deterministic harness helps recover malformed tool calls, detect repetition, and manage context. It does not guarantee that a model will complete every task correctly.
- **Add project context when needed.** Optional RAG provides project retrieval. It is not long-term conversational memory, and its absence does not prevent normal chat.
- **Track work and delegate within scope.** Task lists, user questions, and capability-gated subagents use the same execution and authority rules.
- **Keep Git optional.** Conversation, native shell execution, and supported file tools do not require Git or Git Bash.
- **Make lifecycle observable.** Session persistence, operation status, cancellation reporting, and a local security audit support diagnosis without presenting uncertain effects as success.

The current Core V1 scope has one main active agent session. Multiple chats, voice, external connectors, and long-term conversational memory are not part of this stage.

---

## Project status

At the latest evaluated baseline, Nova Core V1 is implemented and the **SECURITY V1.2 product gate is closed**: `NOVA_SECURITY_V1_2_READY = true`.

The validated scope is **Windows 11 + local NTFS + `HOST_UNISOLATED`**. Linux and macOS are **not certified** by this evaluation. This is a scoped product-quality gate, not an external security certification or a guarantee about future changes.

The historical single-turn `qwen2.5:7b` failure remains recorded as a non-blocking model-behavior limitation. A passing gate does not mean every prompt or model behaves reliably. See the [READY evaluation](docs/security_v12/nova_security_v12_ready.md) for the exact evidence and limitations.

> Nova does not provide a sandbox or process isolation. Commands run with your account's normal permissions. Review proposed actions and verify their results.

---

## Quick Start

### Requirements

For the currently validated workflow:

- Windows 11 and a project on a supported local NTFS filesystem.
- Python 3.10 or newer, as declared in the package metadata.
- Ollama running locally, with a model already installed that can handle tool use and fits your available resources.
- Node.js and npm if you want to develop or run Desktop from source.

The Python package has no third-party runtime dependencies. Ollama is still a required runtime for local inference; Desktop has its own dependencies.

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

Output limits, timeouts, and concurrency limits are operational controls—not OS quotas or isolation. See [product limits](docs/security_v12/s8_limits.md) for the full, surface-specific contract.

---

## Documentation

This README is the project entry point. Detailed architecture, decisions, and validation evidence stay in their own documents.

| Document | What it covers |
|---|---|
| [Nova Core V1](docs/architecture/NOVA_CORE_ARQUITECTURA_V1.md) | Backend boundaries, session lifecycle, providers, tools, and shared interfaces. |
| [SECURITY V1.2](docs/architecture/NOVA_SECURITY_ARQUITECTURA_V1_2.md) | Security contracts, implementation stages, and the normative gate. |
| [Product limits](docs/security_v12/s8_limits.md) | What is enforced on each surface—and what is not. |
| [READY evaluation](docs/security_v12/nova_security_v12_ready.md) · [Manifest](docs/security_v12/nova_security_v12_ready_manifest.json) | Validated scope, evidence, historical failures, and traceability. |

The detailed architecture and validation documents are currently written in Spanish.

---

## Development and Tests

The Python regression suite uses pytest:

```powershell
python -m pytest tests/ -q
```

Install pytest in your development environment before running it. Desktop checks live under [desktop/tests](desktop/tests), and Python tests under [tests](tests).

Host-real and local-model E2E checks have separate prerequisites and evidence. A default regression run alone is not proof that the full SECURITY gate passes; consult the READY evaluation for the distinction between unit, contract, integration, and host-real results.

When contributing, keep execution decisions in Application, preserve the shared CLI/Desktop backend, and include tests for the behavior you change. New platforms or security claims need their own validation.

---

## License

MIT, as declared in [pyproject.toml](pyproject.toml).
