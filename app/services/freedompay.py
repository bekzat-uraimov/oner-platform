"""FreedomPay client. The gateway's ugliness — form-data in, XML out, MD5
signatures instead of an API key — is contained here so the rest of the app only
ever sees Python objects.

Docs: freedompay.kz/docs-en/merchant-api (same API on .kg / .uz)
"""

import hashlib
import secrets
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

from app.core.config import get_settings


# FreedomPay truncates or rejects overlong descriptions; do it ourselves so the
# signature matches whatever they actually store.
MAX_DESCRIPTION = 255

# pg_result in a result callback. Anything but PAID leaves the money unclaimed.
RESULT_FAILED = "0"
RESULT_PAID = "1"
RESULT_INCOMPLETE = "2"


class FreedomPayError(Exception):
    """The gateway rejected the request or answered with something unusable."""


@dataclass(frozen=True)
class PaymentInit:
    payment_id: str
    redirect_url: str


def script_name(url: str) -> str:
    """The signature's first component: the last path segment of the endpoint.

    For our outgoing call that's `init_payment.php`; when verifying FreedomPay's
    call to our result_url it's that URL's last segment instead. Getting this
    wrong is the #1 integration bug, so both sides go through this function.
    """
    return urlparse(url).path.rsplit("/", 1)[-1]


def make_sig(script: str, params: dict[str, str], secret: str) -> str:
    values = [str(params[k]) for k in sorted(params) if k != "pg_sig"]
    return hashlib.md5(";".join([script, *values, secret]).encode()).hexdigest()


def verify_sig(script: str, params: dict[str, str], secret: str) -> bool:
    sent = params.get("pg_sig")
    if not sent:
        return False
    return secrets.compare_digest(sent, make_sig(script, params, secret))


def build_response(
    script: str, secret: str, *, status: str, description: str | None = None
) -> str:
    """The signed XML FreedomPay expects back from our result_url."""
    params = {"pg_status": status, "pg_salt": secrets.token_hex(8)}
    if description is not None:
        # A rejection's reason is shown to the buyer; an error's is for FreedomPay.
        key = "pg_description" if status == "rejected" else "pg_error_description"
        params[key] = description
    params["pg_sig"] = make_sig(script, params, secret)

    root = ElementTree.Element("response")
    for key, value in params.items():
        ElementTree.SubElement(root, key).text = value
    return ElementTree.tostring(root, encoding="unicode")


def parse_init(body: str) -> PaymentInit:
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as e:
        raise FreedomPayError(f"unparseable gateway response: {e}") from e

    if root.findtext("pg_status") != "ok":
        code = root.findtext("pg_error_code", "")
        desc = root.findtext("pg_error_description", "")
        raise FreedomPayError(f"init_payment rejected: {code} {desc}".strip())

    payment_id = root.findtext("pg_payment_id")
    redirect_url = root.findtext("pg_redirect_url")
    if not payment_id or not redirect_url:
        raise FreedomPayError("init_payment returned no payment id or redirect url")
    return PaymentInit(payment_id=payment_id, redirect_url=redirect_url)


class FreedomPayClient:
    def __init__(
        self,
        *,
        merchant_id: str,
        secret_key: str,
        init_url: str,
        result_url: str,
        success_url: str,
        failure_url: str,
        testing_mode: int,
        timeout: float,
    ):
        self.merchant_id = merchant_id
        self.secret_key = secret_key
        self.init_url = init_url
        self.result_url = result_url
        self.success_url = success_url
        self.failure_url = failure_url
        self.testing_mode = testing_mode
        # One client, one connection pool. A fresh httpx.post() per checkout
        # would redo the TLS handshake on every single purchase.
        self.http = httpx.Client(timeout=timeout)

    def init_payment(
        self,
        *,
        order_id: int,
        amount: Decimal,
        currency: str,
        description: str,
    ) -> PaymentInit:
        # Without creds the signature is meaningless and we'd still fire a real
        # request at the live gateway. Fail here instead of on their side.
        if not self.merchant_id or not self.secret_key:
            raise FreedomPayError("FreedomPay credentials are not configured")

        params = {
            "pg_merchant_id": self.merchant_id,
            "pg_order_id": str(order_id),
            "pg_amount": f"{amount:.2f}",
            "pg_currency": currency,
            "pg_description": description[:MAX_DESCRIPTION],
            "pg_salt": secrets.token_hex(8),
            "pg_result_url": self.result_url,
            "pg_success_url": self.success_url,
            "pg_failure_url": self.failure_url,
            # Capture immediately instead of leaving card payments authorized.
            "pg_auto_clearing": "1",
            "pg_testing_mode": str(self.testing_mode),
            # pg_payment_system stays unset on purpose: FreedomPay's hosted page
            # then offers every method the merchant agreement enables.
        }
        params["pg_sig"] = make_sig(
            script_name(self.init_url), params, self.secret_key
        )

        res = self.http.post(self.init_url, data=params)
        res.raise_for_status()
        return parse_init(res.text)


@lru_cache
def get_gateway() -> FreedomPayClient:
    s = get_settings()
    return FreedomPayClient(
        merchant_id=s.freedompay_merchant_id,
        secret_key=s.freedompay_secret_key,
        init_url=s.freedompay_init_url,
        result_url=s.freedompay_result_url,
        success_url=s.freedompay_success_url,
        failure_url=s.freedompay_failure_url,
        testing_mode=s.freedompay_testing_mode,
        timeout=s.freedompay_timeout_s,
    )
