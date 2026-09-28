"""Dialect-aware command classification before any shell process starts.

This is a conservative approval gate, not an operating-system sandbox.
"""

from __future__ import annotations

import re
from enum import Enum

from local_cli.security import is_command_dangerous, is_command_risky
from local_cli.shell_executor import ShellDescriptor


class ShellDecision(Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    BLOCK = "block"


_CHILD_SHELL = re.compile(
    r"(?i)(?:^|[;|&]\s*|\b(?:sudo|doas|env)\s+)"
    r"(?:cmd|powershell|pwsh|bash|zsh|sh)(?:\.exe)?(?:\s|$)|"
    r"\b(?:cmd(?:\.exe)?\s+/[ck]|"
    r"(?:powershell|pwsh)(?:\.exe)?\s+[^\n;|]*-(?:command|c|encodedcommand|enc|file|f)\b|"
    r"(?:bash|zsh|sh)(?:\.exe)?\s+-[a-z]*c\b)"
)
_PS_DYNAMIC = re.compile(
    r"(?i)\b(?:Invoke-Expression|iex|Invoke-Command|icm|Start-Process|"
    r"ScriptBlock\s*::\s*Create|Add-Type|Set-Alias|New-Alias|"
    r"Set-PSBreakpoint)\b|(?<!&)&(?!&)|\[scriptblock\]"
)
_PS_BLOCK = re.compile(
    r"(?i)\b(?:Format-Volume|Clear-Disk|Initialize-Disk|Remove-Partition|"
    r"Format-Disk|diskpart|bcdedit)\b|"
    r"\b(?:Remove-Item|ri|rm|rmdir|rd|del|erase)\b[^\n;|]*"
    r"(?:-Recurse\b[^\n;|]*)?(?:[A-Z]:\\\s*(?:$|[;|])|"
    r"\$env:SystemDrive\\\s*(?:$|[;|]))"
)
_PS_RISKY = re.compile(
    r"(?i)\b(?:Remove-Item|ri|rm|rmdir|rd|del|erase|Clear-Content|"
    r"Stop-Process|Stop-Computer|Restart-Computer|Restart-Service|"
    r"Set-ExecutionPolicy|Set-ItemProperty|Set-Acl|takeown|icacls|"
    r"taskkill|reg\s+(?:delete|add)|netsh|schtasks)\b|"
    r"\b(?:Move-Item|Copy-Item|Set-Content|Add-Content|Out-File)\b"
    r"[^\n;|]*(?:\\Windows\\|\\Program Files\\)|"
    r"\b(?:RunAs|sudo|doas)\b"
)
_PS_DOWNLOAD_EXEC = re.compile(
    r"(?is)\b(?:Invoke-WebRequest|iwr|Invoke-RestMethod|irm|curl|wget)\b"
    r"[^\n;]*\|[^\n;]*(?:iex|Invoke-Expression|&\s*(?:powershell|pwsh|cmd))\b"
)
_PS_REMOVE = re.compile(r"(?i)\b(?:Remove-Item|ri|rm|rmdir|rd|del|erase)\b")
_PS_RECURSE = re.compile(r"(?i)-(?:Recurse|r)\b")
_PS_TOP_LEVEL = re.compile(
    r"(?i)(?:[A-Z]:\\(?:[^\\\s'\";|]+)?\\?|"
    r"\$env:(?:SystemRoot|WINDIR|SystemDrive))(?:[\s'\";|]|$)"
)


def _mask_ps_single_quoted(text: str) -> str:
    """Hide literal PowerShell string contents for structural checks.

    Double-quoted strings are intentionally left intact: they can contain
    expandable subexpressions that execute commands.
    """
    result: list[str] = []
    index = 0
    literal = False
    while index < len(text):
        char = text[index]
        if char == "'":
            if literal and index + 1 < len(text) and text[index + 1] == "'":
                result.extend((" ", " "))
                index += 2
                continue
            literal = not literal
            result.append(" ")
        else:
            result.append(" " if literal and char != "\n" else char)
        index += 1
    return "".join(result)


class ShellPolicy:
    def classify(self, command: str, descriptor: ShellDescriptor) -> ShellDecision:
        if not command.strip() or "\x00" in command:
            return ShellDecision.BLOCK
        # A nested interpreter would interpret text outside this dialect's
        # checks. No tool-call argument can override the selected backend.
        structural = (_mask_ps_single_quoted(command)
                      if descriptor.kind == "powershell" else command)
        if _CHILD_SHELL.search(structural):
            return ShellDecision.BLOCK
        if is_command_dangerous(command):
            return ShellDecision.BLOCK
        if descriptor.kind == "powershell":
            if (_PS_REMOVE.search(structural) and _PS_RECURSE.search(structural)
                    and _PS_TOP_LEVEL.search(command)):
                return ShellDecision.BLOCK
            if _PS_DYNAMIC.search(structural) or _PS_BLOCK.search(command) \
                    or _PS_DOWNLOAD_EXEC.search(command):
                return ShellDecision.BLOCK
            if _PS_RISKY.search(command) or is_command_risky(command):
                return ShellDecision.CONFIRM
            return ShellDecision.ALLOW
        if is_command_risky(command) or re.search(r"\b(?:doas|su)\b", command):
            return ShellDecision.CONFIRM
        return ShellDecision.ALLOW
