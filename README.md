# Nova

**0.13.0 · A local AI assistant for projects, files, sources, and memories.**

Nova combines a desktop interface with Ollama models and tools for reading and modifying files, running commands, and accessing the web. The model proposes actions; the host checks permissions and requests the appropriate approvals. The interface is available in English and Spanish.

This release brings together the Nova Desktop rebuild. Desktop and the CLI share the Application Python backend. The identifiers `local-cli`, `local_cli`, `local-cli-desktop`, and the Electron application identifier are retained for compatibility with existing installations and profiles.

## Features

- **Projects:** independent folders, conversation history, a resizable sidebar, and a viewer with tabs for files, sources, and memories.
- **LLM and EM models:** capability-based detection, installed model selection, individual model enablement, automatic or manual context limits, and separate usage statistics.
- **Ollama catalog:** All, Installed, and For You views; search, variants, and explicit downloads. Recommendations consider available memory and are estimates.
- **Sources:** files copied into Nova and URLs imported per project. Select them for the next message, preview them, download them, change their project association, or delete them.
- **Knowledge:** lexical and semantic project retrieval, automatic indexing, and index rebuilding. Semantic options require an installed, enabled, and available EM model.
- **Memories:** browsing, manual creation, table-based editing, deletion, and automatic capture proposals; import and export with confirmations for sensitive content.
- **Storage:** measurement of Nova's data usage, access to its folders, and management of file copies associated with projects or left unlinked.
- **Web:** separate permissions for reading, searching, and browsing; Google, Bing, or DuckDuckGo, and WebView2, Chrome, or Edge, depending on availability.
- **Interface:** four light and dark themes, interface and code fonts, Nova 2D and Nova 3D mascots, optional transitions, zoom from 50% to 150%, menus, and configurable keyboard shortcuts.

Windows is the desktop and browsing platform validated locally. Portable Python contracts have CI coverage on Windows, Linux, and macOS; this does not constitute validation of the GUI or native browsing on those systems. The `build:source` verification build does not generate installers. Windows packaging has a separate process that includes an executable backend, WebView2, and Windows Sandbox verification; see the [Windows distribution guide](docs/releases/windows-installer-0.13.0.md).

## Run Nova Desktop from source

You need Git, Python 3.10 or later, Node.js 22.12 or later with npm, and a running Ollama instance. CI uses Python 3.14 and Node.js 24. Install a tool-capable conversational model in Ollama; Nova does not download one at startup. The default model is `qwen3.5:9b`, but you should choose a model suitable for your hardware.

From PowerShell:

```powershell
git clone https://github.com/j-hernandez-dev/nova-assistant.git
Set-Location nova-assistant
python -m venv .venv
$novaPython = Join-Path $PWD ".venv\Scripts\python.exe"
& $novaPython -m pip install -e ".[browser]"
Set-Location desktop
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

`npm run dev` opens Nova and starts its backend. Keep that terminal open. For subsequent launches, run the same command from `desktop`. Node must be on the PATH used by processes launched through npm.

Desktop selects this checkout's `.venv`, even if another Python environment is active. The startup log identifies the interpreter and working directory being used. If you previously installed another copy, reinstall the editable package from the correct checkout and verify where it is loaded from:

```powershell
# From the repository root
& .\.venv\Scripts\python.exe -c "import local_cli; print(local_cli.__file__)"
```

If an excessively long PATH prevents `node`, `tsc`, or `vite` from being found, you can shorten it for the current terminal without changing Windows' saved environment variables:

```powershell
$env:Path = "C:\Program Files\nodejs;$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\WindowsPowerShell\v1.0;C:\Program Files\Git\cmd"
npm.cmd run dev -- --host 127.0.0.1
```

If your npm version blocks Electron or esbuild installation scripts, approve those dependencies as instructed by npm. To restore a missing Electron binary, run `node .\node_modules\electron\install.js` from `desktop`.

### Browsing component

WebView2 requires the component prepared in `dist/browser/windows-x64/`, which includes the host, its runtime, and automation dependencies. This is generated output and is excluded from Git. **Installing the Python `browser` extra does not create this component.** A clean checkout without it can use files, the terminal, and other available features, but must not report WebView2 browsing as ready.

Dependency versions and their origins are listed in [native/browser-dependencies.json](native/browser-dependencies.json). Also see [native](native/) and the [preparation scripts](scripts/). Chrome and Edge are explicit alternatives when installed and their requirements are available. Nova does not silently install or switch browsers.

## Build the Windows installer

Building requires Windows x64, Python 3.14 x64, Node.js 22.12 or later, and the .NET 10 SDK. The build installs its dependencies into `build/windows/python`, prepares WebView2 according to the dependency manifest, and may download the required components. The installed application includes these components and does not require a separate Python, Node.js, or .NET installation. Ollama and models remain external requirements.

```powershell
# From the repository root, after preparing Node and the development Python environment
Set-Location desktop
npm.cmd ci
npm.cmd run build:win
```

The output is `desktop/release/Nova-0.13.0-windows-x64-setup.exe`, accompanied by a size and SHA256 receipt in `windows-build.json`. The script does not publish to GitHub. The `build`, `dist`, and `desktop/release` folders contain generated output and are excluded from Git. To test the installer without modifying the host installation, use Windows Sandbox:

```powershell
# From the repository root; use a new directory outside the checkout
$installerQA = Join-Path $env:TEMP ("nova-install-qa-" + [guid]::NewGuid().ToString("N"))
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/test_windows_installer.ps1 `
  -Installer "$PWD/desktop/release/Nova-0.13.0-windows-x64-setup.exe" -Output "$installerQA"
```

This test does not modify host policies: it creates an isolated Windows environment without networking, checks the backend and a local WebView2 page, opens Nova through its actual IPC, and checks that uninstallation preserves the profile and documents. Windows execution policies still apply; any block is reported as a failure. The installer provided with this release does not include a commercial code-signing certificate.

## Projects, sources, and context

Add a folder through Projects or **File → New project…**. The initial project is `<checkout>/workspace/` during development and `Documents/Nova/workspace/` for a new installation. Installation preserves projects already saved in the profile. The content panel contains Files, Sources, and Memories. General settings let you hide it to dedicate the entire panel to the project list.

There are two complementary ways to use sources:

1. **Explicit selection for a message:** select their checkboxes in the sidebar. They appear above the message field and can be removed using ×. A file added through the picker or dragged into the chat is copied into Nova, associated with the project, and selected for the message.
2. **Automatic retrieval:** Knowledge settings control which project passages are retrieved through keyword matching or semantic similarity. This is independent of explicit selection.

Selected texts that fit within the context budget are included in full; larger texts are prepared as passages. `source_read` lets the model read more from the authorized copy during that turn. Selecting a source does not copy the file into the working directory or guarantee that the entire document will fit into a single context.

References display the source and a readable location. Validating `[K1]`, `[K2]`, and similar markers checks the turn's structural references, not the truth of every claim. Invented identifiers or ranges such as `[K1-K10]` may produce an unverifiable-reference warning. Nova does not rewrite the response to hide it.

## Local models

LLM Model contains conversational models, while EM Model contains embedding models. Installed models are classified using capabilities reported by Ollama; a model's commercial name alone is insufficient to identify it as an embedding model.

| Model | Manual context options | Default |
| --- | --- | --- |
| LLM | 4K, 8K, 16K, 32K, 64K, 128K, 256K | Automatic |
| EM | 512, 1K, 2K, 4K, 8K, 16K, 32K | Automatic; all EM models enabled |

These settings do not increase the model's limits or the computer's available memory. Nova reports context and execution errors. For an embedding model, context limits each input text; it does not represent conversation history or response tokens.

The public catalog is retrieved from Ollama, and its metadata is cached. When offline, Nova can use saved information and indicate that it is outdated. Downloading, deleting, and using models are explicit actions. Ollama manages model weights, which are not included in Nova's storage usage.

## Memories

**Retrieval** queries existing memories; **capture** creates memories or candidates:

- Lexical retrieval: matching words and terms; enabled by default.
- Semantic retrieval: similarity through embeddings; disabled by default and dependent on an available EM model.
- Automatic capture: enabled by default in **Low-risk saving** mode. **Propose only** leaves candidates for review under Pending proposals.
- Manual capture: lets you choose the type, current-project or personal-profile scope, and sensitive-content classification.

Memory settings let you authorize access to sensitive memories per project, with confirmation. Viewing, writing, or exporting sensitive content retains the corresponding confirmation requirements. There is no remote-context memory option.

Importing replaces current memories after confirmation. Exporting can include sensitive content only with confirmation. Exported files contain user data: keep them outside the repository.

## Settings and shortcuts

| Group | Sections |
| --- | --- |
| Interface | General, Appearance, Shortcuts |
| Models | LLM Model, EM Model |
| Context and tools | Memory, Knowledge, Web |
| Projects and data | Projects, Chats, Storage |
| About | Version, copyright, backend, provider, and tools |

Settings are saved when applied. Reset restores the section's defaults; Storage uses **Refresh** to measure usage again. The interface language can follow the system or be set to English or Spanish. This does not translate chats or change the model's responses.

Default Windows shortcuts, configurable in Shortcuts:

| Action | Shortcut |
| --- | --- |
| Projects | Ctrl+B |
| Sources | Ctrl+Shift+F |
| Memories | Ctrl+Shift+N |
| Models | Ctrl+Shift+M |
| Settings | Ctrl+, |
| Focus message field | Ctrl+L |
| History | Ctrl+Shift+H |
| Attach file | Ctrl+Shift+A |
| Add project | Ctrl+Shift+O |
| Close viewer | Ctrl+Shift+W |
| Send / new line / stop | Enter / Shift+Enter / Escape |

## Data and storage

Default locations; backend overrides are defined in [local_cli/config.py](local_cli/config.py):

| Data | Location |
| --- | --- |
| Desktop preferences, projects, appearance, and shortcuts | `%APPDATA%\nova-desktop\` |
| Python configuration | `%USERPROFILE%\.config\nova\config` |
| Conversations, sessions, memories, source copies, and indexes | `%USERPROFILE%\.local\state\nova\` |
| Security audit | `%LOCALAPPDATA%\Nova\security_audit\v1\` |
| Model catalog | `%USERPROFILE%\.cache\nova\` |
| Browsing data and retained downloads | Managed browsing folders; Storage displays the effective paths |
| Plans and legacy Knowledge data | The project's `.agents/` folder |

Storage breaks down chats, attachments, memories, browsing, configuration, auditing, the catalog, and caches. It excludes the application installation and Ollama model weights. Refresh recalculates sizes and the inventory.

Attaching a file creates a **persistent copy**. Moving or renaming the original does not break that copy. You can download it through Save As, unlink it, move its association to another project, or delete it. Removing a project preserves its copies under **Unlinked**, unless you confirm deletion of its associated files. Deleting Nova's copy does not delete the original.

Folder cleanup explains its effects and requests a restart when a store is in use. Pending operations are retained in `nova-storage-control`, alongside the profile, until completed. Do not manually delete active stores.

## Permissions and recovery

Nova can read, write, edit, list, and search files; run commands; retrieve web pages; and operate a browser. Web permissions are independent of action approvals. Search uses Google by default; Bing and DuckDuckGo are alternatives.

Policy checks, approvals, and single-use grants mediate side effects. The shell and browser run with the account's normal permissions. Browser profiles are dedicated and temporary; personal Chrome or Edge profiles are not used. This does not provide complete process or network isolation. Sensitive-value protection has explicit limits and is not equivalent to encryption or forensic erasure.

Failed or uncertain actions are not turned into successes by the model's response. Cancellation does not undo completed actions. Interrupted operations and approvals are not automatically replayed when the backend restarts. Unsent drafts and saved history are preserved.

Desktop supports one instance per profile and regenerates disposable Chromium caches before startup. It retains a previous copy in `.chromium-cache-backup` without deleting cookies, localStorage, preferences, chats, or memories. If a cache is locked, persistent use of that cache is avoided for that startup. This reduces problems after abrupt shutdowns but does not replace a backup.

Details: [application execution](docs/application_launch.md), [browsing](docs/active_web_reimplementation/), and [security limits](docs/security_v12/s8_limits.md).

## CLI

```powershell
# From the checkout root
& .\.venv\Scripts\python.exe -m local_cli --provider ollama --select-model
```

`--help` describes arguments, and `/help` describes commands. Available commands include `/models`, `/model`, `/browser`, `/search`, `/fetch`, `/attach`, `/source`, `/rag`, `/memory`, `/context`, and `/usage`. `/fetch on|off|status` controls HTTP reading separately from browsing. CLI system messages are in English; the model can respond in your language.

## Development and release checks

From the repository root, with the Python environment prepared:

```powershell
$novaPython = Join-Path $PWD ".venv\Scripts\python.exe"
& $novaPython -m pip install -e ".[browser,memory-semantic]" pytest pytest-subtests
& $novaPython -B ci/release_check.py --tag v0.13.0
& $novaPython -B ci/contract_inventory.py
$run = Join-Path $env:TEMP ("nova-preflight-" + [guid]::NewGuid().ToString("N"))
& $novaPython -B ci/run_contracts.py --job core --output "$run\core"
& $novaPython -B ci/run_contracts.py --job security --output "$run\security"
& $novaPython -B ci/run_contracts.py --job memory --output "$run\memory"
& $novaPython -B ci/run_contracts.py --job knowledge --output "$run\knowledge"
Set-Location desktop
npm.cmd ci
npm.cmd audit --audit-level=low
npm.cmd test
npm.cmd run build:source
```

Contract results are written to new, test-owned directories outside the checkout. The inventory distinguishes current tests, historical artifacts, and native or real-model checks. Do not run all historical campaigns as though they certify the current code.

`npm test` runs every ordinary `.test.cjs` suite and requires them to match the CI inventory. `build:source` checks TypeScript and builds the renderer, main process, and preloads; **it does not run electron-builder**. `build:win` prepares a standalone PyInstaller backend, the browsing component, and the NSIS x64 installer in `desktop/release`, with publishing disabled. Other packaging scripts retain their previous scope; macOS and Linux do not have this validated standalone distribution.

To check the visible version using Electron and the synthetic backend, use a new directory outside the checkout:

```powershell
# From the repository root, after build:source
$nativeRun = Join-Path $env:TEMP ("nova-about-" + [guid]::NewGuid().ToString("N"))
node desktop/tests/run_gui.cjs --case about-version --output "$nativeRun" --python "$novaPython"
```

The launcher gives the test application the actual package version and creates a private profile. It also supports `question-host` and `resume-recovery`; these cases use a scripted backend without real inference or data from your profile.

Electron tests and campaigns involving real models or browsing are explicit checks with dedicated profiles. See the [0.13.0 results and limitations](docs/releases/0.13.0.md). Earlier evidence, including failed or partial attempts, remains in [docs](docs/) with its original scope.

## License and origin

MIT; see [LICENSE](LICENSE). Nova builds on the original [local-cli project by lutelute](https://github.com/lutelute/local-cli); attribution for those contributions is preserved.
