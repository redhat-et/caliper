#!/usr/bin/env bash
ROOT=$(readlink -f "$(dirname ${BASH_SOURCE})/../")

#GOCACHE=${ROOT}/.go-build
#[ -d "${GOCACHE}" ] || mkdir -p "${GOCACHE}"
go build -o ./bin/app ./cmd