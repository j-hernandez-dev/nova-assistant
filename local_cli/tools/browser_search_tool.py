"""Search with the owned browser, through the ordinary Browser ToolRuntime path."""
from local_cli.core.browser_search import BrowserSearchSettings
from local_cli.tools.browser_tools import BrowserTool


class BrowserSearchTool(BrowserTool):
    def __init__(self, *, settings=None, save=None, **kwargs):
        super().__init__('browser_navigate', **kwargs)
        self.settings = settings or BrowserSearchSettings()
        self._save = save

    @property
    def name(self): return 'web_search'

    @property
    def description(self):
        return ('Search the web using the selected browser and search engine. '
                'No SearXNG server or API key is needed. Returns titles, URLs and discovery snippets, '
                'not read articles. Open useful result URLs with browser_navigate to read and cite them. '
                'Use a public query; never include private files or credentials unless explicitly requested.')

    @property
    def parameters(self):
        return {'type': 'object', 'properties': {
            'query': {'type': 'string', 'description': 'Public search query, including dates when relevant; at most 500 characters.'},
            'max_results': {'type': 'integer', 'description': '1 to 5 results; default 5.'}},
            'required': ['query'], 'additionalProperties': False}

    def configure(self, state_dir):
        from local_cli.browser_search_config import load_settings, save_settings
        self.settings = load_settings(state_dir)
        self._save = lambda engine: save_settings(state_dir, engine)

    def set_engine(self, engine):
        candidate = BrowserSearchSettings(engine)
        if self._save is not None: self._save(engine)
        self.settings = candidate

    def state(self):
        browser = self.selection.state()
        return {'backend': 'browser', 'engine': self.settings.engine,
                'available': browser['available'], 'adapter': browser['adapter'], 'runtimeCheckedOnUse': True,
                'unavailableReason': browser['unavailableReason'],
                'serverRequired': False, 'networkIsolation': 'NOT_PROVIDED'}
