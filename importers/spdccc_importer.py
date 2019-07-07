from beancount.ingest.importers import csv
from beancount.core.data import Posting



COMPACT_CATE_DICT = {
    "滴滴,嘀嘀,天津舒行科技,CAB": "Transport:Taxi",
    "药房,医院,医药,DRUG": "Health:Drugs",
    "交通卡,地铁,摩拜": "Transport:Public",
    "铁路,上铁": "Leisure:Train",
    "联合网络,中国移动": "Comm:PhonePlan",
    "宽带,VPS,Hosting": "Comm:Internet",
    "顺丰": "Comm:Express",
    "全家,便利,果品,果业,生鲜,水果": "Food:FruitSnacks",
    "餐厅,包子铺,名吃,小吃,餐饮,面馆,"
        "盒马,豆浆": "Food:Meals",
    "优衣库": "Clothes:Clothes",
    "发型,美发": "Health:HairCutting",
    "AVIATION,航空": "Leisure:Aviation",
    "日上": "Leisure:Souvenir",
    "Smart2Pay B.V.": "Leisure:Gaming",
    "京东,宜家": "Home:Groceries",
    "电力公司": "Home:Utilities",
    "Spotify": "Leisure:Media",
}

CATE_DICT = {
    kw: cate_vals
    for kws, cate_vals in COMPACT_CATE_DICT.items()
    for kw in kws.split(",")
}


def _get_category(narration, default_cate="TODO"):
    for kw in CATE_DICT:
        if kw in narration:
            return CATE_DICT[kw]

    return default_cate


def categorizer(txn):
    assert len(txn.postings) == 1, txn
    post = txn.postings[0]
    if post.units.number < 0:
        # 支出
        category = _get_category(txn.narration)
        txn.postings.append(post._replace(
            account=f"Expenses:{category}",
            units=-post.units,
        ))
    elif post.units.number > 0:
        if "还款" in txn.narration:
            txn.postings.append(post._replace(
                account=f"Assets:CN:Saving:CMB:CNY",
                units=-post.units,
            ))
        else:
            extra_narration = " TODO"
            if "返现" in txn.narration:
                extra_narration = ""

            txn.postings.append(post._replace(
                account=post.account.replace("Liabilities", "Income"),
                units=-post.units,
            ))
            if extra_narration:
                txn = txn._replace(narration=txn.narration + extra_narration)
    return txn


CONFIG = [
    csv.Importer(
        {
            # 日期、金额等字段分别叫什么？
            csv.Col.DATE: '记账日期',
            csv.Col.AMOUNT_DEBIT: '交易金额',
            csv.Col.NARRATION1: '交易描述',
            csv.Col.LAST4: '卡号末四位'
        },
        # CSV文件中有哪几列？
        regexps='卡号末四位,记账日期,交易金额,交易描述',
        account="Liabilities:CN:CreditCard:SPDB",
        currency='CNY',
        categorizer=categorizer,
    )
]
