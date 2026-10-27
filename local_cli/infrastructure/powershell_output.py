"""Presentation of bounded PowerShell stderr, never command or effect authority."""
from __future__ import annotations

import codecs
import ntpath
import re
import xml.etree.ElementTree as ET

_MARKER = '#< CLIXML'
_NS = '{http://schemas.microsoft.com/powershell/2004/04}'
_ESCAPE = re.compile(r'_x([0-9a-fA-F]{4})_')


def is_powershell_command(argv):
    """Recognize only the host compiler's PowerShell invocation."""
    return (ntpath.basename(argv[0]).casefold() in
            ('powershell.exe', 'powershell', 'pwsh.exe', 'pwsh')
            and '-encodedcommand' in [arg.casefold() for arg in argv[1:]])


def _unescape(text):
    # Decode once: _x005F_x0041_ is the literal _x0041_, not the letter A.
    text = _ESCAPE.sub(lambda match: chr(int(match[1], 16)), text)
    return text.encode('utf-16-le', errors='surrogatepass').decode('utf-16-le', errors='replace')


def _document(xml):
    # No DTDs/entities or external resolution. Input already has the raw pipe cap.
    if '<!' in xml:
        return None
    try:
        root = ET.fromstring(xml)
    except (ET.ParseError, ValueError):
        return None
    if root.tag != _NS + 'Objs':
        return None
    records = []
    for child in root:
        stream = child.get('S', '').casefold()
        if stream == 'progress':
            continue
        if child.tag == _NS + 'S':
            text = _unescape(child.text or '')
        elif child.tag == _NS + 'Obj':
            value = child.find(_NS + 'ToString')
            if value is None:
                value = next((item for item in child.iter(_NS + 'S')
                              if item.get('N') in ('Message', 'MessageData')), None)
            if value is None:
                return None  # Preserve an unsupported diagnostic instead of losing it.
            text = _unescape(value.text or '')
        else:
            return None
        if stream in ('warning', 'verbose', 'debug', 'information'):
            text = stream.upper() + ': ' + text
        if text and not text.endswith(('\n', '\r')):
            text += '\n'
        records.append(text)
    return ''.join(records)


class PowerShellStderr:
    """Stream plaintext; hold serialized records until a complete XML document.

    The launcher supplies only bytes retained under its existing raw stderr cap.
    Malformed or cut documents remain available verbatim as diagnostic evidence.
    """
    def __init__(self):
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.pending = ''
        self.xml = False
        self.after_xml = False

    def feed(self, chunk, *, final=False):
        self.pending += self.decoder.decode(chunk, final=final)
        output = []
        if final and self.xml and not self.pending:
            self.xml = False
            return _MARKER.encode('utf-8')
        while self.pending:
            if self.xml:
                end = self.pending.find('</Objs>')
                if end < 0:
                    if final:
                        output.append(_MARKER + self.pending)
                        self.pending = ''
                    break
                end += len('</Objs>')
                document, self.pending = self.pending[:end], self.pending[end:]
                decoded = _document(document)
                output.append(decoded if decoded is not None else _MARKER + document)
                self.xml = False
                self.after_xml = decoded is not None
            else:
                if self.after_xml:
                    self.pending = self.pending.lstrip('\r\n')
                    if not self.pending:
                        break
                    self.after_xml = False
                start = self.pending.find(_MARKER)
                if start >= 0:
                    output.append(self.pending[:start])
                    self.pending = self.pending[start + len(_MARKER):]
                    self.xml = True
                else:
                    # Hold a possible partial marker, including across pipe reads.
                    keep = 0 if final else next((size for size in range(
                        min(len(self.pending), len(_MARKER) - 1), 0, -1)
                        if self.pending.endswith(_MARKER[:size])), 0)
                    end = len(self.pending) - keep
                    output.append(self.pending[:end])
                    self.pending = self.pending[end:]
                    break
        return ''.join(output).encode('utf-8')
