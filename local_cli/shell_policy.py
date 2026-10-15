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
# Dynamic execution can be approved, but an explicit child interpreter still
# cannot change the selected shell. Include quoted executable paths and the
# Start-Process form, previously rejected by the blanket dynamic-command rule.
_PS_SHELL_TARGET = (
    r'''(?:"(?:[^"\r\n]*[\\/])?(?:cmd|powershell|pwsh|bash|zsh|sh)(?:\.exe)?"|'''
    r"'(?:[^'\r\n]*[\\/])?(?:cmd|powershell|pwsh|bash|zsh|sh)(?:\.exe)?'|"
    r'''(?:[^\s"';&|]*[\\/])?(?:cmd|powershell|pwsh|bash|zsh|sh)(?:\.exe)?(?=\s|$|[;&|]))'''
)
_PS_CHILD_LAUNCH = re.compile(
    r"(?i)(?:\bStart-Process\b[^;\r\n|]*?\s+|(?<!&)&(?!&)\s*)" + _PS_SHELL_TARGET
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


def _mask_ps_literal_strings(text: str) -> str:
    """Hide literal PowerShell string contents for structural checks.

    A complete double-quoted string without expansion or escape markers is
    literal too: an ampersand in a quoted URL is data, not a call operator.
    Expandable strings remain visible, including their subexpressions, so
    this mask cannot hide dynamic execution. This is not a PowerShell parser.
    """
    result = list(text)
    index = 0
    while index < len(text):
        char = text[index]
        if char == "`":
            # An escaped quote outside a string must not start a literal.
            index += 2
            continue
        if char not in ("'", '"'):
            index += 1
            continue
        end = index + 1
        while end < len(text):
            current = text[end]
            if char == '"' and current == "`":
                # Nested quotes in expandable expressions require a full
                # parser. Keep the entire command visible conservatively.
                return text
            if char == '"' and current == "$":
                return text
            if current == char:
                if char == "'" and end + 1 < len(text) and text[end + 1] == "'":
                    end += 2
                    continue
                break
            end += 1
        if end >= len(text):
            # An incomplete quote is not a proven literal.
            break
        result[index:end + 1] = [
            "\n" if current == "\n" else " "
            for current in text[index:end + 1]
        ]
        index = end + 1
    return "".join(result)


class ShellPolicy:
    def classify(self, command: str, descriptor: ShellDescriptor) -> ShellDecision:
        if not command.strip() or "\x00" in command:
            return ShellDecision.BLOCK
        # A nested interpreter would interpret text outside this dialect's
        # checks. No tool-call argument can override the selected backend.
        structural = (_mask_ps_literal_strings(command)
                      if descriptor.kind == "powershell" else command)
        if _CHILD_SHELL.search(structural):
            return ShellDecision.BLOCK
        if is_command_dangerous(command):
            return ShellDecision.BLOCK
        if descriptor.kind == "powershell":
            dynamic = _PS_DYNAMIC.search(structural)
            if dynamic and (_PS_CHILD_LAUNCH.search(command) or _CHILD_SHELL.search(command)):
                return ShellDecision.BLOCK
            if (_PS_REMOVE.search(structural) and _PS_RECURSE.search(structural)
                    and _PS_TOP_LEVEL.search(command)):
                return ShellDecision.BLOCK
            if _PS_BLOCK.search(command) or _PS_DOWNLOAD_EXEC.search(command):
                return ShellDecision.BLOCK
            if dynamic or _PS_RISKY.search(command) or is_command_risky(command):
                return ShellDecision.CONFIRM
            return ShellDecision.ALLOW
        if is_command_risky(command) or re.search(r"\b(?:doas|su)\b", command):
            return ShellDecision.CONFIRM
        return ShellDecision.ALLOW
