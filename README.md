# Prometheus Resource Usage Querier [WIP]

**// // // // // // ATTENTION: CONSTRUCTION AREA! // // // // // //**

## Overview

This project consists of 2 components.

- `prom-top`: takes a kubeconfig and queries the Openshift cluster's Prometheus endpoint for usage metrics, reported as scalar values.
 Current query types are _average_ and _quantile(.95)_ for `--span` of time, and _instant_ which reports the latest instantaneous measurements.
 Presently only outputs for stdout.  **TODO: write to database**
- `plotter`: reads from a database and renders the information such that OCP components may be compared against each other across versions 
in order to track resource consumption changes.

### Prom-top:

**Prereqs**

- A running OCP cluster
- You must be logged into the cluster. Prometheus queries require a bearer token which is granted at login.  This can also be 
accomplished by created a ServiceAccount and granting it the requisite permissions for accessing the metrics API. Documentation
will eventually be added, for now this is purely experimental.

**Run**

1. Login to your OCP cluster:
`$ oc login $SERVER -kubeadmin -p $KUBEADMIN-PASSWORD`
1. Prom-top needs a kubeconfig.  This can be passed as an arg (`--kubeconfig`), set as and env var (`KUBECONFIG`), or assumed to be in the
default location (`$HOME/.kube/config`). 

    Assuming your config is at the default:
    
    `$ ./bin/prom-top`
    
### Plotter:

Plotter, like prom-top, is under development.  At present, it only reads rows from a postgres database and prints them to stdout.  Not that interesting.
It will eventually produce graphs derived from the data it queries to illustrate trends in resource usage per OCP version, at individual component granularity.
I.e. the net CPU usage by `api-server` pods.  More to follow.

**Prereqs**

- A postgres database table, with columns configured as

```
                        Table "public.prom_test"
   Column   |            Type             | Collation | Nullable | Default
------------+-----------------------------+-----------+----------+---------
 version    | text                        |           | not null |
 component  | text                        |           | not null |
 query      | text                        |           |          |
 value      | numeric(32,32)              |           |          |
 query_time | timestamp without time zone |           |          |
```

- A `.env` file at `./prom-top/` with the following values set:

```
PGHOST=[DATABASE_HOST]
PGPORT=[DATABASE_PORT]
PGDATABASE=[DATABASE_NAME]
PGUSER=[DATABASE_USER]
PGPASSWORD=[DATABASE_PASSWORD]
```

**Run**

1. Ensure your working dir contains the `.env` file
1. Execute `$ ./bin/plotter`

