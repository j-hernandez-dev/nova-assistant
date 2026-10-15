"""One host-owned Browser choice shared by tools and product roots."""
from local_cli.application.browser import BrowserUnavailable
from local_cli.browser_config import BROWSERS, load_browser, save_browser


class BrowserSelection:
    def __init__(self, discover, create, *, selected='webview2'):
        if selected not in BROWSERS: raise ValueError('Invalid browser')
        self.selected, self._discover, self._create = selected, discover, create
        self._save = None

    def configure(self, state_dir):
        self.selected = load_browser(state_dir)
        self._save = lambda selected: save_browser(state_dir, selected)

    def choices(self): return self._discover()

    def validate(self, selected):
        if selected not in BROWSERS: raise ValueError('Choose webview2, chrome, or edge.')
        choice = next(row for row in self.choices() if row['browser'] == selected)
        if not choice['available']:
            raise BrowserUnavailable(choice['reason'], choice['message'])
        return choice

    def select(self, selected):
        self.validate(selected)
        if self._save is not None: self._save(selected)
        self.selected = selected

    def create(self):
        choice = self.validate(self.selected)
        return self._create(choice)

    def state(self):
        choices = self.choices()
        selected = next(row for row in choices if row['browser'] == self.selected)
        return {'selected': self.selected, 'available': selected['available'],
                'unavailableReason': selected['reason'], 'adapter': selected['adapter'],
                'runtimeCheckedOnUse': True, 'networkIsolation': 'NOT_PROVIDED',
                'controlClass': 'HOST_UNISOLATED', 'choices': choices}
