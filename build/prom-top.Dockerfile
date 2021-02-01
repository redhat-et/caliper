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

# Build stage
FROM registry.redhat.io/ubi8/go-toolset:1.13.4 AS build

ENV GOPATH=/opt/app-root/

WORKDIR $GOPATH/src/github.com/caliper

COPY --chown=1001:1 . .

RUN GOCACHE=/tmp/.cache GOOS=linux GOARCH=amd64 go build -o /tmp/prom-top ./prom-top/cmd/...

# Run stage
FROM registry.redhat.io/ubi8/ubi-minimal:8.2

COPY --from=build /tmp/prom-top /usr/local/bin/prom-top

ENTRYPOINT ["prom-top"]