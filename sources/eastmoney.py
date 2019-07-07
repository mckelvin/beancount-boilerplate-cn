import time
import re
import logging
import json
import requests
from dateutil import tz,utils
from datetime import datetime
from urllib import error
from math import log10, floor

from beancount.core.number import D
from beancount.prices import source
from beancount.utils import net_utils


CN_TZ = tz.gettz("Asia/Shanghai")


class Source(source.Source):
    """
    东方财富天天基金基金净值
    注意：需要在雪球标的前加F(方便区分基金与其他标的)

    PYTHONPATH=`pwd`/sources bean-price --no-cache -e CNY:eastmoney/F110011
    """

    http = requests.Session()

    def get_historical_price(self, ticker, date):
        return self._get_daily_price(ticker, date)

    def get_latest_price(self, ticker):
        return self._get_daily_price(ticker)

    def _get_daily_price(self, fund, date=None):
        assert fund[0] == "F"
        params = {
            "callback": "thecallback",
            "fundCode": fund[1:],
            "pageIndex": 1,
            "pageSize": 1,

        }
        if date is not None:
            dt_str = date.strftime("%Y-%m-%d")
            params.update({
                "startDate": dt_str,
                "endDate": dt_str,
            })
        resp = self.http.get(
            "https://api.fund.eastmoney.com/f10/lsjz",
            params=params,
            headers={
                "Referer": "http://fundf10.eastmoney.com/jjjz_{fund}.html"
            }
        )
        assert resp.status_code == 200, resp.text
        result_str = next(re.finditer("thecallback\((.*)\)", resp.text)).groups()[0]
        result = json.loads(result_str)
        trade_date = result["Data"]["LSJZList"][0]["FSRQ"]
        nav = D(result["Data"]["LSJZList"][0]["DWJZ"]).quantize(D('1.000000000000000000'))
        trade_date = datetime.strptime(trade_date, "%Y-%m-%d")
        trade_date = utils.default_tzinfo(trade_date, CN_TZ)

        return source.SourcePrice(nav, trade_date, 'CNY')
