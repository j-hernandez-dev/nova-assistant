"""Test-only one-shot CEF WebRTC feasibility. No Nova imports.
A numeric owned HTTP proxy supplies an offline loopback secure-context fixture.
Separate TCP destination canary and STUN/UDP canary distinguish broker traffic.
No production PUBLIC_ONLY claim: loopback fixture is a test topology exception.
"""
import argparse, ctypes as C, hashlib, http.server, json, os, socket, struct
import subprocess, threading, time, urllib.parse, uuid
from ctypes import wintypes as W
from pathlib import Path

k=C.WinDLL("kernel32",use_last_error=True)
ip=C.WinDLL("iphlpapi",use_last_error=True)
k.CreateEventW.argtypes=[C.c_void_p,W.BOOL,W.BOOL,W.LPCWSTR];k.CreateEventW.restype=W.HANDLE
k.CreateJobObjectW.argtypes=[C.c_void_p,W.LPCWSTR];k.CreateJobObjectW.restype=W.HANDLE
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
k.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD]
k.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE]
k.QueryInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p]
k.TerminateJobObject.argtypes=[W.HANDLE,W.UINT]
k.SetEvent.argtypes=[W.HANDLE];k.CloseHandle.argtypes=[W.HANDLE]
ip.GetExtendedUdpTable.argtypes=[C.c_void_p,C.POINTER(W.ULONG),W.BOOL,W.ULONG,C.c_int,W.ULONG]
class BasicLimits(C.Structure):
    _fields_=[("process_time",C.c_longlong),("job_time",C.c_longlong),("flags",W.DWORD),
              ("min_ws",C.c_size_t),("max_ws",C.c_size_t),("active_limit",W.DWORD),
              ("affinity",C.c_size_t),("priority",W.DWORD),("scheduling",W.DWORD)]
class IO(C.Structure):
    _fields_=[("a",C.c_ulonglong*6)]
class ExtendedLimits(C.Structure):
    _fields_=[("basic",BasicLimits),("io",IO),("process_mem",C.c_size_t),
              ("job_mem",C.c_size_t),("peak_process",C.c_size_t),("peak_job",C.c_size_t)]
class UdpRow(C.Structure):
    _fields_=[("address",W.DWORD),("port",W.DWORD),("pid",W.DWORD)]
def udp_owner(port):
    size=W.ULONG()
    ip.GetExtendedUdpTable(None,C.byref(size),False,socket.AF_INET,1,0)
    b=C.create_string_buffer(size.value)
    if ip.GetExtendedUdpTable(b,C.byref(size),False,socket.AF_INET,1,0)!=0:return None
    n=W.DWORD.from_buffer(b).value
    for i in range(n):
        row=UdpRow.from_buffer(b,4+i*C.sizeof(UdpRow))
        if socket.ntohs(row.port & 0xffff)==port:return int(row.pid)
    return None
def job_pids(job):
    b=C.create_string_buffer(8+8*256)
    if not k.QueryInformationJobObject(job,3,b,len(b),None):raise RuntimeError("JOB_QUERY_FAILED")
    n=W.DWORD.from_buffer(b,4).value
    return sorted(int(C.c_size_t.from_buffer(b,8+i*8).value) for i in range(min(n,256)))
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def main():
    a=argparse.ArgumentParser();a.add_argument("--root",required=True);a=a.parse_args()
    root=Path(a.root).resolve()
    if not root.name.startswith("ncef_") or not (root/"dist/include/cef_version.h").is_file():
        raise RuntimeError("INVALID_OWNED_HARNESS_ROOT")
    exe=root/"dist/Release/nova-cef-native-probe.exe"
    result={"schemaVersion":1,"probe":"CEF_WEBRTC_NATIVE_ONE_SHOT","startedUtc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
            "oneEngineRun":True,"productionPolicyUsed":False,"topology":"OFFLINE_LOOPBACK_FIXTURE_VIA_OWNED_PROXY_NOT_PUBLIC_ONLY_PROOF",
            "harnessExeSha256":sha(exe),"libcefSha256":sha(root/"dist/Release/libcef.dll")}
    datagrams=[];requests=[];reports=[];children=[];lines=[]
    capture=False;stop_udp=threading.Event();calibrated=threading.Event();report_ready=threading.Event()
    udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp.bind(("127.0.0.1",0));udp.settimeout(.2)
    stun_port=udp.getsockname()[1]
    def receive_udp():
        while not stop_udp.is_set():
            try:data,peer=udp.recvfrom(2048)
            except socket.timeout:continue
            except OSError:break
            cookie=len(data)>=20 and data[4:8]==b"\x21\x12\xa4\x42"
            row={"phase":"native" if capture else "calibration","timestampMonotonic":time.monotonic(),
                 "bytes":len(data),"sourcePort":peer[1],"ownerPid":udp_owner(peer[1]),
                 "stunBindingRequest":cookie and data[:2]==b"\x00\x01"}
            datagrams.append(row)
            if row["phase"]=="calibration":calibrated.set()
            if row["stunBindingRequest"]:
                port=peer[1]^0x2112
                addr=bytes(x^y for x,y in zip(socket.inet_aton(peer[0]),b"\x21\x12\xa4\x42"))
                attr=struct.pack("!HHBBH",0x0020,8,0,1,port)+addr
                udp.sendto(struct.pack("!HHI",0x0101,len(attr),0x2112a442)+data[8:20]+attr,peer)
    t=threading.Thread(target=receive_udp,daemon=True);t.start()
    sender=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sender.bind(("127.0.0.1",0))
    sender.sendto(struct.pack("!HHI",1,0,0x2112a442)+b"CALIBRATE001",udp.getsockname())
    if not calibrated.wait(2):raise RuntimeError("UDP_CANARY_NOT_CALIBRATED")
    result["canaryCalibration"]={"received":True,"ownerPidMatchesDriver":datagrams[0]["ownerPid"]==os.getpid(),
                                  "sourcePortMatches":datagrams[0]["sourcePort"]==sender.getsockname()[1]}
    sender.close()
    if not all(result["canaryCalibration"].values()):raise RuntimeError("UDP_CALIBRATION_OWNERSHIP_FAILED")
    class Target(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append({"kind":"DIRECT_TARGET_CANARY","timestampMonotonic":time.monotonic()})
            self.send_response(403);self.send_header("Content-Length","0");self.end_headers()
        def log_message(self,*args):pass
    target=http.server.ThreadingHTTPServer(("127.0.0.1",0),Target)
    target_port=target.server_address[1]
    fixture=("""<!doctype html><meta charset="utf-8"><title>Owned CEF RTC probe</title>
<script>
(async()=>{
const r={secureContext:isSecureContext,apiPresent:typeof RTCPeerConnection==='function',
constructed:false,dataChannelCreated:false,offerAccepted:false,candidates:0,gatheringComplete:false,error:false};
let pc;
try{
pc=new RTCPeerConnection({iceServers:[{urls:'stun:127.0.0.1:STUN_PORT'}]});
r.constructed=true; pc.createDataChannel('diagnostic');r.dataChannelCreated=true;
pc.onicecandidate=e=>{if(e.candidate)r.candidates++};
await pc.setLocalDescription(await pc.createOffer());r.offerAccepted=true;
await new Promise(resolve=>{
let ended=false;
const finish=()=>{if(!ended){ended=true;resolve()}};
pc.onicegatheringstatechange=()=>{if(pc.iceGatheringState==='complete'){r.gatheringComplete=true;finish()}};
setTimeout(finish,8000);
});
}catch(e){r.error=true}
await fetch('/report?data='+encodeURIComponent(JSON.stringify(r)),{cache:'no-store'});
if(pc)pc.close();
})();
</script>""").replace("STUN_PORT",str(stun_port)).encode()
    class Proxy(http.server.BaseHTTPRequestHandler):
        protocol_version="HTTP/1.1"
        def do_GET(self):
            p=urllib.parse.urlsplit(self.path)
            expected=not p.netloc or p.netloc==f"127.0.0.1:{target_port}"
            row={"kind":"OWNED_PROXY_REQUEST","pathClass":"/report" if p.path=="/report" else "/fixture" if p.path=="/fixture" else "other",
                 "timestampMonotonic":time.monotonic(),"exactFixtureOrigin":expected}
            requests.append(row)
            payload=b"";status=403
            if expected and p.path=="/fixture":payload=fixture;status=200
            elif expected and p.path=="/report":
                try:
                    q=json.loads(urllib.parse.parse_qs(p.query)["data"][0])
                    keys={"secureContext","apiPresent","constructed","dataChannelCreated","offerAccepted","candidates","gatheringComplete","error"}
                    if set(q)!=keys or any(not isinstance(v,(bool,int)) for v in q.values()):raise ValueError()
                    reports.append(q);status=204;report_ready.set()
                except (ValueError,KeyError,TypeError):row["invalidReport"]=True
            self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(payload)));self.send_header("Connection","close");self.end_headers()
            if payload:self.wfile.write(payload)
            self.close_connection=True
        def do_CONNECT(self):
            requests.append({"kind":"CONNECT_DENIED_UNRELATED","timestampMonotonic":time.monotonic()})
            self.send_response(403);self.send_header("Content-Length","0");self.end_headers()
        def log_message(self,*args):pass
    proxy_server=http.server.ThreadingHTTPServer(("127.0.0.1",0),Proxy)
    for server in (proxy_server,target):threading.Thread(target=server.serve_forever,daemon=True).start()
    suffix=uuid.uuid4().hex;start_name="Local\\ncef_"+suffix+"_start";stop_name="Local\\ncef_"+suffix+"_stop"
    start=k.CreateEventW(None,True,False,start_name);stop=k.CreateEventW(None,True,False,stop_name)
    job=k.CreateJobObjectW(None,None);limits=ExtendedLimits();limits.basic.flags=0x2000
    if not start or not stop or not job or not k.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)):
        raise RuntimeError("JOB_SETUP_FAILED")
    result["windowStartMonotonic"]=time.monotonic()
    profile=root/("profile_"+suffix[:8]);profile.mkdir(exist_ok=False)
    result["ownedProfileName"]=profile.name
    args=[str(exe),"--probe-root="+str(profile),"--probe-resources="+str(root/"dist/Resources"),
          f"--probe-url=http://127.0.0.1:{target_port}/fixture",
          f"--probe-proxy=http://127.0.0.1:{proxy_server.server_address[1]}",
          "--probe-start="+start_name,"--probe-stop="+stop_name]
    p=subprocess.Popen(args,cwd=str(exe.parent),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="replace")
    result["hostPid"]=p.pid
    # AssignProcessToJobObject requires PROCESS_SET_QUOTA (0x0100),
    # not PROCESS_SET_INFORMATION (0x0200). No privileged token is used.
    handle=k.OpenProcess(0x0100|0x0001|0x1000,False,p.pid)
    assigned=bool(handle and k.AssignProcessToJobObject(job,handle))
    if handle:k.CloseHandle(handle)
    if not assigned:
        p.terminate();p.wait();raise RuntimeError("PROCESS_JOB_ASSIGN_FAILED")
    capture=True;k.SetEvent(start)
    while not report_ready.is_set() and p.poll() is None and time.monotonic()-result["windowStartMonotonic"]<22:
        current=job_pids(job)
        children.append({"timestampMonotonic":time.monotonic(),"pids":current})
        report_ready.wait(.1)
    result["reportReceived"]=report_ready.is_set()
    result["ownedPidsBeforeStop"]=job_pids(job)
    k.SetEvent(stop)
    forced=False
    try:out,err=p.communicate(timeout=12)
    except subprocess.TimeoutExpired:
        forced=True;k.TerminateJobObject(job,93);out,err=p.communicate(timeout=5)
    result["exitCode"]=p.returncode;result["forcedJobTermination"]=forced
    for line in out.splitlines():
        try:
            item=json.loads(line)
            if isinstance(item,dict) and "kind" in item:lines.append(item)
        except ValueError:pass
    result["nativeEvents"]=lines;result["stderrLineCount"]=len(err.splitlines())
    result["stderrSha256"]=hashlib.sha256(err.encode()).hexdigest() if err else None
    # Query the job, not all processes on the computer.
    remaining=job_pids(job)
    if remaining:
        forced=True;k.TerminateJobObject(job,94)
        deadline=time.monotonic()+5
        while remaining and time.monotonic()<deadline:
            remaining=job_pids(job)
            if remaining:threading.Event().wait(.05)
    result["ownedPidsAfterStop"]=remaining
    result["forcedJobTermination"]=forced
    for h in (job,start,stop):k.CloseHandle(h)
    result["windowEndMonotonic"]=time.monotonic()
    capture=False;stop_udp.set();udp.close();t.join(1)
    for server in (proxy_server,target):server.shutdown();server.server_close()
    owned=set(pid for s in children for pid in s["pids"])|set(result["ownedPidsBeforeStop"])
    result["udpDatagrams"]=datagrams;result["ownedProcessSnapshots"]=children
    result["nativeStunDatagramsFromOwnedProcess"]=sum(x["phase"]=="native" and x["stunBindingRequest"] and x["ownerPid"] in owned for x in datagrams)
    result["nativeStunSourcePids"]=sorted({x["ownerPid"] for x in datagrams if x["phase"]=="native" and x["stunBindingRequest"] and x["ownerPid"] in owned})
    result["proxyRequests"]=requests;result["pageTelemetry"]=reports
    result["directHttpTargetHits"]=sum(x["kind"]=="DIRECT_TARGET_CANARY" for x in requests)
    result["cefWebRtcSuppression"]="FAIL" if reports and reports[0]["secureContext"] and result["nativeStunDatagramsFromOwnedProcess"] else "INCONCLUSIVE"
    result["finishedUtc"]=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
    print(json.dumps(result,separators=(",",":")))
if __name__=="__main__":main()
