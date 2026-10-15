# Block 5 — Human intervention and files

Windows implementation using the bundled WebView2 host or an explicitly selected
installed Edge/Chrome. Browser actions and transfers still use the shared
ToolRuntime, Policy, Approval and one-use Grant path.

## Usage

```text
/browser takeover
/browser resume
/browser close
/browser file "C:\path\outside-workspace\example.txt"
/browser sensitive
/browser downloads
/browser discard <downloadId>
```

`takeover` opens the current owned browser window and pauses agent tools. Complete
login/CAPTCHA in that window, then use `resume`. Nova obtains a fresh observation
and invalidates old refs; the window remains open. Closing the window never
implicitly resumes automation. If continuity cannot be confirmed, close the
browser instead. Do not paste passwords into the chat. `sensitive` privately
registers an additional known value for redaction, using hidden terminal input.

Ask Nova naturally to upload a workspace file to an observed file input, or to
download an exact link. Files outside the workspace need explicit host selection
with `/browser file` first. Every upload/download asks for approval of the exact
operation. Selection alone is not approval. The model tools are
`browser_request_takeover`, `browser_upload` and `browser_download`.

Uploads are bounded at 32 MiB. Nova snapshots and revalidates file identity,
revision, size and digest before handing an immutable in-memory copy to the
browser. Attaching a file already discloses it to the website. A local attachment
receipt does not confirm a remote business outcome.

Downloads have a 32 MiB/30 second bound and require an exact one-use permit.
Unrequested downloads are denied. Completed files receive an owned staging path,
size and SHA256 digest only after engine completion. Remote filenames never
choose a local path. Files survive browser close; inspect/discard them with the
commands above. Retained receipts expire after 14 days; expiration does not
silently erase the file. No auto-open, execution or Knowledge import occurs.
WebView2 currently requires the download event URL to match the approved URL;
redirected attachment URLs may need the exact final URL. Interrupted/uncertain
transfers are never retried automatically.

Password/autocomplete-sensitive fields and `data-nova-sensitive` fields are
captured during human control by fixed instrumentation. Committed known values
remain redacted across navigation and resume. This is a known/declared-value
boundary, not universal DLP, protection from the receiving website, or forensic
erasure. Arbitrary ordinary text inputs are not assumed sensitive.

## Verification

Portable contracts are part of Core CI. The real browser job is explicit:

```powershell
python ci/run_contracts.py --job browser-block5 --special --output "$env:TEMP\nova-block5-ci-<new-id>"
```

It requires Windows x64 and the complete rebuilt package in
`dist/browser/windows-x64`. Missing prerequisites fail; no browser is downloaded.
Owned HTTP fixtures simulate human input using trusted test automation. No real
credentials, public sites or personal profiles are used. Installed optional
browsers are tested only when present; absence is not a native positive claim.

CLI and JSONL/Desktop backend share Application's authenticated BrowserControl
contract and status. This block does not add Desktop controls or change its UI.
