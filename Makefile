
# Included custom configs change the value of MAKEFILE_LIST
# Extract the required reference beforehand so we can use it for help target
MAKEFILE_NAME := $(word $(words $(MAKEFILE_LIST)),$(MAKEFILE_LIST))
# Include custom config if it is available
-include Makefile.config

# Application
APP_ROOT    := $(abspath $(lastword $(MAKEFILE_NAME))/..)
APP_NAME    := video-result-viewer
APP_VERSION ?= $(shell cat $(APP_ROOT)/VERSION)
APP_INI     ?= $(APP_ROOT)/config/$(APP_NAME).ini

# guess OS (Linux, Darwin,...)
OS_NAME := $(shell uname -s 2>/dev/null || echo "unknown")
CPU_ARCH := $(shell uname -m 2>/dev/null || uname -p 2>/dev/null || echo "unknown")

# conda
CONDA_ENV_NAME ?= $(APP_NAME)
CONDA_HOME     ?= $(HOME)/.conda
CONDA_ENVS_DIR ?= $(CONDA_HOME)/envs
CONDA_ENV_PATH := $(CONDA_ENVS_DIR)/$(CONDA_ENV_NAME)
# allow pre-installed conda in Windows bash-like shell
ifeq ($(findstring MINGW,$(OS_NAME)),MINGW)
  CONDA_BIN_DIR ?= $(CONDA_HOME)/Scripts
else
  CONDA_BIN_DIR ?= $(CONDA_HOME)/bin
endif
CONDA_BIN := $(CONDA_BIN_DIR)/conda
CONDA_ENV_REAL_TARGET_PATH := $(realpath $(CONDA_ENV_PATH))
CONDA_ENV_REAL_ACTIVE_PATH := $(realpath ${CONDA_PREFIX})

# environment already active - use it directly
ifneq ("$(CONDA_ENV_REAL_ACTIVE_PATH)", "")
  CONDA_ENV_MODE := [using active environment]
  CONDA_ENV_NAME := $(notdir $(CONDA_ENV_REAL_ACTIVE_PATH))
  CONDA_CMD :=
endif
# environment not active but it exists - activate and use it
ifneq ($(CONDA_ENV_REAL_TARGET_PATH), "")
  CONDA_ENV_NAME := $(notdir $(CONDA_ENV_REAL_TARGET_PATH))
endif
# environment not active and not found - create, activate and use it
ifeq ("$(CONDA_ENV_NAME)", "")
  CONDA_ENV_NAME := $(APP_NAME)
endif
# update paths for environment activation
ifeq ("$(CONDA_ENV_REAL_ACTIVE_PATH)", "")
  CONDA_ENV_MODE := [will activate environment]
  CONDA_CMD := source "$(CONDA_BIN_DIR)/activate" "$(CONDA_ENV_NAME)";
endif
# override conda command as desired
CONDA_COMMAND ?= undefined
CONDA_SETUP := 1
ifneq ("$(CONDA_COMMAND)","undefined")
  CONDA_SETUP := 0
  CONDA_ENV_MODE := [using overridden command]
  CONDA_CMD := $(CONDA_COMMAND)
endif

DOWNLOAD_CACHE ?= $(APP_ROOT)/downloads
REPORTS_DIR ?= $(APP_ROOT)/reports
PYTHON_VERSION ?= `python -c 'import platform; print(platform.python_version())'`

# choose conda installer depending on your OS
CONDA_URL = https://repo.continuum.io/miniconda
ifeq ("$(OS_NAME)", "Linux")
  FN := Miniconda3-latest-Linux-x86_64.sh
else ifeq ("$(OS_NAME)", "Darwin")
  FN := Miniconda3-latest-MacOSX-x86_64.sh
else
  FN := unknown
endif

## --- Informative targets --- ##

.PHONY: all
all: help

# Auto documented help targets & sections from comments
#	- detects lines marked by double octothorpe (#), then applies the corresponding target/section markup
#   - target comments must be defined after their dependencies (if any)
#	- section comments must have at least a double dash (-)
#
# 	Original Reference:
#		https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
# 	Formats:
#		https://misc.flogisoft.com/bash/tip_colors_and_formatting
_SECTION := \033[34m
_TARGET  := \033[36m
_NORMAL  := \033[0m
_SPACING := 24
.PHONY: help
# note: use "\#\#" to escape results that would self-match in this target's search definition
help:	## print this help message (default)
	@echo "$(_SECTION)=== $(APP_NAME) help ===$(_NORMAL)"
	@echo "Please use 'make <target>' where <target> is one of:"
#	@grep -E '^[a-zA-Z_-]+:.*?\#\# .*$$' $(MAKEFILE_LIST) \
#		| awk 'BEGIN {FS = ":.*?\#\# "}; {printf "    $(_TARGET)%-24s$(_NORMAL) %s\n", $$1, $$2}'
	@grep -E '\#\#.*$$' "$(APP_ROOT)/$(MAKEFILE_NAME)" \
		| awk ' BEGIN {FS = "(:|\-\-\-)+.*?\#\# "}; \
			/\--/ 		{printf "$(_SECTION)%s$(_NORMAL)\n", $$1;} \
			/:/   		{printf "   $(_TARGET)%-$(_SPACING)s$(_NORMAL) %s\n", $$1, $$2;} \
			/\-only:/   {gsub(/-only/, "", $$1); \
						 printf "   $(_TARGET)%-$(_SPACING)s$(_NORMAL) %s (preinstall dependencies)\n", $$1, $$2;} \
		'

.PHONY: version
version:	## display current version
	@-echo "$(APP_NAME) version: $(APP_VERSION)"

## --- Versioning targets --- ##

# Bumpversion 'dry' config
# if 'dry' is specified as target, any bumpversion call using 'BUMP_XARGS' will not apply changes
BUMP_XARGS ?= --verbose --allow-dirty
ifeq ($(filter dry, $(MAKECMDGOALS)), dry)
	BUMP_XARGS := $(BUMP_XARGS) --dry-run
endif

.PHONY: dry
dry: setup.cfg	## run 'bump' target without applying changes (dry-run)
ifeq ($(findstring bump, $(MAKECMDGOALS)),)
	$(error Target 'dry' must be combined with a 'bump' target)
endif

.PHONY: bump
bump:	## bump version using VERSION specified as user input (make VERSION=<X.Y.Z> bump)
	@-echo "Updating package version ..."
	@[ "${VERSION}" ] || ( echo ">> 'VERSION' is not set"; exit 1 )
	@-bash -c '$(CONDA_CMD) test -f "$(CONDA_ENV_PATH)/bin/bump2version" || pip install $(PIP_XARGS) bump2version'
	@-bash -c '$(CONDA_CMD) bump2version $(BUMP_XARGS) --new-version "${VERSION}" patch;'

