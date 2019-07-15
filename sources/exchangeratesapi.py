import time
import json
import requests
from dateutil import tz,utils
from datetime import datetime

from beancount.core.number import D
from beancount.prices import source


class Source(source.Source):
    """
    PYTHONPATH=`pwd`/sources bean-price --no-cache -e CNY:exchangeratesapi/USDCNY
    """

    http = requests.Session()

    def get_historical_price(self, ticker, date=None):
        return self._get_daily_price(ticker, date)

    def get_latest_price(self, ticker):
        return self._get_daily_price(ticker)

    def _get_daily_price(self, ticker, date=None):
        assert len(ticker) == 6, ticker
        base = ticker[:3]
        symbol = ticker[3:]
        if date is None:
            date_str = "latest"
        else:
            date_str = date.strftime("%Y-%m-%d")

        resp = self.http.get(
            "https://api.exchangeratesapi.io/" + date_str,
            params={
                "symbols": symbol,
                "base": base,
            }
        )
        result = resp.json()

        close_price = D(result["rates"][symbol]).quantize(D('1.000000000000000000'))
        trade_date = utils.default_tzinfo(
            datetime.strptime(result["date"], "%Y-%m-%d"),
            tz.UTC
        )
        currency = base
        return source.SourcePrice(close_price, trade_date, currency)
