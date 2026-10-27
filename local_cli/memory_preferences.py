"""Host-owned Memory preferences. Importing memories never imports permissions."""
from copy import deepcopy
import json
import os
from pathlib import Path
from threading import RLock
from uuid import uuid4

DEFAULTS = {'lexicalRecall':True, 'semanticRecall':False, 'autoCapture':True,
            'captureMode':'low_risk', 'sensitiveProjects':[]}
FIELDS = frozenset(DEFAULTS) - {'sensitiveProjects'}


def canonical_project(path):
    if not isinstance(path,str) or not path.strip() or '\x00' in path or len(path)>4096:
        raise ValueError('INVALID_MEMORY_SETTINGS')
    folder=Path(path).expanduser()
    if not folder.is_absolute():raise ValueError('INVALID_MEMORY_SETTINGS')
    return os.path.normcase(str(folder.resolve()))


class MemoryPreferences:
    def __init__(self,state_dir):
        self.path=Path(state_dir).expanduser()/'memory-preferences.json'
        self._lock=RLock()
        self._value=deepcopy(DEFAULTS)
        try:
            if self.path.is_symlink() or self.path.stat().st_size>2_000_000:raise ValueError()
            raw=json.loads(self.path.read_text(encoding='utf-8'))
            version=raw.pop('schemaVersion')
            if type(version) is not int or version!=1 or set(raw)!=set(DEFAULTS):raise ValueError()
            self._validate({k:raw[k] for k in FIELDS})
            if not isinstance(raw['sensitiveProjects'],list) or len(raw['sensitiveProjects'])>1024:raise ValueError()
            raw['sensitiveProjects']=sorted(set(canonical_project(p) for p in raw['sensitiveProjects']))
            self._value=raw
        except (OSError,ValueError,KeyError,TypeError,UnicodeError):pass

    @staticmethod
    def _validate(value):
        if (not isinstance(value,dict) or set(value)!=FIELDS
            or any(type(value[k]) is not bool for k in ('lexicalRecall','semanticRecall','autoCapture'))
            or value['captureMode'] not in ('low_risk','propose_only')):
            raise ValueError('INVALID_MEMORY_SETTINGS')

    def snapshot(self):
        with self._lock:return deepcopy(self._value)

    def _save(self,value):
        if self.path.is_symlink():raise OSError('Invalid preferences target')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_name('.memory-preferences-'+uuid4().hex+'.tmp')
        try:
            with temporary.open('x',encoding='utf-8') as out:
                json.dump({'schemaVersion':1,**value},out,ensure_ascii=False)
                out.write('\n');out.flush();os.fsync(out.fileno())
            os.replace(temporary,self.path)
        finally:temporary.unlink(missing_ok=True)
        self._value=value

    def update(self,value):
        self._validate(value)
        with self._lock:self._save({**self._value,**deepcopy(value)})
        return self.snapshot()

    def set_sensitive(self,path,enabled):
        if type(enabled) is not bool:raise ValueError('INVALID_MEMORY_SETTINGS')
        path=canonical_project(path)
        with self._lock:
            projects=set(self._value['sensitiveProjects'])
            if enabled:projects.add(path)
            else:projects.discard(path)
            if len(projects)>1024:raise ValueError('INVALID_MEMORY_SETTINGS')
            self._save({**self._value,'sensitiveProjects':sorted(projects)})
        return self.snapshot()

    def allows_sensitive(self,workspace):
        with self._lock:return canonical_project(str(workspace)) in self._value['sensitiveProjects']

    def reset(self):
        with self._lock:self._save(deepcopy(DEFAULTS))
        return self.snapshot()
