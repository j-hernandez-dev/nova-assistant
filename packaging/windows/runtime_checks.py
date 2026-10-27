"""Explicit installer verification. No user data, model or external website."""
import io
import sqlite3
import sys


def runtime_info():
    import numpy
    import pypdf
    from local_cli import __version__
    from local_cli.tools.browser_tools import browser_package_root
    stream = io.BytesIO()
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(stream)
    assert len(pypdf.PdfReader(stream).pages) == 1
    assert numpy.dot([1, 2], [3, 4]) == 11
    with sqlite3.connect(':memory:') as connection:
        assert connection.execute('select 1').fetchone() == (1,)
    root = browser_package_root()
    return dict(status='PASS', version=__version__, frozen=bool(getattr(sys, 'frozen', False)),
                python=sys.version.split()[0], numpy=numpy.__version__, pypdf=pypdf.__version__,
                pdfRoundTrip=True, numpyNativeMath=True, sqlite=True,
                browserPresent=all((root / p).is_file() for p in
                    ['host/nova-webview-host.exe', 'runtime/msedgewebview2.exe', 'python/playwright/driver/node.exe']))


def check_browser():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    from local_cli.tools.browser_tools import browser_package_root
    from local_cli.infrastructure.browser.windows_webview2 import WebView2BrowserSession
    class Fixture(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'<title>Nova packaged browser check</title><input id="value"><p>Owned offline fixture</p>'
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session = WebView2BrowserSession(browser_package_root(), timeout=40)
    try:
        session.start()
        session.navigate('http://127.0.0.1:' + str(server.server_port) + '/owned.html')
        assert session.page.title() == 'Nova packaged browser check'
        session.page.locator('#value').fill('bundle-ok')
        assert session.page.locator('#value').input_value() == 'bundle-ok'
        version = session.ready.runtime_version
    finally:
        closed = session.close()
        server.shutdown()
        server.server_close()
        thread.join(2)
    assert closed.host_exited and closed.job_empty and closed.profile_removed and not closed.errors
    return dict(status='PASS', engine='WebView2', runtimeVersion=version,
                ownedLoopbackNavigation=True, formRoundTrip=True,
                hostExited=closed.host_exited, jobEmpty=closed.job_empty,
                profileRemoved=closed.profile_removed, externalWebsite=False)
