from pathlib import Path
import sys
from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH).resolve().parents[1]
modules = []
for source in sorted((root / 'local_cli').rglob('*.py')):
    parts = list(source.relative_to(root).with_suffix('').parts)
    if parts[-1] == '__init__':
        parts.pop()
    modules.append('.'.join(parts))
datas = copy_metadata('numpy') + copy_metadata('pypdf') + copy_metadata('local-cli')
datas += [(str(root / 'LICENSE'), 'licenses/nova')]
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.is_file():
    datas.append((str(python_license), 'licenses/python'))

a = Analysis([str(root / 'packaging/windows/backend_entry.py')], pathex=[str(root)],
    binaries=[], datas=datas, hiddenimports=modules,
    excludes=['tkinter', 'pytest', 'playwright', 'greenlet', 'pyee'],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='nova-backend',
    debug=False, strip=False, upx=False, console=True,
    icon=str(root / 'desktop/build/icon.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='nova-backend')
