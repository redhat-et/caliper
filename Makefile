#Copyright 2020 Jonathan Cope jcope@redhat.com
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

.ONESHELL:
SHELL = /usr/bin/env bash

ROOTDIR := $(shell pwd)
OUTDIR := $(ROOTDIR)/bin

GOOS = linux
GOARCH = amd64

PROMTOP_TAG=prom-top:latest
PLOTTER_TAG=plotter:latest

# By default, run build containers.
# set this to any non-0 value to build locally.
DOCKER=0

.PHONY: all build
all: build

build: TMP_DIR=./_build_promtop/
build: prom-top plotter

# As a requirement for go modules, the go.mod and go.sum file should be a the repo's root dir, which complicates
# containerized builds.  We don't want to copy the entire project into the container, just the ./prom-top source code.
# But since the go.* dependency files aren't stored there, we have to do some moving and copying to setup up a clean
# context for docker to build in.
.PHONY: prom-top
prom-top:
ifeq (${DOCKER}, 0)
	rm -rf $(TMP_DIR)
	mkdir $(TMP_DIR)
	cp -r ./prom-top $(TMP_DIR)
	cp go.mod go.sum $(TMP_DIR)
	docker build -t $(PROMTOP_TAG) -f ./build/prom-top.Dockerfile $(TMP_DIR)
	rm -rf $(TMP_DIR)
else
	go build -o ./bin/prom-top ./prom-top/cmd/...
endif

.PHONY: plotter
plotter:
ifeq ($(DOCKER), 0)
	docker build -t $(PLOTTER_TAG) -f ./build/plotter.Dockerfile plotter/
else
	pip install -r ./plotter/requirements.txt
endif

.PHONY: up
up: plotter
ifeq ($(DOCKER), 0)
	(cd ./build && docker-compose up)
else
	./bin/plotter
endif

.PHONY: clean
clean:
ifeq ($(DOCKER), 0)
	@(cd ./build && docker-compose down --rmi local)
	@docker rmi $(PROMTOP_TAG) 2>/dev/null || echo "Image $(PROMTOP_TAG) not found, skipping"
	@docker rmi $(PLOTTER_TAG) 2>/dev/null || echo "Image $(PLOTTER_TAG) not found, skipping"
	@rm -rf $(TMP_DIR) || echo "$(TMP_DIR) not found, skipping"
else
	rm bin/prom-top
endif