/*
Copyright 2020 Jonathan Cope jcope@redhat.com

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

// top provides the functionality for constructing a PromQL query given the predefined set of metrics in targetMetrics.
// The type of query is specified via the Config.QueryType.  Supported queries are 95%ile over time, average
// over time, and instantaneous, for each metric.  Thus, the query/metric matrix is as follows, where only 1 vertex is
// executed per invocation.
//
//          | 95%-ile | or | Avg | or | Instant |
// CPU      |_________| or |_____| or |_________|
// Memory   |_________| or |_____| or |_________|
// FS I/O   |_________| or |_____| or |_________|
// Net Send |_________| or |_____| or |_________|
// Net Rcv  |_________| or |_____| or |_________|
//
// Top supports only a small subset of functionality of PromQL. Queries are deliberately geared to return InstantVectors.
// A vector instance is essentially a scalar value and a timestamp.  Thus, the queries used here MAY span a range of
// time, but MUST return a single vector representation of the measurement.  For instance, the average bytes of memory
//consumed over the last 10 minutes is an InstantVector. However, the average bytes of memory consumed, read at steps
// of 1 second over 10 minutes, would produce a RangeVector:a series of InstantVectors representing the moment to moment
// average value.
// See https://prometheus.io/docs/prometheus/latest/querying/basics/#expression-language-data-types for more info
// on promQL vector types.
package top

import (
	"bytes"
	"context"
	"fmt"
	"hash/fnv"
	"strconv"
	"strings"
	"text/template"
	"time"

	v1 "github.com/prometheus/client_golang/api/prometheus/v1"
	"github.com/prometheus/common/model"

	"github.com/redhat-et/caliper/prom-top/pkg/dbhandler"
)

type Config struct {
	Context context.Context
	// QueryType must specify the query to be executed, defaults to Instant
	QueryType string `json:"queryType"`
	// Range (optional) defines a span of time from (time.Now() - Range) until time.Now()
	// Ignored by Instant query.
	// Input must adhere to Prometheus time format where time is an int and time unit is a single character.
	// Time units are
	//   ms milliseconds
	//   s = seconds
	//   m = minutes
	//   h = hours
	//   d = days
	//   w = weeks
	//   m = months
	//   y = years
	// The time format concatenates the int and unit: ##unit, e.g. 10 minutes == 10m
	Range string `json:"range,omitempty"`
	// PrometheusClient must be an initialized prometheus client
	PrometheusClient v1.API `json:"prometheusClient"`
}

const (
	cpuMetric    = "container_cpu_usage_seconds_total"
	memoryMetric = "container_memory_usage_bytes"
	//"container_network_receive_bytes_total",
	//"container_network_transmit_bytes_total",
)

// Query Templates
// These templates are combined with targetMetrics to generate the query string respective of the query type
// defined at start time.  Given ONE OF
//     T_INSTANT
//     T_QUANTILE
//     T_AVERAGE
const (
	avgCpu  = `avg(rate(container_cpu_usage_seconds_total{pod!=''}[{{.Range}}])) by (pod, namespace, node)`
	maxCpu  = `max(rate(container_cpu_usage_seconds_total{pod!=''}[{{.Range}}])) by (pod, namespace, node)`
	minCpu  = `min(rate(container_cpu_usage_seconds_total{pod!=''}[{{.Range}}])) by (pod, namespace, node)`
	q95Cpu  = `quantile(.95, rate(container_cpu_usage_seconds_total{pod!=''}[{{.Range}}])) by (pod, namespace, node)`
	instCpu = `sum(container_cpu_usage_seconds_total{pod!=''}) by (pod, namespace, node)`

	avgMem  = `avg(container_memory_usage_bytes{pod!=''}) by (pod, namespace, node)`
	maxMem  = `max(container_memory_usage_bytes{pod!=''}) by (pod, namespace, node)`
	minMem  = `min(container_memory_usage_bytes{pod!=''}) by (pod, namespace, node)`
	q95Mem  = `quantile(.95, container_memory_usage_bytes) by (pod, namespace, node)`
	instMem = `container_memory_usage_bytes{pod!=''}`
)

var metrics = []string{avgCpu, maxCpu, minCpu, q95Cpu, instCpu, avgMem, maxMem, minMem, q95Mem, instMem}

type PodMetric dbhandler.Row

func (p PodMetric) MarshalCSV() []byte {
	return []byte(fmt.Sprintf("%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,\n",
		p.Metric, p.Range, p.Pod, p.Namespace, p.LabelApp,
		floatToString(p.Q95Value), floatToString(p.MaxValue), floatToString(p.MinValue),
		floatToString(p.AvgValue), floatToString(p.InstValue)))
}

func floatToString(f float64) string {
	return strconv.FormatFloat(f, 'e', -1, 64)
}

func (p PodMetric) String() string {
	return fmt.Sprintf("metric => %q {Pod=%s, Namespace=%s, Node=%s, Label App=%s}: {Avg: %f, Q95: %f, Max: %f, Min: %f}",
		p.Metric, p.Pod, p.Namespace, p.Node, p.LabelApp, p.AvgValue, p.Q95Value, p.MaxValue, p.MinValue,
	)
}

type PodMetricTable []*PodMetric

func (pm PodMetricTable) MarshalCSV() []byte {
	buf := new(bytes.Buffer)
	buf.Write([]byte("metric, range, pod, namespace, label-app, quantile-95, max, min, avg, inst\n"))
	for _, line := range pm {
		buf.Write(line.MarshalCSV())
	}
	return buf.Bytes()
}

// targetMetrics specify the metric to be queried.  These values are processed by generateQueryList()
// to generated the query string
//var targetMetrics = []string{cpuMetric, memoryMetric}

func top(cfg Config) (PodMetricTable, error) {
	now := time.Now() // get current time to maintain static end of range in queries

	//podMetricHashTable is used to collate metric values by pod.  Each query must be executed independently, resulting
	// in up to 4 values per pod.  Pods are hashed to the table to enable simple lookup and updating
	podMetricHashTable := make(map[uint32]*PodMetric)
	hash := fnv.New32a()
	for _, m := range metrics {
		tmp := template.New("")
		template.Must(tmp.Parse(m))
		//// constructs the query
		queryBuf := new(bytes.Buffer)
		err := tmp.Execute(queryBuf, struct {
			Metric, Range string
		}{m, cfg.Range})
		if err != nil {
			return nil, fmt.Errorf("composing base query template: %v", err)
		}

		// execute the query
		queryValue, _, err := cfg.PrometheusClient.Query(cfg.Context, queryBuf.String(), now)
		if err != nil {
			return nil, fmt.Errorf("query %q failed: %v", queryBuf.String(), err)
		}
		vector, ok := queryValue.(model.Vector)
		if !ok {
			return nil, fmt.Errorf("expected vector")
		}

		for _, sample := range vector {
			ns, _ := sample.Metric["namespace"]
			pod, _ := sample.Metric["pod"]
			node, _ := sample.Metric["node"]

			// The hash is derived from the namespace, pod name, and node
			var metric string
			if strings.Contains(m, "mem") {
				metric = "container_memory_bytes"
			} else if strings.Contains(m, "cpu") {
				metric = "cpu_usage_ratio"
			}
			_, err := hash.Write([]byte(fmt.Sprintf("%s-%s-%s", string(ns), string(pod), metric)))
			id := hash.Sum32()
			hash.Reset()

			if err != nil {
				return nil, err
			}
			_, ok := podMetricHashTable[id]
			if !ok {
				podMetricHashTable[id] = new(PodMetric)
			}

			labelApp, _ := sample.Metric["label_app"]
			podMetricHashTable[id].Namespace = string(ns)
			podMetricHashTable[id].Pod = string(pod)
			podMetricHashTable[id].Node = string(node)
			podMetricHashTable[id].Metric = metric
			podMetricHashTable[id].LabelApp = string(labelApp)
			podMetricHashTable[id].Range = cfg.Range
			podMetricHashTable[id].QueryTime = now.Format(dbhandler.TimestampFormat)

			switch {
			case strings.Contains(m, "quantile"):
				podMetricHashTable[id].Q95Value = float64(sample.Value)
			case strings.Contains(m, "avg"):
				podMetricHashTable[id].AvgValue = float64(sample.Value)
			case strings.Contains(m, "max"):
				podMetricHashTable[id].MaxValue = float64(sample.Value)
			case strings.Contains(m, "min"):
				podMetricHashTable[id].MinValue = float64(sample.Value)
			case len(m) > 0:
				// instant metrics will not have the above aggregation queries, making it difficult to detect.
				// assume it's an instant query if the string is non-0 len and doesn't contain an aggregation query
				podMetricHashTable[id].InstValue = float64(sample.Value)
			}
			//}
		}
	}
	podMetrics := make(PodMetricTable, 0, len(podMetricHashTable))
	for _, pm := range podMetricHashTable {
		podMetrics = append(podMetrics, pm)
	}

	return podMetrics, nil
}

const defaultRange = "10m"

// Top executes the specified query against targetMetrics and returns a slice of Prometheus InstantVertices.  An
// instantVertex is a point-in-time data structure containing the metric values for all reporting components.  Thus,
// Top is not intended for continuous monitoring.
func Top(cfg Config) (PodMetricTable, error) {
	if cfg.Context == nil {
		cfg.Context = context.Background()
	}
	if len(cfg.Range) == 0 {
		cfg.Range = defaultRange
	}
	return top(cfg)
}
