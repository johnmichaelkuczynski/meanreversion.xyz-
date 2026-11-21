"""Browser-local purchase intent; native Google OAuth and Stripe stay unchanged."""
import os
from urllib.parse import urlencode, urlsplit

from tornado.web import RequestHandler, create_signed_value, decode_signed_value

INTENT_COOKIE = "mr_full_access_intent"
DESTINATION = "mr_checkout_destination"
MAX_AGE_DAYS = 15 / (24 * 60)


def read_intent(cookies):
    secret = os.environ.get("SESSION_SECRET", "")
    if not secret:
        return None
    value = decode_signed_value(
        secret, INTENT_COOKIE, cookies.get(INTENT_COOKIE, ""),
        max_age_days=MAX_AGE_DAYS,
    )
    return value.decode() if value else None


def departure_url(destination):
    """Only server-signed, short-lived destinations may leave the purchase flow."""
    value = create_signed_value(
        os.environ["SESSION_SECRET"], DESTINATION, destination,
    ).decode()
    return "/api/full-access/leave?" + urlencode({"destination": value})


class PurchaseStart(RequestHandler):
    def get(self):
        if self.request.headers.get("Sec-Fetch-Site") == "cross-site":
            self.send_error(403)
            return
        symbol = self.get_argument("ticker", "").strip().upper()
        # The value is a display/request intent, never a payment entitlement.
        if not symbol or len(symbol) > 16 or any(
            char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for char in symbol
        ):
            self.send_error(400)
            return
        self.set_signed_cookie(
            INTENT_COOKIE, symbol, expires_days=MAX_AGE_DAYS,
            httponly=True, secure=self.request.headers.get(
                "X-Forwarded-Proto", self.request.protocol,
            ) == "https", samesite="Lax", path="/",
        )
        self.redirect("/")


class PurchaseLeave(RequestHandler):
    def get(self):
        value = decode_signed_value(
            self.application.settings["cookie_secret"], DESTINATION,
            self.get_argument("destination", ""), max_age_days=MAX_AGE_DAYS,
        )
        if not value:
            self.send_error(400)
            return
        destination = value.decode()
        parsed = urlsplit(destination)
        home = (parsed.path == "/" and not parsed.scheme and not parsed.netloc
                and not parsed.fragment)
        if not home and not (
            parsed.scheme == "https" and parsed.hostname == "checkout.stripe.com"
            and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
        ):
            self.send_error(400)
            return
        self.clear_cookie(INTENT_COOKIE, path="/")
        self.redirect(destination)
