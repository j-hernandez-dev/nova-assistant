"""Standalone native execution + read-only Windows PID/TCP observer.

Not a product runner or retry mechanism. Each named mode executes once.
Native Log + TCP snapshots + canaries are complementary, not universal packet
capture. Snapshot loss/DNS observer limitations must remain explicit.
"""
import ctypes
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

class Entry(ctypes.Structure):
    _fields_=[('size',w.DWORD),('usage',w.DWORD),('pid',w.DWORD),('heap',ctypes.c_size_t),
              ('module',w.DWORD),('threads',w.DWORD),('parent',w.DWORD),
              ('priority',w.LONG),('flags',w.DWORD),('exe',w.WCHAR*260)]

k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];k.CreateToolhelp32Snapshot.restype=w.HANDLE
k.Process32FirstW.argtypes=[w.HANDLE,ctypes.POINTER(Entry)];k.Process32NextW.argtypes=[w.HANDLE,ctypes.POINTER(Entry)]
k.CloseHandle.argtypes=[w.HANDLE]
ip=ctypes.WinDLL('iphlpapi')
ip.GetExtendedTcpTable.argtypes=[ctypes.c_void_p,ctypes.POINTER(w.DWORD),w.BOOL,w.ULONG,ctypes.c_int,w.ULONG]
ip.GetExtendedUdpTable.argtypes=[ctypes.c_void_p,ctypes.POINTER(w.DWORD),w.BOOL,w.ULONG,ctypes.c_int,w.ULONG]

def tree(parent, previous):
    handle=k.CreateToolhelp32Snapshot(2,0)
    if handle==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_last_error())
    entries=[];entry=Entry();entry.size=ctypes.sizeof(entry)
    try:
        ok=k.Process32FirstW(handle,ctypes.byref(entry))
        while ok:
            entries.append((entry.pid,entry.parent,entry.exe));ok=k.Process32NextW(handle,ctypes.byref(entry))
    finally:k.CloseHandle(handle)
    owned={parent}|set(previous)
    for _ in range(12):
        enlarged=owned|{pid for pid,ppid,_ in entries if ppid in owned}
        if enlarged==owned:break
        owned=enlarged
    live=[{'pid':pid,'parentPid':ppid,'image':exe} for pid,ppid,exe in entries if pid in owned]
    return owned,live

def tcp(owned):
    rows=[]
    for family,width,owner_offset,remote_port_offset in [(2,24,20,16),(23,56,52,44)]:
        size=w.DWORD(0);rc=ip.GetExtendedTcpTable(None,ctypes.byref(size),False,family,5,0)
        if rc not in (0,122):raise OSError(rc)
        data=ctypes.create_string_buffer(size.value);rc=ip.GetExtendedTcpTable(data,ctypes.byref(size),False,family,5,0)
        if rc:raise OSError(rc)
        raw=data.raw;count=int.from_bytes(raw[:4],'little')
        for i in range(count):
            row=raw[4+i*width:4+(i+1)*width]
            pid=int.from_bytes(row[owner_offset:owner_offset+4],'little')
            if pid in owned:
                port=int.from_bytes(row[remote_port_offset:remote_port_offset+2],'big')
                address=socket.inet_ntop(socket.AF_INET if family==2 else socket.AF_INET6,row[12:16] if family==2 else row[24:40])
                rows.append({'pid':pid,'family':family,'remotePort':port,'addressClass':'loopback' if address in ('127.0.0.1','::1') else 'other'})
    return rows

def udp(owned):
    rows=[]
    for family,width,owner_offset,port_offset in [(2,12,8,4),(23,28,24,20)]:
        size=w.DWORD(0);rc=ip.GetExtendedUdpTable(None,ctypes.byref(size),False,family,1,0)
        if rc not in (0,122):raise OSError(rc)
        data=ctypes.create_string_buffer(size.value);rc=ip.GetExtendedUdpTable(data,ctypes.byref(size),False,family,1,0)
        if rc:raise OSError(rc)
        raw=data.raw;count=int.from_bytes(raw[:4],'little')
        for i in range(count):
            row=raw[4+i*width:4+(i+1)*width];pid=int.from_bytes(row[owner_offset:owner_offset+4],'little')
            if pid in owned:rows.append({'pid':pid,'family':family,'localPort':int.from_bytes(row[port_offset:port_offset+2],'big')})
    return rows

def main():
    binary,root,mode,*label=sys.argv[1:]
    base=Path(root);run=base/(label[0] if label else mode)
    run.mkdir()  # Fresh or stop; never overwrite/rerun.
    env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMDATA')}
    start=datetime.now(timezone.utc).isoformat();clock=time.monotonic();observations=[];seen=set();errors=[]
    p=subprocess.Popen([binary,mode,str(run)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    live=[]
    while p.poll() is None:
        try:
            seen,live=tree(p.pid,seen);rows=tcp(seen);udp_rows=udp(seen)
            # Bounded metadata; no executable paths, credentials, packet bodies.
            if len(observations)<3000 and (rows or udp_rows or not observations):observations.append({'ms':round((time.monotonic()-clock)*1000,3),'tree':live,'tcp':rows,'udp':udp_rows})
        except OSError as e:errors.append({'kind':type(e).__name__,'winerror':getattr(e,'winerror',None)})
        if time.monotonic()-clock>180:
            # Guardrail, not retry. Preserve failure; kill only our owned probe.
            p.kill();errors.append({'kind':'HARNESS_TIME_LIMIT'});break
        time.sleep(.05)  # Observer cadence, never added to page/native critical path.
    out,err=p.communicate(timeout=10)
    report={'schemaVersion':1,'mode':mode,'processId':p.pid,'startUtc':start,'endUtc':datetime.now(timezone.utc).isoformat(),
            'durationSeconds':round(time.monotonic()-clock,3),'exitCode':p.returncode,
            'binarySha256':hashlib.sha256(Path(binary).read_bytes()).hexdigest(),'processTreeSnapshots':observations,'observerErrors':errors,
            'observationScope':'ToolHelp PID/tree + OWNER_PID IPv4/IPv6 TCP snapshots; NOT packet or DNS event history',
            'nativeEvidencePresent':(run/'native.json').is_file(),'stdoutPresent':bool(out),'stderrPresent':bool(err)}
    (run/'observer.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    # Do not print engine error pages, raw native log or auth information.
    print(json.dumps({k:report[k] for k in ('mode','exitCode','durationSeconds','nativeEvidencePresent','processId')}))
    return p.returncode

if __name__=='__main__':raise SystemExit(main())
