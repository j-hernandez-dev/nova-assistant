import json
from unittest.mock import patch
import pytest
from local_cli.memory_preferences import MemoryPreferences,DEFAULTS


def test_memory_defaults_persistence_and_project_permission(tmp_path):
    prefs=MemoryPreferences(tmp_path/'state')
    assert prefs.snapshot()==DEFAULTS
    values={'lexicalRecall':False,'semanticRecall':True,'autoCapture':False,'captureMode':'propose_only'}
    prefs.update(values);prefs.set_sensitive(str(tmp_path),True)
    reopened=MemoryPreferences(tmp_path/'state')
    assert reopened.allows_sensitive(tmp_path)
    assert all(reopened.snapshot()[k]==v for k,v in values.items())
    reopened.set_sensitive(str(tmp_path),False);assert not reopened.allows_sensitive(tmp_path)
    reopened.reset();assert MemoryPreferences(tmp_path/'state').snapshot()==DEFAULTS


@pytest.mark.parametrize('patch_value',[{'semanticRecall':'true'},{'captureMode':'off'},{'autoCapture':1},{'sensitiveProjects':[]}])
def test_memory_preferences_reject_invalid_or_permission_in_settings(tmp_path,patch_value):
    prefs=MemoryPreferences(tmp_path)
    candidate={k:v for k,v in DEFAULTS.items() if k!='sensitiveProjects'}|patch_value
    with pytest.raises(ValueError):prefs.update(candidate)
    assert prefs.snapshot()==DEFAULTS


def test_failed_memory_save_preserves_file_and_confirmed_state(tmp_path):
    prefs=MemoryPreferences(tmp_path);prefs.reset();before=prefs.path.read_bytes()
    with patch('local_cli.memory_preferences.os.replace',side_effect=OSError('synthetic failure')):
        with pytest.raises(OSError):prefs.set_sensitive(str(tmp_path),True)
    assert prefs.snapshot()==DEFAULTS and prefs.path.read_bytes()==before
    assert list(tmp_path.glob('.memory-preferences-*.tmp'))==[]


def test_memory_file_cannot_invent_permissions_or_invalid_defaults(tmp_path):
    file=tmp_path/'memory-preferences.json'
    file.write_text(json.dumps({'schemaVersion':1,**DEFAULTS,'autoCapture':'true'}))
    assert MemoryPreferences(tmp_path).snapshot()==DEFAULTS
