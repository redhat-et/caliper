# Caliper [WIP]

**// // // // // // ATTENTION: CONSTRUCTION AREA! // // // // // //**

## Overview

This project consists of 2 components.

- `prom-top`: takes a kubeconfig and queries the Openshift cluster's Prometheus endpoint for usage metrics, reported as scalar values.
 Current query types are _average_ and _quantile(.95)_ for `--span` of time, and _instant_ which reports the latest instantaneous measurements.
 Presently only outputs for stdout.  **TODO: write to database**
- `plotter`: reads from a database and renders the information such that OCP components may be compared against each other across versions 
in order to track resource consumption changes.

### General Pre-reqs

- A dotenv (`.env`) must be present in the same directory as `prom-top` and `plotter` containing db connection information.  This 
is to simplify database access to for both apps.  An example file is provided at `./.env.example` in the repo root.

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

Plotter, like prom-top, is under development.  The app is written in Python3 and utilizes the Plotly library to process.
It queries the database and generates a stacked bar chart from the results.  At present, it generates a single chart describing
the percentage of CPU time consumed by each component vs the OCP version.

**Prereqs**

- A postgres database table, with columns configured as shown below.  Only **type** is required. 

```
                             Table "public.metrics"
     Column      |            Type             | Collation | Nullable | Default
-----------------+-----------------------------+-----------+----------+---------
 version         | text                        |           | not null |
 metric          | text                        |           |          |
 pod             | text                        |           |          |
 namespace       | text                        |           |          |
 label_app       | text                        |           |          |
 query_time      | timestamp without time zone |           |          |
 value           | numeric                     |           |          |
 aggregator_code | text                        |           |          |
 node            | text                        |           |          |
```

**Run**

1. Ensure your working dir contains the `.env` file
1. execute `$ python `
