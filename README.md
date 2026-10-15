# Nova

A local AI assistant for files, code, commands and web browsing. Describe a task naturally: the model chooses tools, and the host checks permissions, requests approval when required and returns the actual result.

The current development focus is the Windows CLI. Desktop consumes the same Python Application backend. The package and command retain `local-cli` / `local_cli` for compatibility.

## Current scope

- Read, write, edit, list and search local files.
- Execute host terminal commands using the selected shell's real syntax.
- Navigate the browser, read rendered pages and interact through opaque element references.
- Search with the browser, open sources and summarize their actual content. No SearXNG server or API key is required.
- Use WebView2 by default; optionally select installed Chrome or Edge on Windows.
- Hand browser control to the human for login/CAPTCHA; approve exact uploads and retain completed downloads.
- Use optional HTTP `web_fetch`, independently controlled by `/fetch`.
- Retain conversations, use local MEMORY, attachments/Knowledge and optional project RAG.

The model can combine tools in one task. Ordinary requests do not require keyword-based lanes. Tool results and uncertain outcomes must not be presented as verified success.

**Windows is the host-tested platform for this Browser implementation.** Portable contracts do not certify native Browser support on Linux/macOS. Historical Security, Memory and Active Web evaluations retain their original source/runtime scope; they do not certify every later change. This development stage does not publish an installer or compile a new executable.

## Install and run from source

Requirements: Python 3.10+ (current CI uses 3.14), a running Ollama with an already installed tool-capable model, and Windows plus the prepared Browser component for Browser features. The recommended/default model tag is `qwen3.5:9b`. Nova does not automatically download it.

From **the checkout you intend to run**:

```powershell
Set-Location "C:\path\to\nova-assistant"
python -m venv .venv
$novaPython = Join-Path $PWD ".venv\Scripts\python.exe"
& $novaPython -m pip install -e ".[browser]"
& $novaPython -m local_cli --provider ollama --select-model
```

For an existing Python environment, reinstall with `-e ".[browser]"` from this checkout. Otherwise an editable install can still load another source copy when launched from Downloads or your home directory. Verify it with:

```powershell
& $novaPython -c "import local_cli; print(local_cli.__file__)"
```

`--debug` also prints the loaded source directory. Use `python -m local_cli --help` for startup arguments. A larger `--num-ctx` consumes more resources and does not correct a wrong installation.

The base package depends on `pypdf` for supported document extraction. The `browser` extra installs pinned Playwright. Optional `memory-semantic` adds NumPy for vector contracts, not a certified semantic-recall guarantee. See [pyproject.toml](pyproject.toml).

### Browser component

The prepared development component lives at `dist/browser/windows-x64/`: WebView2 host, Fixed Version runtime and automation dependencies. It is reproducible generated output, excluded from Git. Installing the Python extra alone does **not** create it; a clean checkout without the component cannot advertise Browser availability.

Dependency pins are in [native/browser-dependencies.json](native/browser-dependencies.json). This stage reuses the existing component; executable packaging/release is deferred. Missing Browser prerequisites do not disable file tools or terminal.

WebView2 is the default without a selection prompt. Optional alternatives are explicitly selected:

```text
/browser list
/browser use edge
/browser use chrome
/browser use webview2
```

Nova uses temporary owned profiles, not your personal Chrome/Edge profile. It does not install or silently switch browsers. Browser traffic has no exhaustive network isolation (`NOT_PROVIDED`, `HOST_UNISOLATED`); this is not a hostile-site network sandbox.

## Everyday use

Start in the project directory and ask naturally:

```text
Lee el README y dime de qué trata.
Crea catalogo.html con una landing sencilla y autocontenida.
Busca una noticia de México y abre la fuente para resumirla.
Abre esta URL y haz clic en el control que te indico.
```

Browser search uses Bing by default; `/search engine google` or `/search engine duckduckgo` selects an alternative. CAPTCHA, rate limits and changed markup can prevent search. Snippets are discovery metadata, not articles already read.

For login/CAPTCHA use `/browser takeover`, interact with the owned window, then explicitly `/browser resume`. Do not send passwords in chat. `/browser sensitive` accepts private declared-sensitive input. Uploading discloses a file to the page and requires approval. Completed downloads remain in owned staging until discarded; they are not automatically opened or executed.

`/fetch on|off|status` controls separate HTTP retrieval, independently of Browser search and terminal HTTP commands. HTTP public-destination checks do not imply Browser network isolation.

CLI system messages are English; the model can respond in your language. Normal mode shows concise progress, debug mode includes diagnostics. Ctrl+C requests cancellation. If stopping remains unconfirmed after a second interruption, the CLI says so rather than claiming termination.

## Commands

`/help` contains the full syntax. `/fetch` is canonical; `/web fetch` and `/quit` are not duplicate aliases.

| Area | Commands |
| --- | --- |
| Session | `/help`, `/exit`, `/clear`, `/resume`, `/save`, `/status` |
| Model/provider | `/models`, `/model`, `/provider`, `/brain`, `/registry`, `/info`, `/running`, `/install`, `/uninstall` |
| Browser/web | `/browser`, `/search`, `/fetch` |
| Context | `/attach`, `/source`, `/rag`, `/context`, `/usage`, `/copy` |
| Memory/work | `/memory`, `/agents`, `/plan`, `/ideate`, `/knowledge`, `/skills` |
| Git/maintenance | `/diff`, `/undo`, `/checkpoint`, `/rollback`, `/update` |

Git/maintenance commands may modify the checkout; inspect help before using them. Git is optional for ordinary chat. Administrative commands are not required for natural-language tasks.

## Configuration and data

Precedence: CLI arguments, environment variables, config file, defaults. The default config is `~/.config/nova/config`; the state root is `~/.local/state/nova`. See [local_cli/config.py](local_cli/config.py) for overrides.

Browser/search/fetch preferences are local state, separate from approval. Plans and legacy Knowledge normally use `.agents/`. Conversations, MEMORY and attachments use their configured state directories. On Windows the security audit defaults to `%LOCALAPPDATA%\Nova\security_audit\v1`. Browser profiles are temporary; retained downloads have an explicit discard command.

These are runtime/user data, not source. Do not delete them while Nova is running. Ignoring a path in Git does not prove cleanup or erase evidence. No user configuration migration is performed in this stage.

## Permissions and truthful results

- Policy, Approval, one-use Grants and ToolRuntime still mediate effects. Selecting a tool is not permission.
- Direct file tools enforce their supported filesystem scope. Supported out-of-scope access can require approval. Shell processes use your account's normal permissions, independently of the direct file broker.
- Dynamic application launch requests ask for permission; nested interpreters, elevation and critical operations retain their existing denials.
- To leave a desktop application running, the command tool uses `keep_open=true`; PowerShell uses `Start-Process` without `-Wait`. A successful launch does not verify a visible application window. Ordinary commands retain bounded process cleanup.
- Failed or uncertain effects cannot become success through model prose. Cancellation does not imply rollback. Uncertain Browser mutations/transfers must not be automatically repeated.
- Known/declared sensitive-value protection has explicit limits; it is not universal DLP, forensic erasure or protection from a receiving website.

Details: [application launch](docs/application_launch.md), [Browser blocks](docs/active_web_reimplementation/), [historical security limits](docs/security_v12/s8_limits.md).

## Development checks

Use the positive inventory rather than a blanket historical pytest campaign:

```powershell
& $novaPython -m pip install -e ".[browser,memory-semantic]" pytest pytest-subtests
& $novaPython ci/contract_inventory.py
$run = Join-Path $env:TEMP ("nova-preflight-" + [guid]::NewGuid().ToString("N"))
& $novaPython ci/run_contracts.py --job core --output "$run\core"
& $novaPython ci/run_contracts.py --job security --output "$run\security"
& $novaPython ci/run_contracts.py --job memory --output "$run\memory"
& $novaPython ci/run_contracts.py --job knowledge --output "$run\knowledge"
```

Outputs must be fresh owned directories outside the checkout. The runner validates classification, nonzero collection and the intended selection. Windows/native and local-model smokes have explicit prerequisites; ordinary CI does not repeat historical certification.

The small manual corpus uses the installed model, existing Browser component, owned synthetic pages and temporary files:

```powershell
& $novaPython scripts/smoke_browser_block7.py --output "$run\browser-corpus.json"
```

It changes no personal Browser preferences and uses fixture approvals only for its owned actions. This is a functional regression, not a general model/network certification.

### Optional Desktop development

```powershell
Set-Location desktop
npm ci
npm run dev
```

Desktop's backend must use the intended Python environment. CI runs seven contract suites and `tsc --noEmit`. This phase does not invoke `npm run build` or electron-builder, or change Desktop presentation/language.

## Documentation and license

Decisions and historical evidence live in [docs](docs/). Block 7 has a separate [corpus/pre-commit report](docs/active_web_reimplementation/bloque_7_corpus_precommit/resultados.md). Prior failed/partial evidence is preserved.

MIT. See [LICENSE](LICENSE).
