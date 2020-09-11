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

SERVER = "github.com/copejon/prometheus-query/src/cmd"
APP= "prom-ag"

GOOS = linux
GOARCH = amd64

BUILD_IMG=registry.redhat.io/ubi8/go-toolset:1.13.4

.PHONY: all build
all: build

build: ./cmd
	[ -d $(OUTDIR) ] || mkdir -p $(OUTDIR)
	docker run -e GOOS=$(GOOS) -e GOARCH=$(GOARCH) --rm -v $(shell pwd):/opt/app-root/src/$(APP) -w /opt/app-root/src/app/ $(BUILD_IMG) ./hack/build.sh

.PHONY: build_server
build_image: build/Dockerfile
	docker build -t localhost/$(APP) --file=server.Dockerfile .

.PHONY: clean
clean:
	GOCACHE="$(ROOTDIR)" go clean -cache
	rm "$(OUTDIR)/$(APP)"