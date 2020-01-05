all: prices

prices:
	./scripts/update-prices.py | sh
fava:
	fava ledger/main.beancount

%:
	bean-$@ ledger/main.beancount

portfolio:
	@./scripts/generate-portfolio.py

networth:
	@./scripts/generate-networth-report.py
