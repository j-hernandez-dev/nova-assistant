"""Portable report projection contracts; no browser/model/native fixture."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import importlib.util
import sys
from ci.sanitize_reports import publish,public_node

def test_parameter_values_are_hashed_in_public_case_names():
    assert 'synthetic-sensitive-marker'not in public_node('test_x[synthetic-sensitive-marker]')
    assert public_node('test_x[one]')!=public_node('test_x[two]')
    assert public_node('test_x')=='test_x'

def test_failed_reports_preserve_failure_without_body_or_credentials(tmp_path):
    output=tmp_path/'reports';output.mkdir()
    marker='synthetic-sensitive-marker'
    (output/'run.json').write_text(json.dumps(dict(exit_code=1,tests_executed=1,password=marker,
        native_ci_profile_cleanup={'status':'CLEANUP_UNCONFIRMED','owned_profile_absent':False,
            'arbitrary_detail':marker})),encoding='utf-8')
    (output/'selection.json').write_text(json.dumps(['tests/x.py::test_x']),encoding='utf-8')
    (output/'collected_nodeids.json').write_text(json.dumps(['tests/x.py::test_x['+marker+']']),encoding='utf-8')
    (output/'tests.xml').write_text('<testsuites><testsuite><testcase name="test_x['+marker+']" classname="tests.x"><failure type="AssertionError" message="'+marker+'">'+marker+'</failure><system-out>'+marker+'</system-out></testcase></testsuite></testsuites>',encoding='utf-8')
    result=publish(output)
    assert result['exit_code']==1 and result['public_report_counts']['failure']==1
    assert result['native_ci_profile_cleanup']=={'status':'CLEANUP_UNCONFIRMED','owned_profile_absent':False}
    public=output/'public'
    assert all(marker not in p.read_text(encoding='utf-8')for p in public.iterdir())
    assert len(list(ET.parse(public/'tests.xml').iter('failure')))==1
    assert not list(ET.parse(public/'tests.xml').iter('system-out'))
    assert 'password'not in(public/'run.json').read_text()

def test_only_allowlisted_reports_are_projected(tmp_path):
    output=tmp_path/'reports';output.mkdir()
    (output/'run.json').write_text('{"exit_code":0}',encoding='utf-8')
    (output/'fixture.key').write_text('synthetic sensitive fixture bytes',encoding='utf-8')
    (output/'profile').mkdir();(output/'profile/cookies').write_text('synthetic cookie',encoding='utf-8')
    publish(output)
    assert {p.name for p in(output/'public').iterdir()}=={'run.json','pytest.log'}

def test_runner_installs_same_interpreter_native_plugin_search_paths():
    # PYTHONPATH assignment affects children, not the running pytest interpreter.
    from ci.run_contracts import install_runtime_import_paths,ROOT
    before=list(sys.path)
    try:
        install_runtime_import_paths()
        assert str(ROOT/'native/nova-browser-host/tests')in sys.path
        assert importlib.util.find_spec('v12_b5.history_guard')is not None
    finally:sys.path[:]=before
