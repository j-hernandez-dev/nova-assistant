"""Fixed known-value capture, not universal DLP or protection from the website."""
from uuid import uuid4
from local_cli.core.browser import BrowserActionError


class SensitiveCapture:
    def __init__(self, context, redactor):
        self.context, self.redactor = context, redactor
        self.binding = '__nova_sensitive_' + uuid4().hex
        self.failed, self.drafts = False, {}
        self.script = '''(() => {
          const send = globalThis[BINDING];
          const ids = new WeakMap(); let sequence = 0;
          const documentId = globalThis.crypto?.randomUUID?.() || String(Date.now()) + Math.random();
          const id = el => { if (!ids.has(el)) ids.set(el, documentId + ':' + (++sequence)); return ids.get(el); };
          const sensitive = el => el instanceof HTMLInputElement &&
            (el.type === 'password' || el.hasAttribute('data-nova-sensitive') ||
             ['current-password','new-password','one-time-code'].includes(el.autocomplete));
          const capture = () => Promise.all([...document.querySelectorAll('input')].filter(sensitive).map(el => send('commit', id(el), el.value)));
          document.addEventListener('input', e => { if (sensitive(e.target)) send('draft', id(e.target), e.target.value); }, true);
          document.addEventListener('change', e => { if (sensitive(e.target)) send('commit', id(e.target), e.target.value); }, true);
          document.addEventListener('submit', capture, true);
          globalThis.addEventListener('pagehide', capture, true);
          globalThis[CHECKPOINT] = capture;
        })();'''.replace('BINDING', repr(self.binding)).replace('CHECKPOINT', repr(self.binding + '_flush'))

    def install(self):
        def receive(source, phase, identity, value):
            if phase not in ('draft', 'commit') or not isinstance(identity, str) or len(identity) > 100 or not isinstance(value, str) or len(value) > 8192:
                self.failed = True
                raise BrowserActionError('SECRET_BOUNDARY_UNCONFIRMED', 'Sensitive input exceeded the bounded capture contract.')
            if phase == 'draft': self.drafts[identity] = value
            else:
                self.drafts.pop(identity, None)
                if value: self.redactor.register(value, protected=True)
        self.context.expose_binding(self.binding, receive)
        self.context.add_init_script(self.script)
        for page in self.context.pages:
            page.evaluate(self.script)

    def checkpoint(self, page):
        try:
            if len(page.frames) > 16: raise ValueError('too many frames')
            for frame in page.frames:
                frame.evaluate('(name) => { if (typeof globalThis[name] !== "function") throw Error("capture unavailable"); return globalThis[name](); }', self.binding + '_flush')
            if self.failed or self.drafts: raise ValueError('uncommitted sensitive state')
        except Exception:
            self.seal()
            raise BrowserActionError('SECRET_BOUNDARY_UNCONFIRMED', 'The sensitive-input checkpoint could not be confirmed. Browser control remains paused.') from None

    def seal(self):
        # Retirement preserves the latest known sensitive drafts, but never
        # manufactures a successful checkpoint or grants resume authority.
        for value in self.drafts.values():
            if value: self.redactor.register(value, protected=True)
        self.drafts.clear()
