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
	"encoding/csv"
	"fmt"
	"k8s.io/klog"
	"text/template"
	"time"

	v1 "github.com/prometheus/client_golang/api/prometheus/v1"
	"github.com/prometheus/common/model"
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
	memoryMetric = "container_fs_usage_bytes"
	//"container_network_receive_bytes_total",
	//"container_network_transmit_bytes_total",
)

// Query Templates
// These templates are combined with targetMetrics to generate the query string respective of the query type
// defined at start time.  Given ONE OF
//     T_INSTANT
//     T_QUANTILE
//     T_AVERAGE
// the corresponding query below is used.  Only ONE query is executed during runtime.
const (
	quantileOverTimeTemplate = `quantile_over_time(.95, {{.Metric}}[{{.Range}}])`
	avgOverTimeTemplate      = `avg_over_time({{.Metric}}[{{.Range}}])`
	instantTemplate          = `{{.Metric}}`

	// appLabelQuery wraps query templates after they've been processed in order to
	// add the 'label_app' label to the metric.  This groups pods by their deployment
	appLabelQuery = `sum by (pod, label_app) (kube_pod_labels{pod!="", label_app!=""}) * on (pod) group_right(label_app) sum by (pod, namespace, node) ({{.Query}})`
)

const (
	aggregatorCodeQuantile95 = "Q95"
	aggregatorCodeAverage    = "AVG"
	aggregatorCodeInstant    = "INST"
)

var aggregatorCodeLookup = map[string]string{
	quantileOverTimeTemplate: aggregatorCodeQuantile95,
	avgOverTimeTemplate:      aggregatorCodeAverage,
	instantTemplate:          aggregatorCodeInstant,
}

func selectQueryTemplates(q string) ([]string, error) {
	t := make([]string, 0)
	klog.Infof("DEBUG -------- template selector: %s", q)
	switch q {
	case "q":
		t = append(t, quantileOverTimeTemplate)
	case "a":
		t = append(t, avgOverTimeTemplate)
	case "i":
		t = append(t, instantTemplate)
	default:
		t = []string{quantileOverTimeTemplate, avgOverTimeTemplate, instantTemplate}
	}
	return t, nil
}

//func generateTargetMetricQueries(cfg Config) ([]string, error) {
//	metricTmps, err := selectQueryTemplates(cfg.QueryType)
//	if err != nil {
//		return nil, fmt.Errorf("failed to parse query type: %v", err)
//	}
//
//	queries := make([]string, 0)
//	appLabelsTmp := template.New("labels")
//	template.Must(appLabelsTmp.Parse(appLabelQuery))
//	for _, t := range metricTmps {
//		tmp := template.New("")
//		template.Must(tmp.Parse(t))
//		for _, tm := range targetMetrics {
//			metricBuf := new(bytes.Buffer)
//			err = tmp.Execute(metricBuf, struct {
//				Metric, Range string
//			}{tm, cfg.Range})
//			if err != nil {
//				return nil, fmt.Errorf("composing base query template: %v", err)
//			}
//
//			labelBuf := new(bytes.Buffer)
//			err = appLabelsTmp.Execute(labelBuf, struct {
//				Query string
//			}{metricBuf.String()})
//			if err != nil {
//				return nil, fmt.Errorf("composing label query template: %v", err)
//			}
//			queries = append(queries, labelBuf.String())
//		}
//	}
//	return queries, nil
//}

func sampleCSVRecord(s *model.Sample) []string {
	return []string{
		string(s.Metric[model.LabelName("namespace")]),
		string(s.Metric[model.LabelName("pod")]),
		s.Value.String(),
		s.Timestamp.String(),
	}
}

type QueryResult struct {
	Metric         string `json:"metric"`
	AggregatorCode string `json:"aggregator_code"`
	model.Vector
	Warnings v1.Warnings `json:"warnings,omitempty"`
}

var header = []string{"namespace", "pod", "value", "time"}

func (q QueryResult) MarshalCSV() ([]byte, error) {
	v := q.Vector
	buf := new(bytes.Buffer)
	wtr := csv.NewWriter(buf)
	err := wtr.Write(header)
	if err != nil {
		return nil, fmt.Errorf("error writing header: %v", err)
	}
	for _, s := range v {
		err = wtr.Write(sampleCSVRecord(s))
		if err != nil {
			return nil, fmt.Errorf("error writing csv entry: %v", err)
		}
	}
	wtr.Flush()
	return buf.Bytes(), nil
}

// targetMetrics specify the metric to be queried.  These values are processed by generateQueryList()
// to generated the query string
var targetMetrics = []string{cpuMetric, memoryMetric}

func top(cfg Config) ([]*QueryResult, error) {
	results := make([]*QueryResult, 0)
	now := time.Now() // get current time to maintain static end of range in queries

	metricTmps, err := selectQueryTemplates(cfg.QueryType)
	if err != nil {
		return nil, fmt.Errorf("failed to parse query type: %v", err)
	}

	appLabelsTmp := template.New("labels")
	template.Must(appLabelsTmp.Parse(appLabelQuery))
	// worst case scenario these loops will execute a total of 12 times (n_TargetMetrics * n_QueryTemplates)
	for _, t := range metricTmps {
		tmp := template.New("")
		template.Must(tmp.Parse(t))
		for _, tm := range targetMetrics {

			klog.Infof("DEBUG --------- template: %s", t)

			// constructs the query
			queryBuf := new(bytes.Buffer)
			err = tmp.Execute(queryBuf, struct {
				Metric, Range string
			}{tm, cfg.Range})
			if err != nil {
				return nil, fmt.Errorf("composing base query template: %v", err)
			}

			// wraps the query with the appLabelQuery to inject the label_app into the metric's label vector
			labelBuf := new(bytes.Buffer)
			err = appLabelsTmp.Execute(labelBuf, struct {
				Query string
			}{queryBuf.String()})
			if err != nil {
				return nil, fmt.Errorf("composing label query template: %v", err)
			}

			// execute the query
			val, warn, err := cfg.PrometheusClient.Query(cfg.Context, labelBuf.String(), now)
			if err != nil {
				return nil, fmt.Errorf("query %q failed: %v", labelBuf.String(), err)
			}
			v, ok := val.(model.Vector)
			if !ok {
				return nil, fmt.Errorf("expected vector")
			}
			code, ok := aggregatorCodeLookup[t]
			if !ok {
				return nil, fmt.Errorf("template unknown in lookup: %s", t)
			}
			results = append(results, &QueryResult{
				Metric:         tm,
				AggregatorCode: code,
				Vector:         v,
				Warnings:       warn,
			})
		}
	}
	return results, nil
}

const defaultRange = "10m"

// Top executes the specified query against targetMetrics and returns a slice of Prometheus InstantVertices.  An
// instantVertex is a point-in-time data structure containing the metric values for all reporting components.  Thus,
// Top is not intended for continuous monitoring. See TODO
func Top(cfg Config) ([]*QueryResult, error) {
	if cfg.Context == nil {
		cfg.Context = context.Background()
	}
	if len(cfg.Range) == 0 {
		cfg.Range = defaultRange
	}
	return top(cfg)
}
