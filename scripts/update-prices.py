#!/usr/bin/env python3
import os
import datetime


ONE_DAY = datetime.timedelta(days=1)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICE_PATH = os.path.join(ROOT_DIR, "ledger", "prices.beancount")


def yield_date_range(start_date, end_date):
    curr_date = start_date
    while curr_date <= end_date:
        if curr_date.weekday() < 5:
            yield curr_date
        curr_date += ONE_DAY


def main():
    with open(PRICE_PATH, "rb") as fhandler:
        fhandler.seek(-1000, os.SEEK_END)
        last_line = fhandler.readlines()[-1]
        last_date_str = last_line.split()[0].decode()
        last_date = datetime.datetime.strptime(last_date_str, "%Y-%m-%d")

    # 部分香港基金的净值更新时间比较慢，所以此处不用 last_date + 1
    start_date = last_date
    end_date = datetime.datetime.now() - ONE_DAY
    for curr_date in yield_date_range(start_date, end_date):
        print(
            f"PYTHONPATH=`pwd`/sources bean-price --no-cache -d {curr_date:%Y-%m-%d}"
            f" ledger/main.beancount >> ledger/prices.beancount;"
        )

def get_existed_symbol_dates(target_symbol):
    existed_date = set()
    with open(PRICE_PATH) as fhandler:
        for line in fhandler.readlines():
            dt, _, symbol, px, unit = line.split()
            if symbol != target_symbol:
                continue
            existed_date.add(dt)
    return existed_date


if __name__ == "__main__":
    main()
