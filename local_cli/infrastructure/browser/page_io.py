"""Common Playwright page IO, independent of the browser launcher/platform."""
from urllib.parse import urlsplit
from local_cli.application.browser import BrowserNavigation, BrowserRead, BrowserUnavailable

_BODY_READ = """(element, limit) => {
 const text = element.innerText || '';
 return {text: text.slice(0, limit), truncated: text.length > limit};
}"""


class PlaywrightPageIO:
    def navigate(self, url):
        try:
            p = urlsplit(url) if isinstance(url, str) else None
            if (p is None or len(url) > 8192 or p.scheme not in ('http', 'https')
                    or not p.hostname or p.username is not None or p.password is not None):
                raise ValueError()
        except ValueError as exc:
            raise BrowserUnavailable('INVALID_URL', 'Navigation requires an HTTP or HTTPS URL without embedded credentials.') from exc
        page = self._active_page()
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=self.timeout * 1000)
            return BrowserNavigation(page.url[:8192], page.title()[:1024])
        except Exception as exc:
            raise BrowserUnavailable('NAVIGATION_FAILED', 'The browser could not finish navigation before its deadline.') from exc

    def read(self, *, max_chars=16000):
        if type(max_chars) is not int or not 1 <= max_chars <= 32000:
            raise ValueError('max_chars must be between 1 and 32000')
        page = self._active_page()
        try:
            result = page.locator('body').evaluate(_BODY_READ, max_chars, timeout=self.timeout * 1000)
            return BrowserRead(page.url[:8192], page.title()[:1024], result['text'][:max_chars], bool(result['truncated']))
        except Exception as exc:
            raise BrowserUnavailable('READ_FAILED', 'The browser could not read the current page before its deadline.') from exc
