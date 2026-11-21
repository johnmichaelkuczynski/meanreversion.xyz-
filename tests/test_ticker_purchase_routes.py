import os
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

from ticker_purchase_routes import (
    INTENT_COOKIE, PurchaseStart, PurchaseLeave, departure_url, read_intent,
)


class PurchaseRouteTests(AsyncHTTPTestCase):
    def get_app(self):
        self.environment = patch.dict(os.environ, {"SESSION_SECRET": "unit-test-signing-only"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        return Application([
            (r"/api/full-access/start", PurchaseStart),
            (r"/api/full-access/leave", PurchaseLeave),
        ], cookie_secret="unit-test-signing-only")

    def test_intent_is_signed_httponly_and_survives_a_new_session(self):
        response = self.fetch("/api/full-access/start?ticker=MSFT", follow_redirects=False)
        assert response.code == 302 and response.headers["Location"] == "/"
        header = response.headers["Set-Cookie"]
        assert "HttpOnly" in header and "SameSite=Lax" in header
        value = header.split(";", 1)[0].split("=", 1)[1].strip('"')
        assert read_intent({INTENT_COOKIE: value}) == "MSFT"
        assert read_intent({INTENT_COOKIE: value + "tampered"}) is None

    def test_cross_site_intent_is_rejected(self):
        response = self.fetch("/api/full-access/start?ticker=MSFT",
                              headers={"Sec-Fetch-Site": "cross-site"}, follow_redirects=False)
        assert response.code == 403

    def test_checkout_redirect_requires_signature_and_stripe_host(self):
        for destination in ("https://checkout.stripe.com/c/pay/fixture", "/",
                            "/?requested_ticker=MSFT&checkout_error=1"):
            response = self.fetch(departure_url(destination), follow_redirects=False)
            assert response.code == 302 and response.headers["Location"] == destination
            assert INTENT_COOKIE in response.headers["Set-Cookie"]
        bad = self.fetch(departure_url("https://example.test"), follow_redirects=False)
        assert bad.code == 400
        url = departure_url("https://checkout.stripe.com/c/pay/fixture")
        token = parse_qs(urlsplit(url).query)["destination"][0]
        bad = self.fetch("/api/full-access/leave?destination=" + token + "x", follow_redirects=False)
        assert bad.code == 400
