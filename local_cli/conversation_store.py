"""Per-project last-conversation autosave — quit no longer loses work.

The flight recorder (session_log.py) records *events* for diagnosis;
this store keeps the *faithful message history* needed to resume.
After every turn the frontend saves the conversation to
``<state_dir>/projects/<cwd-slug>/last-conversation.jsonl``; the next
session in the same folder can restore it (CLI ``/resume``, desktop
"restore last conversation").

System messages are not saved: the system prompt and project
instructions are version-dependent and re-built fresh on resume, and
mid-conversation skill injections re-fire on the next matching input.

Same constitution as the flight recorder: fail-open (a broken save
never breaks the session), atomic (write temp + rename, so a crash
mid-save cannot corrupt the previous good copy), tolerant load
(corrupt lines are skipped).
"""

import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local_cli.session_log import project_slug

_FILENAME = "last-conversation.jsonl"

# A resumable conversation of thousands of messages would blow a small
# model's context anyway; keep the newest tail.
_MAX_MESSAGES = 400


class ConversationStore:
    """Save/load the last conversation for one project directory."""

    def __init__(
        self,
        state_dir: str,
        cwd: str | None = None,
        enabled: bool = True,
    ) -> None:
        self._enabled = enabled
        try:
            self._cwd = str(Path(cwd or os.getcwd()).resolve())
        except OSError:
            self._cwd = str(cwd or "?")
        self._legacy_dir = (
            Path(state_dir).expanduser() / "projects"
            / project_slug(self._cwd)
        )
        identity = hashlib.sha256(os.path.normcase(self._cwd).encode('utf-8')).hexdigest()[:16]
        self._dir = self._legacy_dir.with_name(self._legacy_dir.name + '-' + identity)

    @property
    def path(self) -> Path:
        return self._dir / _FILENAME

    @property
    def history_paths(self) -> list[Path]:
        paths = [self.path]
        legacy = self._legacy_dir / _FILENAME
        try:
            with legacy.open(encoding='utf-8') as stream:
                first = json.loads(stream.readline(131072))
            cwd = first.get('cwd') if isinstance(first, dict) and first.get('_meta') else None
            if isinstance(cwd, str) and Path(cwd).is_absolute() and os.path.normcase(str(Path(cwd).resolve())) == os.path.normcase(self._cwd):
                paths.append(legacy)
        except (OSError, ValueError, IndexError):
            pass
        return paths

    def _read_path(self):
        return next((path for path in self.history_paths if path.exists()), self.path)

    def clear_checked(self):
        for path in self.history_paths:
            path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Save / load / clear
    # ------------------------------------------------------------------

    def save(self, messages: list[dict[str, Any]]) -> None:
        """Persist the conversation (minus system messages).  Never raises."""
        try:
            self.save_checked(messages)
        except Exception:
            pass  # legacy fail-open facade; application can observe failures

    def save_checked(self, messages: list[dict[str, Any]]) -> None:
        """Same legacy format/retention, with observable errors for adapters."""
        if not self._enabled:
            return
        keep = [
            m for m in messages
            if isinstance(m, dict) and m.get("role") != "system"
        ][-_MAX_MESSAGES:]
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "_meta": True,
                "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "cwd": self._cwd,
            }, ensure_ascii=False) + "\n")
            for message in keep:
                fh.write(json.dumps(message, ensure_ascii=False, default=str) + "\n")
        os.replace(tmp_path, self.path)

    def load(self, *, include_presentation: bool = False, include_archive_date: bool = False) -> list[dict[str, Any]]:
        """Return the saved messages ([] if absent or unreadable)."""
        if not self._enabled:
            return []
        try:
            text = self._read_path().read_text(encoding="utf-8")
        except OSError:
            return []
        messages: list[dict[str, Any]] = []
        archived_at = None
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            if obj.get('_meta'):
                value = obj.get('saved_at')
                try:
                    if isinstance(value, str) and len(value) <= 64 and datetime.fromisoformat(value).tzinfo is not None:
                        archived_at = value
                except ValueError:
                    pass
                continue
            if "role" in obj:
                if not include_presentation:
                    obj.pop("_nova_display", None)
                elif include_archive_date and archived_at and obj.get('role') in ('user', 'assistant') and not obj.get('_nova_display'):
                    # This is the archive's date, never an invented send/completion time.
                    obj['_nova_display'] = {'savedAt': archived_at}
                messages.append(obj)
        return messages

    def info(self) -> dict[str, Any] | None:
        """Summary for a resume prompt: message count, time, preview."""
        messages = self.load()
        if not messages:
            return None
        saved_at = ""
        try:
            first_line = self._read_path().read_text(
                encoding="utf-8",
            ).splitlines()[0]
            meta = json.loads(first_line)
            if isinstance(meta, dict) and meta.get("_meta"):
                saved_at = str(meta.get("saved_at", ""))
        except (OSError, ValueError, IndexError):
            pass
        preview = ""
        for message in messages:
            if message.get("role") == "user":
                content = str(message.get("content", ""))
                preview = content[:80]
                break
        return {
            "count": len(messages),
            "saved_at": saved_at,
            "preview": preview,
        }

    def clear(self) -> None:
        """Discard the saved conversation (e.g. on /clear).  Never raises."""
        try:
            self.clear_checked()
        except OSError:
            pass
