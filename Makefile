# --------------------------------------------------------------- utils

.PHONY: fmt # format and remove unused imports
fmt:
	pip install isort
	isort .
	pip install autoflake
	autoflake --remove-all-unused-imports --recursive --in-place .

	pip install ruff
	ruff format --config line-length=500 .

.PHONY: sec # check for common vulnerabilities
sec:
	pip install bandit
	pip install safety
	
	bandit -r .
	safety check --full-report

.PHONY: reqs # generate requirements.txt file
reqs:
	pip install pipreqs
	rm -rf requirements.txt
	pipreqs .

.PHONY: up # pull remote changes and push local changes
up:
	git pull
	git add .
	@if [ -z "$(msg)" ]; then \
		git commit -m "up"; \
	else \
		git commit -m "$(msg)"; \
	fi
	git push

# --------------------------------------------------------------- conda

# workaround because makefile executes each line of the recipe in a separate sub-shell
.ONESHELL:
SHELL = /bin/bash
CONDA_DEACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda deactivate
CONDA_ACTIVATE_BASE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda activate base
CONDA_ACTIVATE_CON = source $$(conda info --base)/etc/profile.d/conda.sh ; conda activate con

.PHONY: conda-install # install conda environment from scratch and export it
conda-install:
	# conda config --env --set subdir osx-64
	# conda config --env --set subdir osx-arm64
	conda config --set auto_activate_base false
	conda info

	$(CONDA_ACTIVATE_BASE)
	conda create --yes --name con python=3.11

	$(CONDA_ACTIVATE_CON)
	pip install --upgrade pip
	pip install --upgrade setuptools
	pip install --upgrade wheel

	pip install clip flax jax numpy tensorflow clu dataclasses scipy torchvision pillow torch torchvision timm tqdm opencv-python transformers eagerpy tensorboard matplotlib torchsummary pandas
	# pip install cudatoolkit cudnn

	conda env export --name con > conda-environment.yml
	$(CONDA_DEACTIVATE)
	conda remove --yes --name con --all

.PHONY: conda-install-snapshot # install conda environment from yaml file
conda-install-snapshot:
	$(CONDA_ACTIVATE_BASE)
	conda env create --file conda-environment.yml

	@echo "to activate the conda environment, run: 'conda activate con'"
	@echo "to deactivate the conda environment, run: 'conda deactivate'"

.PHONY: conda-clean # remove conda environment
conda-clean:
	conda remove --yes --name con --all
	conda env list

# --------------------------------------------------------------- help

.PHONY: help # generate help message
help:
	@grep '^.PHONY: .* #' Makefile | sed 's/\.PHONY: \(.*\) # \(.*\)/\1	\2/' | expand -t20
