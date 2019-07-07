all: prices

prices:
	PYTHONPATH=`pwd`/sources bean-price -i ledger/main.beancount >> ledger/prices.beancount
