"""Explicit TTY host controls; no file or source ownership in the CLI."""
import json
from pathlib import Path


def handle_knowledge_command(argument, console, *, attach=False):
    try:
        if attach:
            old_ids={r['sourceId'] for r in console.snapshot().services.get('knowledge',{}).get('attachmentRefs',[])}
            # The whole remainder is a literal path (spaces supported), no shell.
            path = argument.strip().strip('"')
            if not path: raise ValueError()
            result = console.knowledge('source_import', {'path':str(Path(path).expanduser().absolute())})
        else:
            parts=argument.strip().split(maxsplit=1)
            name=parts[0] if parts else 'list'
            arg=parts[1] if len(parts)>1 else ''
            if name=='detach': console._attachment_refs=[]; return
            if name=='cancel':
                result=console.knowledge('source_cancel', {'operationId':arg})
            elif name=='import':
                result=console.knowledge('source_import',{'path':str(Path(arg.strip('"')).expanduser().absolute()),'scope':'WORKSPACE'})
            elif name in ('promote','delete'):
                result=console.knowledge('source_'+name, {'sourceId':arg})
            elif name=='detail':result=console.knowledge('source_detail',{'sourceId':arg})
            elif name=='url':result=console.knowledge('source_import_url',{'url':arg,'scope':'WORKSPACE'})
            elif name in ('refresh','refresh-url','export'):
                source_id,value=arg.split(maxsplit=1)
                result=console.knowledge({'refresh':'source_refresh','refresh-url':'source_refresh_url','export':'source_export'}[name],
                    {'sourceId':source_id,'url' if name=='refresh-url' else 'path':value.strip('"') if name=='refresh-url' else str(Path(value.strip('"')).expanduser().absolute())})
            elif name=='remote':
                source_id,choice=arg.split(maxsplit=1)
                if choice not in ('on','off'):raise ValueError()
                result=console.knowledge('source_remote',{'sourceId':source_id,'allowed':choice=='on'})
            elif name=='select':
                refs=console.snapshot().services.get('knowledge',{}).get('attachmentRefs',[])
                selected=[r for r in refs if r['sourceId']==arg]
                if not selected: raise ValueError()
                console._attachment_refs=selected
                return
            elif name in ('list','status'): result=console.knowledge('source_'+name,{})
            else: raise ValueError()
        if result.get('accepted') and result.get('createdIds',{}).get('operationId'):
            completed=console.wait_for_operation(result['createdIds']['operationId'])
            refs=console.snapshot().services.get('knowledge',{}).get('attachmentRefs',[])
            if attach: console._attachment_refs=[r for r in refs if r['sourceId'] not in old_ids and r['state'] in ('READY','PARTIAL')]
        console._write(json.dumps(completed.payload.get('result',{}).get('data') if 'completed' in locals() and
            getattr(completed,'payload',{}).get('result',{}).get('data') is not None else
            console.snapshot().services.get('knowledge',{}),ensure_ascii=False)+'\n')
        if not result.get('accepted'): console._write(result['error']['code']+'\n')
    except (ValueError,TypeError):
        console._write('Usage: /attach <path>; /source list|status|import <path>|url <URL>|detail|select|promote|delete <sourceId>|refresh|refresh-url|export <sourceId> <path/URL>|remote <sourceId> on|off|cancel <operationId>|detach\n')
