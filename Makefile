# CC Token 儀表板 — 常用指令（make <目標>）
PY   ?= python3
PORT ?= 8787

.PHONY: help test run menubar quick-app app install-statusline clean

help:
	@echo 'CC Token 儀表板'
	@echo '  make test               煙霧測試（不需 Claude Code）'
	@echo '  make run                開瀏覽器儀表板 (PORT=$(PORT))'
	@echo '  make menubar            直接跑選單列（需 pip3 install rumps）'
	@echo '  make quick-app          產生免編譯 .app → dist/quick/'
	@echo '  make app                py2app 自包含 .app + .dmg → dist/'
	@echo '  make install-statusline 印出要貼進 ~/.claude/settings.json 的設定'
	@echo '  make clean'

test:
	bash packaging/smoke_test.sh

run:
	$(PY) src/cc_token_dashboard.py serve --port $(PORT)

menubar:
	$(PY) src/cc_token_dashboard.py menubar --port $(PORT)

quick-app:
	bash packaging/make_quick_app.sh

app:
	bash packaging/build_app.sh

install-statusline:
	@echo '把以下內容合併進 ~/.claude/settings.json：'
	@echo '{'
	@echo '  "statusLine": {'
	@echo '    "type": "command",'
	@echo '    "command": "python3 $(CURDIR)/src/cc_token_dashboard.py status"'
	@echo '  }'
	@echo '}'

clean:
	rm -rf build dist .build .build-venv *.egg-info packaging/build packaging/dist
