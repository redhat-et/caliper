# Build container image
# use microdnf to install packages
FROM registry.redhat.io/ubi8/ubi-minimal:8.2

COPY ./cluster-report-card /usr/bin/prometheus-query

ENTRYPOINT ["prometheus-query"]