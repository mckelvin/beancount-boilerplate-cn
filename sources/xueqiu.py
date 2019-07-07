import time
import json
import requests
from dateutil import tz,utils
from datetime import datetime

from beancount.core.number import D
from beancount.prices import source

EXPECTED_COLS = [
    "timestamp",
    "volume",
    "open",
    "high",
    "low",
    "close",
    "chg",
    "percent",
    "turnoverrate",
    "amount",
    "volume_post",
    "amount_post"
]
CN_TZ = tz.gettz("Asia/Shanghai")
NY_TZ = tz.gettz("America/New_York")


class Source(source.Source):
    """
    雪球 A股、港股、美股
    注意：需要在雪球标的前加国家(方便区分时区)

    PYTHONPATH=`pwd`/sources bean-price --no-cache -e CNY:xueqiu/CN:SH510300
    PYTHONPATH=`pwd`/sources bean-price --no-cache -e HKD:xueqiu/HK:02800
    PYTHONPATH=`pwd`/sources bean-price --no-cache -e USD:xueqiu/US:SPY
    """

    http = requests.Session()
    headers = requests.utils.default_headers()
    headers.update(
        {
            'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_3) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/73.0.3683.103 Safari/537.36'),
        }
    )
    http.get("https://xueqiu.com/", headers=headers)

    def get_historical_price(self, ticker, date):
        return self._get_daily_price(ticker, date)

    def get_latest_price(self, ticker):
        return self._get_daily_price(ticker)

    def _get_daily_price(self, ticker, date=None):
        region, symbol = ticker.split(":", 1)
        if region in {"HK", "CN"}:
            exchange_tz = CN_TZ
            if region == "HK":
                currency = "HKD"
            else:
                currency = "CNY"
        else:
            assert region == "US"
            exchange_tz = NY_TZ
            currency = "USD"
        if date is None:
            trade_date = utils.default_tzinfo(
                datetime.now(),
                exchange_tz,
            )
        else:
            trade_date = utils.default_tzinfo(
                datetime.combine(date, datetime.max.time()),
                exchange_tz
            )
        begin = int(time.mktime(trade_date.timetuple())) * 1000
        url = (
            f"https://stock.xueqiu.com/v5/stock/chart/kline.json?"
            f"symbol={symbol}&begin={begin}&period=day&"
            f"type=before&count=-1&indicator=kline"
        )

        resp = self.http.get(url, headers=self.headers)
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["error_code"] == 0, result["error_description"]
        bar = result["data"]["item"][0]
        assert result["data"]["column"] == EXPECTED_COLS
        returned_ts = bar[EXPECTED_COLS.index("timestamp")]
        close_price = D(
            bar[EXPECTED_COLS.index("close")]
        ).quantize(D('1.000000000000000000'))

        trade_date = datetime.fromtimestamp(returned_ts/1000, exchange_tz)
        return source.SourcePrice(close_price, trade_date, currency)
