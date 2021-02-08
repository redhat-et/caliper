# Caliper [WIP]

## Overview

Caliper's objective is to provide a cross-version analysis of Openshift CPU, Memory, and Network usage.  Users (or automation) can execute a simple CLI tool to query, aggregate, and store metrics in a database.  A long lived service will read from the database and host a dashboard of plots comparing resource usage across versions.

Unlike `kubectl top`, Caliper aggregates its results from Prometheus time-series, providing a more accurate picture of resource consumption.  Where `kubectl top` takes an instantaneous reading from [metrics-server](https://github.com/kubernetes-sigs/metrics-server), Caliper calculates 95th%, average, min, and max from a user-defined time range (default 10min). 

This project consists of 2 components and has a dependency on a Postgres database.

- `prom-top`: a CLI tool that queries a Prometheus API endpoint in a OCP cluster.  Results are printed to shell by default or optionally written to a Postgres DB. 
- `plotter`: reads `prom-top` results from a Postgres DB and servers a plot dashboard over http. Data is presented as  
- Postgres: persists results from `prom-top` for later use by `plotter`



## Deploy

### Build

Build workflows are driven by `make`.  By default, it will build to container images. Do deactivate container builds and compile locally, pass `DOCKER=0` as a `make` variable.

- `make` / `make all` / `make build`: builds prom-top and plotter from source and produces container images for both.
- `make prom-top`: compiles prom-top into a container image
- `make plotter`: create a plotter container image.  It `DOCKER != 0`, install python deps locally.
- `make up`: uses docker-compose script to deploy a optionally build, then deploy a plotter and Postgres container.  If `DOCKER != 0`, then only starts the local plotter binary.  Use `ctrl-C` to stop the processes.
- `make clean`: deletes build artifacts (container images or local binaries, depending you `DOCKER=0`)

## Run

#### Prereqs

1. A running, reachable Openshift cluster

1. A logged in user account to that cluster. 

   - This is because promQL queries require a bearer token.  Later manifests will be added to describe an in-cluster agent with the appropriate perms to query the Prometheus API endpoint.

## Setup and Execute

To generate plots, Plotter and Postgres must be running.

1. `make up` will deploy plotter and postgres.
1. In a browser, enter the address `localhost:8050` to verify plotter is running and is reachable.
1. *Optionally*, dry-run prom-top by printing the metric data to stdout.  This is the default action for the app:  `./bin/prom-top`
1. Execute prom-top with args: `./bin/prom-top -v $OPENSHIFT_CLUSTER_VERSION -o postgres`
1. On the plotter browser page, hit refresh.  You should now see the aggregated metric data represented on the plots.

## Expected Ouput

Once deployed, Plotter will fetch all data from Postgres and generate comparative charts thanks to the Dash and Plottly python packages (see below).

Groupings are configure in the [component-mappings.yaml](./plotter/component-mapping.yaml). Currently, the config is designed to compose groupings of namespaces.  This is likely to change with feedback but works as a PoC for the time being.




![](/Users/jcope/Workspace/github.com/redhat-et/caliper/hack/charts.png)