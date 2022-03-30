include Makefile.include

export

ifndef OPAMSWITCH
OPAMSWITCH=prism-8.10.2
endif

INSWITCH=$(shell opam switch show)
ifeq ($(INSWITCH),$(OPAMSWITCH))
INSWITCH=True
else
INSWITCH=False
endif

# build internal packages
.PHONY: install
install: venv_check venv
	echo "Installing project into virtual environment $(VENV)"
	pip install -e .

# test internal packages
test: venv_check venv switch_check
	echo "Running tests"
	pytest --pyargs --cov=prism prism


venv: $(VENV)/bin/activate

ifneq ($(SOFT),True)
.PHONY: requirements.txt
requirements.txt:
	touch requirements.txt
endif

ifneq ($(CONDA), True)
$(VENV)/bin/activate: requirements.txt
	test -d $(VENV) || virtualenv $(VENV) -p $(PEARLS_PYTHON)
	source $(VENV)/bin/activate && pip install -Ur requirements.txt
	touch $(VENV)/bin/activate
else
.PHONY: $(VENV)/bin/activate
$(VENV)/bin/activate: requirements.txt
	echo "Conda environment $(CONDA_DEFAULT_ENV) already activated."
endif

ifeq ($(INSWITCH),True)
switch_check:
else
switch_check:
	$(error You must activate the OPAM switch before making this target. $(n)    Call 'source $(GITROOT)/setup_coq.sh' to activate the project switch)
endif

clean:
	if [ $(INVENV) = "True" ] ; then \
	  echo "You must deactivate your virtual environment prior to cleaning."; \
	  exit 1; \
	else \
	  echo "Removing virtual environment: $(VENV)"; \
	fi
	rm -rf $(VENV)
	find -iname "*.pyc" -delete
	opam switch remove $(SWITCH_NAME)
