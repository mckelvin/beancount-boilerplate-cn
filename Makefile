GDOCIDFILE=local/gdocid
GDOCID=`cat $(GDOCIDFILE)`
TODAY=`date "+%Y-%m-%d"`
MONTH=`date "+%Y-%m"`
DIARY_MD_PATH=`date "+raw-data/.notable/notes/diary/%Y/%m/%Y-%m-%d.md"`
PFCSV="local/portfolio-$(TODAY).csv"
NWCSV="local/net-worth-$(TODAY).csv"


all: prices

prices-today:
	./scripts/update-prices.py --today-only | sh

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

gdocid:
	@test -f $(GDOCIDFILE) && true || (echo "Please fill gdoc id in $(GDOCIDFILE)"; exit 1)

spreadsheet: gdocid
	@echo "Generating $(PFCSV) ..."
	@./scripts/generate-portfolio.py > $(PFCSV)
	@echo "$(PFCSV) Done\n"
	@echo "Generating $(NWCSV) ..."
	@./scripts/generate-networth-report.py --padding --since 2019-10-01 > $(NWCSV)
	@echo "$(NWCSV) Done\n"
	@egrep "^(日期|$(MONTH))" $(NWCSV) | column -ts,
	@echo "Uploading to spreadsheet ..."
	@upload-to-sheets --docid=$(GDOCID) $(PFCSV):持仓 $(NWCSV):净值

today:
	make prices-today
	make spreadsheet

backup:
	git stash
	git pull --rebase origin master
	git stash pop
	git add .
	git commit -m "AutoBackup"
	git push origin master
