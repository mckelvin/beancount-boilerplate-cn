# beancount-boilerplate-cn

本项目是为如下人士准备的 (AND)

- 生活、工作在中国
- 熟练使用 \*nix 环境下终端操作
- 对[文本记账](https://plaintextaccounting.org/)感兴趣
- 看过了最基础的 beancount 介绍但是没有看完所有文档（太多了）
- 想马上试试用 beancount 记账

### 安装

1. Python 3.6.5
如果你已经安装了 [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv), 那需要一个基于 Python 3.6.5 的虚拟环境，否则请自行准备 Python 3.6.5 运行环境:

```shell
pyenv virtualenv 3.6.5 beancount-env
```

2. 安装依赖的库

```shell
pip install -r requirements.txt
```

### 这份模板中的假定使用者是这样的:

- 有如下银行的储蓄卡
	- 招商银行 (工资卡)
	- 招商银行香港分行
- 有如下银行的全币种信用卡
	- 浦发银行 (日常消费主力卡, 外币交易自动购汇人民币还款)
	- 工商银行 (境外消费为主，外币交易不自动购汇，需要自行购汇还外币)
- 有如下投资(机)账户
	- 富途证券港美股账户
	- 东方财富证券A股账户
	- 蚂蚁财富(支付宝)基金账户
	- 天天基金账户

### 如何初始化/已有帐本迁移过来

可见 `ledger/init.beancount` 文件中初始化的过程

### Commodity 命名

每一个投资标的就是一个commodity, 比如现金 CNY, USD, 股票 SPY, AAPL ...

- 各国外汇按标准名称来：
	- `CNY`, `USD`, `CNH`, ...
- 美股代号按交易所代码来
	- `AAPL`, `GOOGL`
- 港股代号以 `HK_` 开头按 4 位数字命名
	- `HK_2800`, `HK_0700`
- A股(含场内基金)代号以 `CN_` 开头按 6 位数字命名
	- `CN_000001`, `CN_510300`, ...
- 场外基金(货币基金除外)以 `CN_F` 开头按 6 位数字命名
	- `CN_F110011`
- 货币基金直接用 CNY 表示，收益需要手工更新(原因是货币基金无净值的概念)。
	- CNY

### 你可能想批量替换的关键字
  - 帐本名称 `YourLedger`
  - 所在城市 `YourCity`
  - 供职单位 `YourEmployer`
  - `XXX`
  - `TODO`

### 文件布局

- importers/ : 通过 bean-extract 自动导入帐单所需的自定义脚本
- raw-data/ : csv 等格式的原始帐单存放目录
- sources/ : 自定义的股票、基金行情脚本（默认只支持从雅虎财经中获取）
- ledger/ : 所有的 beancount 文件都在这里面
    - main.beancount : 主入口
	- account.beancount : 所有的账户定义在这里
	- commodity.beancount : 如果你不需要自动获取行情价格，你甚至都不需要这个文件 
	- prices.beancount : 这个文件由 bean-price 命令管理，一般不需要手动修改
	- init.beancount : 初始化帐本用
	- salary.beancount : 工资收入
	- invest.beancount : 现金之外的投资(机)相关记录(买卖、申赎)
	- daily/ : 日常流水
		- daily/2019 : 按年分目录
		- daily/2019/2019-07-03-spdbccc.beancount : 主力消费卡记录(自动生成+人工修改)
		- daily/2019/2019-07-03-other.beancount : 非主力下记录
		- daily/2019/2019-07-03-settle.beancount : 定期结算检查点

### 支出如何分类

- 参照随手记App的支出分类法, 分为2级, 见 ledger/account.beancount
  中账户的定义。

### 如何处理五险一金

- 公司缴纳的公积金作为收入计算
- 公司缴纳的各种险不入帐
- 个人缴纳的各种税和险作为支出计算
- 个人缴纳的公积金当作转帐计算
- 详见 salary.beancount

### 如何处理股票、基金

- 因为交易频率不高，因此数据都是手工输入
- 可参见 invest.beancount 中的定义

### 如何获取外汇、股票、基金行情

- ledger/commodity.beancount 中定义了某一个 commodity 从哪里获取行情
- 自定义行情脚本定义在 sources/ , 目前支持从雪球获取A/港/美股股票行情，从天天基金获取基金行情
- 货币基金当现金处理

### 如何获取标的的最新价格

```
make prices
```
### 如何自动生成帐单

基于2019年5月的帐单(csv格式)生成 beancount 文件

```
bean-extract importers/spdccc_importer.py raw-data/spdbcc/2019-05-spdbcc.csv > ledger/daily/2019/2019-06-03-spdbcc.beancount
```
