#!/usr/bin/env python3
"""
本脚本用来生成持仓CSV, 后续可以把CSV导入表格软件进一步聚合分析。
和 bean-report 相比主要的优先是：

- 输出带 meta 中自定义的名称，资产类别
- 过滤已支出不可退款的，预付款项
- 过滤不可支配资产
"""
import os
import csv
import datetime
import logging
import collections
import io

import click
import pandas as pd
import beancount.loader
import beancount.core.data
from beancount.core import getters
from beancount.reports import holdings_reports


logger = logging.getLogger()


def get_account_map(entries):
    account_map = {}
    for entry in entries:
        if isinstance(entry, beancount.core.data.Open):
            account_map[entry.account] = entry
    return account_map


def sort_key(row):
    """
    输出大体的风险系数以供排序
    """
    asset_class = row["一级类别"]
    asset_subclass = row["二级类别"]
    ac_list = ["现金", "债券", "基金", "股票", "另类资产"]
    asc_list = [
        "本币", "外汇", "债券基金", "可转换债券", "指数基金",
        "偏股混合基金", "中国股票", "香港股票", "美国股票", "贵金属",
        "加密货币"
    ]
    factor1 = ac_list.index(asset_class)
    factor2 = asc_list.index(asset_subclass)
    return (1 + factor1) * 100 + factor2


def get_ledger_file():
    this_file = os.path.abspath(__file__)
    workdir = os.path.dirname(this_file)
    while not os.path.exists(os.path.join(workdir, "ledger")):
        workdir = os.path.dirname(workdir)

    return os.path.join(workdir, "ledger", "main.beancount")


def get_portfolio_matrix(asof_date=None):
    """
    打印持仓
    Args:
        asof_date: 计算该日为止的持仓, 避免未来预付款项影响。
    """
    if asof_date is None:
        asof_date = datetime.date.today()

    (entries, errors, option_map) = beancount.loader.load_file(get_ledger_file())
    entries = [entry for entry in entries if entry.date <= asof_date]

    assets_holdings, price_map = holdings_reports.get_assets_holdings(entries, option_map)
    account_map = get_account_map(entries)
    commoditiy_map = getters.get_commodity_map(entries, create_missing=False)

    holding_groups = {}
    for holding in assets_holdings:
        account_obj = account_map[holding.account]
        if account_obj is None:
            raise ValueError("account is not defined for %s" % holding)
        currency_obj = commoditiy_map[holding.currency]
        if currency_obj is None:
            raise ValueError("commoditiy is not defined for %s" % holding)
        if bool(int(account_obj.meta.get("sunk", 0))):
            logger.warn(f"{account_obj.account} is an sunk. Ignored.")
            continue
        if bool(int(account_obj.meta.get("nondisposable", 0))):
            logger.warn(f"{account_obj.account} is nondisposable. Ignored.")
            continue

        for meta_field in ("name", "asset-class", "asset-subclass"):
            if meta_field not in currency_obj.meta:
                raise ValueError(
                    "Commodity %s has no '%s' in meta"
                    "" % (holding.currency, meta_field)
                )

        account_name = account_obj.meta["name"]
        account_nondisposable = bool(int(account_obj.meta.get("nondisposable", 0)))
        symbol_name = currency_obj.meta["name"]
        asset_class = currency_obj.meta["asset-class"]
        asset_subclass = currency_obj.meta["asset-subclass"]
        symbol = holding.currency
        currency = holding.cost_currency
        price = holding.price_number
        price_date = holding.price_date
        if price is None:
            if symbol == currency:
                price = 1
                price_date = ''
        qty = holding.number
        if currency == "CNY":
            cny_rate = 1
        else:
            cny_rate = price_map[(currency, "CNY")][-1][1]

        # 2. bloomberg_symbol
        holding_dict = {
            "account": account_name,
            "nondisposable": account_nondisposable,
            "symbol": symbol,
            "symbol_name": symbol_name,
            "asset_class": asset_class,
            "asset_subclass": asset_subclass,
            "quantity": qty,
            "currency": currency,
            "price": price,
            "price_date": price_date,
            "cny_rate": cny_rate,
        }
        group_key = (symbol, account_nondisposable)
        holding_groups.setdefault(group_key, []).append(holding_dict)

    rows = []
    cum_networth = 0
    for (symbol, account_nondisposable), holdings in holding_groups.items():
        qty_by_account = {}
        for holding in holdings:
            if holding["account"] not in qty_by_account:
                qty_by_account[holding["account"]] = 0
            qty_by_account[holding["account"]] += holding["quantity"]

        total_qty = sum(qty_by_account.values())
        holding0 = holdings[0]

        networth = holding["cny_rate"] * holding["price"] * total_qty
        cum_networth += networth
        row = {
            "一级类别": holding["asset_class"],
            "二级类别": holding["asset_subclass"],
            "标的": holding["symbol_name"],
            "代号": symbol,
            "可支配": "是" if not account_nondisposable else "否",
            "持仓量": "%.3f" % total_qty,
            "市场价格": "%.4f" % holding["price"],
            "报价日期": holding["price_date"],
            "市场价值": int(round(holding["price"] * total_qty)),
            "货币": holding["currency"],
            "人民币价值": "%.2f" % networth,
        }
        rows.append(row)
    rows.sort(key=sort_key)
    return rows, cum_networth


def print_portfolio_csv(rows):
    fhandler = io.StringIO()
    writer = csv.DictWriter(fhandler, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    print(fhandler.getvalue())


@click.command()
@click.option('-d', '--date', default=None)
def main(date):
    logging.basicConfig(level=logging.INFO)
    if date is None:
        asof_date = datetime.date.today()
    else:
        asof_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()

    rows, cum_networth = get_portfolio_matrix(asof_date)
    logger.info("As of %s, disposable networth=%d CNY", asof_date, cum_networth)
    print_portfolio_csv(rows)


if __name__ == "__main__":
    main()
