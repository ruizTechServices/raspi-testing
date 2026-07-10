from __future__ import annotations

from flask import Blueprint, jsonify, request

from unified_server.integrations.apod import ApodClient
from unified_server.integrations.crypto import CryptoPriceClient
from unified_server.integrations.currency import CurrencyClient
from unified_server.integrations.http import IntegrationError
from unified_server.integrations.network import PublicIpClient
from unified_server.integrations.weather import WeatherClient
from unified_server.settings import get_settings


def build_integrations_blueprint(
    weather: WeatherClient | None = None,
    network: PublicIpClient | None = None,
    crypto: CryptoPriceClient | None = None,
    currency: CurrencyClient | None = None,
    apod: ApodClient | None = None,
) -> Blueprint:
    """Public read-only widget endpoints proxying free public APIs.

    Same auth posture as /api/system/temperature: no key required, covered by
    the app-wide rate limit. Proxying keeps CORS trivial, caches responses,
    and keeps the NASA key server-side.
    """
    bp = Blueprint("integrations", __name__)
    weather = weather or WeatherClient()
    network = network or PublicIpClient()
    crypto = crypto or CryptoPriceClient()
    currency = currency or CurrencyClient()
    apod = apod or ApodClient()

    @bp.get("/api/integrations/weather")
    def integrations_weather():
        try:
            return jsonify({"status": "ok", **weather.snapshot()})
        except IntegrationError as exc:
            return jsonify({"error": f"Weather is unavailable: {exc}"}), 503

    @bp.get("/api/integrations/network/public-ip")
    def integrations_public_ip():
        try:
            return jsonify({"status": "ok", **network.public_ip()})
        except IntegrationError as exc:
            return jsonify({"error": f"Public IP lookup failed: {exc}"}), 503

    @bp.get("/api/integrations/crypto/prices")
    def integrations_crypto_prices():
        try:
            return jsonify({"status": "ok", **crypto.prices()})
        except IntegrationError as exc:
            return jsonify({"error": f"Crypto prices are unavailable: {exc}"}), 503

    @bp.get("/api/integrations/currency/convert")
    def integrations_currency_convert():
        amount = request.args.get("amount", type=float)
        from_currency = request.args.get("from", default=get_settings().CURRENCY_DEFAULT_BASE)
        to_currency = request.args.get("to", default="")
        if amount is None:
            return jsonify({"error": "amount must be a positive number."}), 400
        try:
            return jsonify({"status": "ok", **currency.convert(amount, from_currency, to_currency)})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except IntegrationError as exc:
            return jsonify({"error": f"Currency conversion is unavailable: {exc}"}), 503

    @bp.get("/api/integrations/apod")
    def integrations_apod():
        try:
            return jsonify({"status": "ok", **apod.picture_of_the_day()})
        except IntegrationError as exc:
            return jsonify({"error": f"NASA picture of the day is unavailable: {exc}"}), 503

    return bp
