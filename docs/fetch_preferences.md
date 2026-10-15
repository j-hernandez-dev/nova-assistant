# Fetch and terminal preferences

Fetch is enabled by default. The model may choose `web_fetch` or a terminal
command from the available tools. There is no Active Web activation or browser
selection step in this copy.

At the `You>` prompt:

```text
/fetch status
/fetch off
/fetch on
```

`/web fetch status`, `/web fetch off`, and `/web fetch on` are aliases.
The commands appear in `/help`.

The explicit choice is saved in `fetch-preference.json` inside Nova's configured
state directory (by default `~/.local/state/nova`). A missing preference means
enabled. Starting Nova does not create or migrate this preference file.

`/fetch off` disables the fetch tool. It does not disable terminal HTTP commands
such as `curl.exe` or `Invoke-WebRequest`. Terminal commands continue through
their normal permissions and human approval; selecting a tool does not grant
permission to execute it. Destructive commands retain their existing checks.

This setting does not configure a search provider. An optional search provider
and direct retrieval of a known URL are separate functions.

## Start this copy from the correct directory

An existing Python environment may have an editable installation pointing to
the older repository. Starting one directory above this copy can therefore load
the older code. No reinstall or user configuration migration is required: start
from this exact directory and verify the imported module.

```powershell
Set-Location 'C:\Users\joseh\Downloads\nova-min\nova-assistant'
$novaPython = 'C:\Users\joseh\AppData\Local\Temp\nova-precommit-venv\Scripts\python.exe'
& $novaPython -c 'import local_cli; print(local_cli.__file__)'
& $novaPython -m local_cli --provider ollama --select-model --num-ctx 32768 --debug
```

The import check must print:

```text
C:\Users\joseh\Downloads\nova-min\nova-assistant\local_cli\__init__.py
```

CLI controls and user error messages use English. The model may continue
responding in the user's language. Invalid command arguments produce a usage or
error message rather than a traceback.

## Verification

A real `qwen3.5:9b` turn through the shared CLI Application called `web_fetch`
for `https://example.com/`, received a completed fetch result, and answered in
Spanish. The same temporary session confirmed default-on, explicit off,
saved-off after relaunch, and explicit on. No personal settings were changed.

The shell fix treats `&` inside a complete, non-expanding PowerShell quoted URL
as URL data. It does not automatically approve the surrounding command.
