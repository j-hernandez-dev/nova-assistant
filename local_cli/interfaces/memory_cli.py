"""Minimal explicit CLI syntax. Parsing/presentation only, no store or policy."""
import json


def handle_memory_command(argument,client,write=print):
    parts=argument.strip().split(maxsplit=1)
    action=parts[0].lower() if parts else 'status'
    rest=parts[1] if len(parts)>1 else ''
    action='status' if action=='inspect' else action
    help_text=('Memory: status | list [JSON] | search <text> | show <id> | '
        'remember <JSON> | correct <JSON> | forget <JSON> | export [JSON] | '
        'proposals | confirm <JSON> | reject <JSON>. '
        'Proposal actions: {"jobId":"...","proposalId":"...","revision":3,"resolution":"supersede"}. '
        'JSON examples: {"kind":"PREFERENCE","text":"Short examples","scope":"WORKSPACE"}; '
        '{"memoryId":"...","revision":1,"text":"Corrected"}. '
        'Sensitive writes: consentSensitive:true for this exact action; inspection/export: includeSensitive:true. '
        'Forget does not erase audit, logs, source conversations or backups; no secure erase.')
    if action=='help':
        write(help_text); return
    try:
        if action in ('search','show') and rest.lstrip().startswith('{'): args=json.loads(rest)
        elif action=='search': args={'query':rest}
        elif action=='show': args={'memoryId':rest}
        else: args=json.loads(rest) if rest else {}
        if not isinstance(args,dict): raise ValueError()
        response=client.memory('memory_'+action,args)
        write(json.dumps(response,ensure_ascii=False,indent=2))
    except (ValueError,TypeError):
        write('MEMORY_UNTRUSTED_INPUT: Invalid memory command. '+help_text)
