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

FROM registry.redhat.io/ubi8/go-toolset:1.13.4 AS build

ENV GOPATH=/opt/app-root/

WORKDIR $GOPATH/src/prom-top

# mount the repo root to work dir
COPY --chown=1001:1 . .

RUN GOCACHE=/tmp/.cache GOOS=linux GOARCH=amd64 go build -o ./bin/prom-top ./cmd

# Run container image
FROM registry.redhat.io/ubi8/ubi-minimal:8.2

COPY --from=build ./opt/app-root/src/prom-top/bin/prom-top /usr/local/bin/prom-top

ENTRYPOINT ["prom-top"]