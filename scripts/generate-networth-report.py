#!/usr/bin/env python3
"""
计算每日投资盈亏和投资净值曲线
"""

import os
import csv
import datetime
import logging
import collections
import io
import decimal

import click
import pandas as pd
import beancount.loader
import beancount.core.data
from beancount.core import getters
from beancount.parser import options
from beancount.core import prices
from beancount.ops import holdings
from beancount.reports import holdings_reports


logger = logging.getLogger()


def get_account_map(entries):
    account_map = {}
    for entry in entries:
        if isinstance(entry, beancount.core.data.Open):
            account_map[entry.account] = entry
    return account_map


def get_ledger_file():
    this_file = os.path.abspath(__file__)
    workdir = os.path.dirname(this_file)
    while not os.path.exists(os.path.join(workdir, "ledger")):
        workdir = os.path.dirname(workdir)

    return os.path.join(workdir, "ledger", "main.beancount")


def compute_networth_series(since_date, end_date=None):
    if end_date is None:
        end_date = datetime.date.today()
    (entries, errors, options_map) = beancount.loader.load_file(get_ledger_file())
    account_map = get_account_map(entries)

    target_currency = 'CNY'
    curr_date = since_date

    result = []
    prev_networth = None
    prev_disposable_networth = None
    cum_invest_nav = decimal.Decimal("1.0")
    while curr_date < end_date:
        entries_to_date = [entry for entry in entries if entry.date <= curr_date]
        holdings_list, price_map_to_date = holdings_reports.get_assets_holdings(
            entries_to_date, options_map, target_currency
        )
        networth_in_cny = 0
        disposable_networth_in_cny = 0
        for hld in holdings_list:
            acc = account_map[hld.account]
            # 预付但大部分情况下不能兑现的沉没资产
            is_sunk = bool(int(acc.meta.get("sunk", 0)))

            # 不可支配
            nondisposable = bool(int(acc.meta.get("nondisposable", 0)))
            if not nondisposable:
                disposable_networth_in_cny += hld.market_value
            networth_in_cny += hld.market_value

        txs_of_date = [
            entry for entry in entries
            if entry.date == curr_date and
                isinstance(entry, beancount.core.data.Transaction)
        ]

        non_trade_expenses = 0
        non_trade_incomes = 0
        for tx in txs_of_date:
            for posting in tx.postings:
                acc = posting.account
                is_nt_exp = acc.startswith("Expenses:") and not acc.startswith("Expenses:Trade:")
                is_nt_inc = acc.startswith("Income:") and not acc.startswith("Income:Trade:")
                if is_nt_exp or is_nt_inc:
                    if posting.units.currency != target_currency:
                        base_quote = (posting.units.currency, target_currency)
                        _, rate = prices.get_latest_price(price_map_to_date, base_quote)
                    else:
                        rate = 1

                    if is_nt_exp:
                        non_trade_expenses += (posting.units.number * rate)
                    else:
                        non_trade_incomes -= (posting.units.number * rate)

        if prev_networth:
            pnl = networth_in_cny - non_trade_incomes + non_trade_expenses - prev_networth
            pnl_str = ("%.2f" % pnl) if not isinstance(pnl, str) else pnl
            pnl_rate_str = "%.4f%%" % (100 * pnl / prev_disposable_networth)
            cum_invest_nav *= (1 + pnl / prev_disposable_networth)
        else:
            pnl_str = 'n/a'
            pnl_rate_str = 'n/a'

        result.append({
            "日期": curr_date,
            # 净资产=资产 - 负债（信用卡）, 包含了沉没资产
            "净资产": "%.2f" % networth_in_cny,
            # 可投资金额=净资产 - 不可支配资产（公积金、预付房租、宽带)
            "可投资金额": "%.2f" % disposable_networth_in_cny,
            # Income:Trade(已了结盈亏、分红) 以外的 Income (包含公积金收入、储蓄利息)
            "非投资收入": "%.2f" % non_trade_incomes,
            # Expenses:Trade 以外的 Expenses (包含社保等支出)
            "非投资支出": "%.2f" % non_trade_expenses,
            "投资盈亏": pnl_str,
            # 投资盈亏% = 当日投资盈亏/昨日可投资金额
            "投资盈亏%": pnl_rate_str,
            "累计净值": "%.4f" % cum_invest_nav,
        })

        curr_date += datetime.timedelta(days=1)
        prev_networth = networth_in_cny
        prev_disposable_networth = disposable_networth_in_cny
    return result


def print_portfolio_csv(rows):
    fhandler = io.StringIO()
    writer = csv.DictWriter(fhandler, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    print(fhandler.getvalue())


@click.command()
@click.option('-s', '--since', default=None)
def main(since):
    if since is None:
        today = datetime.date.today()
        since_date = datetime.date(today.year, 1, 1)
    else:
        since_date = datetime.datetime.strptime(since, "%Y-%m-%d").date()

    rows = compute_networth_series(since_date)
    print_portfolio_csv(rows)


if __name__ == "__main__":
    main()
