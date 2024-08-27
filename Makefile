# --------------------------------------------------------------- venv

.PHONY: init # initialize venv
init:
	# get requirements.in
	pip install pip --upgrade
	pip install pipreqs
	rm -rf requirements.txt requirements.in
	pipreqs . --mode no-pin --encoding latin-1
	mv requirements.txt requirements.in

	# get requirements.txt
	pip install pip-tools
	pip-compile requirements.in -o requirements.txt -vvv
	
	# install everything in venv
	rm -rf .venv
	python3 -m venv .venv
	@bash -c "source .venv/bin/activate && pip install -r requirements.txt"

.PHONY: lock # freeze pip and lock reqs
lock:
	@bash -c "source .venv/bin/activate && pip freeze > requirements.in"
	pip-compile requirements.in -o requirements.txt

# --------------------------------------------------------------- nohup

.PHONY: monitor # create nohup with restart on failure
monitor:
	@if [ "$(filepath)" = "" ]; then echo "missing 'filepath' argument"; exit 1; fi

	# @runtime="./.venv/bin/python3";
	@runtime="python3"; \
	monitor() { \
		while true; do \
			if ! pgrep -f "$(filepath)" > /dev/null; then \
				echo "$$(date): process died, restarting..." >> monitor.log; \
				rm -rf "monitor-process.log"; \
				rm -rf "monitor-process.pid"; \
				$$runtime "$(filepath)" >> "monitor-process.log" 2>&1 & \
				echo $$! > "monitor-process.pid"; \
			fi; \
			sleep 5; \
		done; \
	}; \
	monitor >> "monitor.log" 2>&1 & \
	echo $$! > "monitor.pid"; \
	echo "$$(date): started" >> "monitor.log"

.PHONY: monitor-tail # tail log of nohup process
monitor-tail:
	while true; do clear; tail -n 100 monitor-process.log; sleep 0.1; done
	# watch -n 0.1 "tail -n 100 monitor-process.log"

.PHONY: monitor-kill # kill nohup process
monitor-kill:
	-kill -9 $$(cat monitor.pid)
	rm -rf monitor.pid
	rm -rf monitor.log
	-kill -9 $$(cat monitor-process.pid)
	rm -rf monitor-process.pid
	rm -rf monitor-process.log

# --------------------------------------------------------------- utils

.PHONY: fmt # format codebase
fmt:
	pip install isort
	pip install ruff
	pip install autoflake

	isort .
	autoflake --remove-all-unused-imports --recursive --in-place .
	ruff format --config line-length=500 .

.PHONY: sec # check for vulns
sec:
	pip install bandit
	pip install safety
	
	bandit -r .
	safety check --full-report

.PHONY: up # pull and push changes
up:
	git pull
	git add .
	if [ -z "$(msg)" ]; then git commit -m "up"; else git commit -m "$(msg)"; fi
	git push

.PHONY: help # generate help message
help:
	@echo "Usage: make [target]\n"
	@grep '^.PHONY: .* #' Makefile | sed 's/\.PHONY: \(.*\) # \(.*\)/\1	\2/' | expand -t20
