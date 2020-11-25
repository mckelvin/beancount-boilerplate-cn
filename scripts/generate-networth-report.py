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
import beancount.loader
import beancount.core.data
from beancount.core import prices
from beancount.ops.holdings import get_assets_holdings


logger = logging.getLogger()

KNOWN_ASSET_CLASSES = {
    "股权",
    "另类",
    "债权",
    "现金",
}
EXPENSES_PREFIX = "Expenses:"
EXPENSES_TRADE_PREFIX = "Expenses:Trade:"
EXPENSES_PREPAYMENTS_PREFIX = "Assets:PrePayments"


def get_maps(entries):
    account_map = {}
    commodity_map = {}
    for entry in entries:
        if isinstance(entry, beancount.core.data.Open):
            account_map[entry.account] = entry
        elif isinstance(entry, beancount.core.data.Commodity):
            commodity_map[entry.currency] = entry
    return account_map, commodity_map


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
    account_map, commodity_map = get_maps(entries)

    target_currency = 'CNY'
    curr_date = since_date

    result = []
    prev_networth = None
    prev_disposable_networth = None
    cum_invest_nav = decimal.Decimal("1.0")
    cum_invest_nav_ytd = decimal.Decimal("1.0")
    cum_invest_pnl = decimal.Decimal(0)
    cum_invest_pnl_ytd = decimal.Decimal(0)

    while curr_date <= end_date:
        entries_to_date = [entry for entry in entries if entry.date <= curr_date]
        holdings_list, price_map_to_date = get_assets_holdings(
            entries_to_date, options_map, target_currency
        )
        raw_networth_in_cny = decimal.Decimal(0)  # 包含sunk资产的理论净资产
        networth_in_cny = decimal.Decimal(0)  # 不包含sunk资产的净资产
        disposable_networth_in_cny = decimal.Decimal(0)
        dnw_by_asset_class = {}

        for hld in holdings_list:
            if hld.currency == "DAY":
                continue

            acc = account_map[hld.account]
            cmdt = commodity_map[hld.currency]
            if hld.market_value is None:
                raise ValueError(hld)

            raw_networth_in_cny += hld.market_value
            # 预付但大部分情况下不能兑现的沉没资产，比如预付的未来房租
            is_sunk = bool(int(acc.meta.get("sunk", 0)))
            if is_sunk:
                continue

            # 不可支配，比如房租押金
            nondisposable = bool(int(acc.meta.get("nondisposable", 0)))
            if not nondisposable:
                disposable_networth_in_cny += hld.market_value
                asset_class = cmdt.meta["asset-class"]
                if asset_class not in dnw_by_asset_class:
                    dnw_by_asset_class[asset_class] = decimal.Decimal(0)
                dnw_by_asset_class[asset_class] += hld.market_value

            networth_in_cny += hld.market_value

        txs_of_date = [
            entry for entry in entries
            if entry.date == curr_date and
                isinstance(entry, beancount.core.data.Transaction)
        ]

        non_trade_expenses = decimal.Decimal(0)
        non_trade_incomes = decimal.Decimal(0)
        for tx in txs_of_date:
            is_time_tx = any((posting.units.currency == "DAY" for posting in tx.postings))
            if is_time_tx:
                continue

            for posting in tx.postings:
                acc = posting.account
                is_non_trade_exp = (
                    acc.startswith(EXPENSES_PREFIX) and not acc.startswith(EXPENSES_TRADE_PREFIX)
                ) or (
                    acc.startswith(EXPENSES_PREPAYMENTS_PREFIX)
                )

                is_non_trade_inc = acc.startswith("Income:") and not acc.startswith("Income:Trade:")
                if is_non_trade_exp or is_non_trade_inc:
                    if posting.units.currency != target_currency:
                        base_quote = (posting.units.currency, target_currency)
                        _, rate = prices.get_latest_price(price_map_to_date, base_quote)
                    else:
                        rate = decimal.Decimal(1)

                    if is_non_trade_exp:
                        non_trade_expenses += (posting.units.number * rate)
                    else:
                        non_trade_incomes -= (posting.units.number * rate)

        if prev_networth:
            pnl = networth_in_cny - non_trade_incomes + non_trade_expenses - prev_networth
            pnl_str = ("%.2f" % pnl) if not isinstance(pnl, str) else pnl
            pnl_rate_str = "%.4f%%" % (100 * pnl / prev_disposable_networth)
            cum_invest_nav *= (1 + pnl / prev_disposable_networth)
            cum_invest_nav_ytd *= (1 + pnl / prev_disposable_networth)
            cum_invest_pnl += pnl
            cum_invest_pnl_ytd += pnl
        else:
            pnl = None
            pnl_str = 'n/a'
            pnl_rate_str = 'n/a'

        daily_status = {
            "日期": curr_date,
            # 理论净资产=总资产 - 负债
            "理论净资产": "%.2f" % raw_networth_in_cny,
            # 净资产=总资产' - 负债（信用卡）- 沉没资产
            "净资产": "%.2f" % networth_in_cny,
            "沉没资产": "%.2f" % (raw_networth_in_cny - networth_in_cny),
            # 可投资金额=净资产 - 不可支配资产（公积金、预付房租、宽带)
            "可投资净资产": "%.2f" % disposable_networth_in_cny,
            # Income:Trade(已了结盈亏、分红) 以外的 Income (包含公积金收入、储蓄利息)
            "非投资收入": "%.2f" % non_trade_incomes,
            # Expenses:Trade 以外的 Expenses (包含社保等支出)
            "非投资支出": "%.2f" % non_trade_expenses,
            "投资盈亏": pnl_str,
            # 投资盈亏% = 当日投资盈亏/昨日可投资金额
            "投资盈亏%": pnl_rate_str,
            "累计净值": "%.4f" % cum_invest_nav,
            "累计盈亏": "%.2f" % cum_invest_pnl,
            "当年净值": "%.4f" % cum_invest_nav_ytd,
            "当年盈亏": "%.2f" % cum_invest_pnl_ytd,
        }

        if curr_date.weekday() >= 5:
            if pnl is not None:
                assert pnl <= 0.01, daily_status  # 预期周末不应该有投资盈亏

        assert abs(sum(dnw_by_asset_class.values()) - disposable_networth_in_cny) < 1

        assert set(dnw_by_asset_class.keys()) <= KNOWN_ASSET_CLASSES, dnw_by_asset_class
        for asset_class in KNOWN_ASSET_CLASSES:
            propotion = 100 * dnw_by_asset_class.get(asset_class, 0) / disposable_networth_in_cny
            daily_status[f"{asset_class}%"] = f"{propotion:.2f}%"

        result.append(daily_status)


        next_date = curr_date + datetime.timedelta(days=1)
        if curr_date.year != next_date.year:
            cum_invest_nav_ytd = decimal.Decimal("1.0")
            cum_invest_pnl_ytd = decimal.Decimal(0)
        curr_date = next_date
        prev_networth = networth_in_cny
        prev_disposable_networth = disposable_networth_in_cny
    return result


def print_portfolio_csv(rows, transpose):
    fhandler = io.StringIO()
    writer = csv.DictWriter(fhandler, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    if not transpose:
        print(fhandler.getvalue().strip())
        return

    transposed = list(zip(*csv.reader(io.StringIO(fhandler.getvalue()))))
    t_fhandler = io.StringIO()
    csv.writer(t_fhandler).writerows(transposed)
    print(t_fhandler.getvalue().strip())

def add_padding(rows):
    curr_date = rows[-1]["日期"]
    empty_row = {key: "" for key, val in rows[-1].items()}
    while True:
        curr_date += datetime.timedelta(days=1)
        if (curr_date.month == 1 and curr_date.day == 1):
            break

        empty_row["日期"] = ""  # curr_date
        rows.append(empty_row.copy())
    return rows


@click.command()
@click.option('-s', '--since', default=None)
@click.option('--padding/--no-padding', default=False)
@click.option('--transpose/--no-transpose', default=False)
def main(since, padding, transpose):
    if since is None:
        today = datetime.date.today()
        since_date = datetime.date(today.year, 1, 1)
    else:
        since_date = datetime.datetime.strptime(since, "%Y-%m-%d").date()

    rows = compute_networth_series(since_date)
    if padding:
        rows = add_padding(rows)
    print_portfolio_csv(rows, transpose)


if __name__ == "__main__":
    main()
