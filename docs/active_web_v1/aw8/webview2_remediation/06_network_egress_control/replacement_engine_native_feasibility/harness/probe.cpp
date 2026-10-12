// Test-only native CEF C-API harness. No Nova product imports or IPC.
// Fixed-version headers and libcef.dll are required; no CEF wrapper or Electron.
#include <windows.h>
#include <shellapi.h>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <string>
#include "include/cef_api_hash.h"
#include "include/cef_version.h"
#include "include/capi/cef_app_capi.h"
#include "include/capi/cef_browser_capi.h"
#include "include/capi/cef_client_capi.h"
#include "include/capi/cef_command_line_capi.h"
#include "include/capi/cef_life_span_handler_capi.h"
#include "include/capi/cef_render_handler_capi.h"
#include "include/capi/cef_task_capi.h"

template<class T> struct StaticRef {
  T value{};
  std::atomic<int> refs{1};
  StaticRef() {
    value.base.size=sizeof(T);
    value.base.add_ref=[](cef_base_ref_counted_t* p) {
      reinterpret_cast<StaticRef<T>*>(p)->refs.fetch_add(1);
    };
    value.base.release=[](cef_base_ref_counted_t* p)->int {
      // Static handler lifetime is the executable lifetime, never a page lifetime.
      reinterpret_cast<StaticRef<T>*>(p)->refs.fetch_sub(1);
      return 0;
    };
    value.base.has_one_ref=[](cef_base_ref_counted_t* p)->int {
      return reinterpret_cast<StaticRef<T>*>(p)->refs.load()==1;
    };
    value.base.has_at_least_one_ref=[](cef_base_ref_counted_t* p)->int {
      return reinterpret_cast<StaticRef<T>*>(p)->refs.load()>=1;
    };
  }
};
static StaticRef<cef_app_t> app;
static StaticRef<cef_client_t> client;
static StaticRef<cef_life_span_handler_t> life;
static StaticRef<cef_render_handler_t> render;
static StaticRef<cef_task_t> poll_stop;
static cef_browser_t* owned_browser=nullptr;
static HANDLE stop_event=nullptr;
static std::wstring proxy;
static unsigned long long start_tick=0;
static bool closing=false;

static cef_string_t str(const std::wstring& s) {
  cef_string_t result{};
  static_assert(sizeof(wchar_t)==sizeof(char16_t));
  cef_string_utf16_set(reinterpret_cast<const char16_t*>(s.c_str()),s.size(),&result,1);
  return result;
}
static void set(cef_string_t& target,const std::wstring& s) {
  cef_string_utf16_set(reinterpret_cast<const char16_t*>(s.c_str()),s.size(),&target,1);
}
static void event(const char* kind) {
  std::printf("{\"kind\":\"%s\",\"pid\":%lu,\"tick\":%llu}\n",
              kind,GetCurrentProcessId(),GetTickCount64());
  std::fflush(stdout);
}
static void switch_value(cef_command_line_t* c,const wchar_t* key,const std::wstring& val) {
  auto k=str(key),v=str(val);
  c->append_switch_with_value(c,&k,&v);
  cef_string_utf16_clear(&k); cef_string_utf16_clear(&v);
}
static void switch_flag(cef_command_line_t* c,const wchar_t* key) {
  auto k=str(key); c->append_switch(c,&k); cef_string_utf16_clear(&k);
}
static void on_command(cef_app_t*,const cef_string_t* type,cef_command_line_t* c) {
  if(type && type->length) {
    std::wstring t(reinterpret_cast<const wchar_t*>(type->str),type->length);
    const char* label=t==L"utility"?"utility":t==L"renderer"?"renderer":t==L"gpu-process"?"gpu-process":"other";
    auto k=str(L"utility-sub-type");auto v=c->get_switch_value(c,&k);
    bool network=v && std::wstring(reinterpret_cast<const wchar_t*>(v->str),v->length)==L"network.mojom.NetworkService";
    std::printf("{\"kind\":\"SUBPROCESS_STARTED\",\"pid\":%lu,\"type\":\"%s\",\"networkService\":%s}\n",GetCurrentProcessId(),label,network?"true":"false");
    std::fflush(stdout);cef_string_utf16_clear(&k);
    if(v)cef_string_userfree_utf16_free(v);
    return;
  }
  // One immutable profile, not a security certificate.
  switch_value(c,L"proxy-server",proxy);
  switch_value(c,L"proxy-bypass-list",L"<-loopback>");
  switch_flag(c,L"disable-quic");
  switch_flag(c,L"disable-background-networking");
  switch_flag(c,L"disable-component-update");
  event("FIXED_PROXY_PROFILE_REQUESTED");
}
static void configure_handlers() {
  app.value.on_before_command_line_processing=on_command;
  client.value.get_life_span_handler=[](cef_client_t*)->cef_life_span_handler_t* {
    life.value.base.add_ref(&life.value.base); return &life.value;
  };
  client.value.get_render_handler=[](cef_client_t*)->cef_render_handler_t* {
    render.value.base.add_ref(&render.value.base); return &render.value;
  };
  life.value.on_after_created=[](cef_life_span_handler_t*,cef_browser_t* b) {
    b->base.add_ref(&b->base); owned_browser=b; event("BROWSER_CREATED");
  };
  life.value.on_before_close=[](cef_life_span_handler_t*,cef_browser_t*) {
    event("BROWSER_CLOSED");
    if(owned_browser){ owned_browser->base.release(&owned_browser->base); owned_browser=nullptr; }
    cef_quit_message_loop();
  };
  render.value.get_view_rect=[](cef_render_handler_t*,cef_browser_t*,cef_rect_t* r) {
    *r={0,0,800,600};
  };
  render.value.on_paint=[](cef_render_handler_t*,cef_browser_t*,cef_paint_element_type_t,
                          size_t,const cef_rect_t*,const void*,int,int) {};
  poll_stop.value.execute=[](cef_task_t*) {
    bool requested=stop_event && WaitForSingleObject(stop_event,0)==WAIT_OBJECT_0;
    if(!closing && (requested || GetTickCount64()-start_tick>30000)) {
      closing=true; event(requested?"ORDERLY_STOP_REQUESTED":"HARNESS_DEADLINE");
      if(owned_browser){
        auto h=owned_browser->get_host(owned_browser);
        h->close_browser(h,1); h->base.release(&h->base);
      }else{cef_quit_message_loop();}
    }else if(!closing){cef_post_delayed_task(TID_UI,&poll_stop.value,100);}
  };
}
int wmain(int argc,wchar_t** argv) {
  configure_handlers();
  const char* api=cef_api_hash(CEF_API_VERSION,0);
  if(!api || std::strcmp(api,CEF_API_HASH_PLATFORM)!=0){event("API_HASH_MISMATCH");return 21;}
  cef_main_args_t args{}; args.instance=GetModuleHandleW(nullptr);
  int sub=cef_execute_process(&args,&app.value,nullptr);
  if(sub>=0)return sub;
  std::wstring root,resources,url,gate,stop;
  for(int i=1;i<argc;i++){
    std::wstring a=argv[i];
    auto read=[&](const wchar_t* k,std::wstring& v){
      std::wstring prefix=std::wstring(L"--")+k+L"=";
      if(a.rfind(prefix,0)==0)v=a.substr(prefix.size());
    };
    read(L"probe-root",root);read(L"probe-resources",resources);read(L"probe-url",url);
    read(L"probe-proxy",proxy);read(L"probe-start",gate);read(L"probe-stop",stop);
  }
  if(root.empty()||resources.empty()||url.empty()||proxy.empty()||gate.empty()||stop.empty()){
    event("MISSING_HARNESS_ARGUMENT");return 22;
  }
  HANDLE start=OpenEventW(SYNCHRONIZE,FALSE,gate.c_str());
  if(!start || WaitForSingleObject(start,10000)!=WAIT_OBJECT_0){
    event("OWNERSHIP_START_GATE_FAILED");return 23;
  }
  CloseHandle(start); stop_event=OpenEventW(SYNCHRONIZE,FALSE,stop.c_str());
  if(!stop_event){event("STOP_GATE_FAILED");return 24;}
  event("OWNED_JOB_START_GATE_PASSED");
  cef_settings_t settings{};settings.size=sizeof(settings);
  // This executable has no CEF sandbox integration. Claim remains HOST_UNISOLATED.
  settings.no_sandbox=1;settings.windowless_rendering_enabled=1;
  set(settings.root_cache_path,root);set(settings.cache_path,root+L"\\Default");
  set(settings.resources_dir_path,resources);set(settings.locales_dir_path,resources+L"\\locales");
  settings.log_severity=LOGSEVERITY_INFO;
  set(settings.log_file,root+L"\\cef-startup.log");
  std::printf("{\"kind\":\"IDENTITY\",\"cef\":\"%s\",\"chromium\":\"154.0.8037.98\","
              "\"apiVersion\":%d,\"apiHash\":\"%s\",\"arch\":\"X64\","
              "\"noSandbox\":true,\"hostUnisolated\":true}\n",CEF_VERSION,CEF_API_VERSION,api);
  std::fflush(stdout);
  if(!cef_initialize(&args,&settings,&app.value,nullptr)){
    event("INITIALIZE_FAILED");return 25;
  }
  event("ENGINE_INITIALIZED");
  cef_window_info_t wi{};wi.size=sizeof(wi);wi.bounds={0,0,800,600};
  wi.windowless_rendering_enabled=1;wi.runtime_style=CEF_RUNTIME_STYLE_CHROME;
  cef_browser_settings_t bs{};bs.size=sizeof(bs);bs.windowless_frame_rate=15;
  auto u=str(url);
  auto created=cef_browser_host_create_browser_sync(&wi,&client.value,&u,&bs,nullptr,nullptr);
  cef_string_utf16_clear(&u);
  if(!created){event("CONTROL_CREATION_FAILED");cef_shutdown();return 26;}
  created->base.release(&created->base);
  start_tick=GetTickCount64();
  cef_post_delayed_task(TID_UI,&poll_stop.value,100);
  cef_run_message_loop();
  cef_shutdown();event("ENGINE_SHUTDOWN_CONFIRMED");
  CloseHandle(stop_event);
  cef_string_utf16_clear(&settings.root_cache_path);
  cef_string_utf16_clear(&settings.cache_path);
  cef_string_utf16_clear(&settings.resources_dir_path);
  cef_string_utf16_clear(&settings.locales_dir_path);
  cef_string_utf16_clear(&settings.log_file);
  return 0;
}
