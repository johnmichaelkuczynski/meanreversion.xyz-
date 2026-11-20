"""Serve the already-installed chart runtime without a third-party CDN."""

from functools import lru_cache
from tornado.web import RequestHandler


@lru_cache(maxsize=1)
def plotly_runtime():
    from plotly.offline import get_plotlyjs
    return get_plotlyjs()


class PlotlyRuntime(RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/javascript; charset=utf-8")
        self.set_header("Cache-Control", "public, max-age=86400")
        self.set_header("X-Content-Type-Options", "nosniff")
        self.finish(plotly_runtime())
