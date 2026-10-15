# Persistent application launch

The command tool accepts `keep_open` (boolean, default false). When asked to
open a desktop application, the model should set it to true. On PowerShell,
use `Start-Process` without `-Wait` so the launch command can finish. This is
shared tool guidance, not a user-language classifier or a new slash command.

- A persistent launch requires exact human approval, including for a simple
  command. The CLI explicitly says applications will be kept open. JSONL and
  Desktop receive the same arguments and Approval/Grant binding.
- The flag is bound into both the tool arguments and the process snapshot
  before Approval/Grant. A pending invocation cannot change it afterward.
- Successful command completion releases the launcher's handles without
  terminating its child applications. The app can outlive the turn and Nova.
  The human closes it normally. Nova does not keep capturing its output.
- The cleanup receipt is scoped to `launcher_only_children_released`; it does
  not claim those children exited. This is not an application sandbox or lease.
- Temporary commands retain the original process-tree cleanup. Nonzero exit,
  cancellation and timeout retain cleanup even when `keep_open` was requested.
  The timeout bounds the launch command, not the lifetime of a released app.
- Policy denials, elevation restrictions and nested-interpreter restrictions
  remain in force. This flag cannot bypass them, Approval, or a fresh Grant.
- The result confirms command execution, not window visibility. Shell effects
  remain UNKNOWN where required. No automatic retry follows an uncertain effect.

Validation: portable tests in `tests/test_application_process_lifecycle.py`,
and the explicit Windows native case
`tests/security_v12/test_s4_host.py::test_owned_gui_lifetime_after_approved_shell_completion`.
The native fixture opens its own short-lived window, checks its exact process
identity, and closes only that window. It verifies persistent and temporary
lifetimes independently; it does not launch the user's applications.

The initial local-model selection smoke omitted the optional lifetime flag.
A compact shared shell instruction was added. The subsequent `qwen3.5:9b`
selection smoke proposed `Start-Process` with `keep_open=true`. Neither selection
smoke executed its proposed command. They are functional checks, not a model
quality benchmark or historical certification.

Local verification on Windows: 410 regression cases passed, plus 3 additional
denial cases and 7 native cases. The native checks cover persistent window
survival, temporary child cleanup, cancellation and timeout. The CI inventory
contains 3898 functions with no unclassified entries. All owned fixture windows
were closed and no fixture process remained at final inspection.
