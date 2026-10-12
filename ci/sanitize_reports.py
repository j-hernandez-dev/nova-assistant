"""Publish only bounded CI summaries; raw diagnostics stay in runner temp.

Never copy fixture directories, XML failure bodies, test stdout, parameter
values, credentials or TLS material into Actions artifacts.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

SAFE_RUN_FIELDS=('schema','scope','job','host','python','pytest','selection_manifest_sha256',
    'positive_base_contracts','collected_parameter_instances','collected_nodeids_sha256',
    'collection_guard','tests_executed','quality_attempts','model_campaigns','exit_code',
    'special_infrastructure','new_skips_xfails_or_deselection','skipped','xfailed','xpassed',
    'zero_collected','execution_complete','historical_python_write_veto','historical_native_ntfs_guard','bootstrap_error_class')

def public_node(name):
    name=str(name)
    if '[' in name:
        base,parameter=name.split('[',1)
        return base+'[case-'+hashlib.sha256(parameter.encode()).hexdigest()[:12]+']'
    return name

def publish(output:Path):
    output=output.resolve()
    root=Path(__file__).resolve().parents[1]
    if output.is_relative_to(root):raise ValueError('REPORT_OUTPUT_INSIDE_CHECKOUT')
    run=json.loads((output/'run.json').read_text(encoding='utf-8'))
    safe={k:run[k] for k in SAFE_RUN_FIELDS if k in run}
    cleanup=run.get('native_ci_profile_cleanup')
    if isinstance(cleanup,dict) and cleanup.get('status') in ('NOT_REQUIRED','CONFIRMED','CLEANUP_UNCONFIRMED'):
        safe['native_ci_profile_cleanup']={'status':cleanup['status']}
        if type(cleanup.get('owned_profile_absent')) is bool:
            safe['native_ci_profile_cleanup']['owned_profile_absent']=cleanup['owned_profile_absent']
    public=output/'public';public.mkdir(exist_ok=True)
    tree=ET.parse(output/'tests.xml') if (output/'tests.xml').exists() else None
    counts=Counter();newroot=ET.Element('testsuites');suite=ET.SubElement(newroot,'testsuite',name='positive-contract-regression')
    if tree is not None:
        for item in tree.iter('testcase'):
            attrs={k:public_node(item.get(k,'')) for k in ('name','classname')}
            attrs['time']=item.get('time','0')
            target=ET.SubElement(suite,'testcase',attrs)
            state='passed'
            for kind in ('failure','error','skipped'):
                original=item.find(kind)
                if original is not None:
                    state=kind
                    # Preserve failure truth, never publish arbitrary assertion
                    # text (which can contain a synthetic known secret).
                    ET.SubElement(target,kind,type=original.get('type',kind),
                        message='Details retained in private runner diagnostics; not published.')
                    break
            counts[state]+=1
        suite.set('tests',str(sum(counts.values())))
        for kind in ('failure','error','skipped'):suite.set(kind+'s'if kind!='skipped'else kind,str(counts[kind]))
        ET.ElementTree(newroot).write(public/'tests.xml',encoding='utf-8',xml_declaration=True)
    safe['public_report_counts']=dict(counts)
    safe['parameter_values_published']=False
    safe['raw_failure_bodies_published']=False
    (public/'run.json').write_text(json.dumps(safe,indent=2)+'\n',encoding='utf-8')
    for name in ('selection.json','collected_nodeids.json'):
        p=output/name
        if p.exists():
            items=json.loads(p.read_text(encoding='utf-8'))
            (public/name).write_text(json.dumps([public_node(x)for x in items],indent=2)+'\n',encoding='utf-8')
    (public/'pytest.log').write_text('Public CI summary only.\n'+json.dumps(dict(exit_code=run.get('exit_code'),counts=dict(counts)))+'\n',encoding='utf-8')
    return safe

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(publish(args.output)))
