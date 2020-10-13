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

// queries provides the functionality for constructing a PromQL query given the predefined set of metrics in targetMetrics.
// The type of query is determined via the QueryConfig.QueryType.  Supported queries are 95%ile over time, average
// over time, and instantaneous, for each metric.  Thus, the query/metric matrix is as follows, where only 1 vertex is
// executed per invocation.
//
//          | 95th-%ile | Avg | Instant|
// CPU      |___________|_____|________|
// Memory   |___________|_____|________|
// FS I/O   |___________|_____|________|
// Net Send |___________|_____|________|
// Net Rcv  |___________|_____|________|
//
// Queries supports only a small subset of functionality of PromQL in order to reflect the "top" format of the tool.
// Queries are deliberately geared to return InstantVectors.  A vector instance is essentially a scalar value and a
// timestamp.  Thus, the queries used here MAY span a range of time, but MUST return a single vector representation
// of the measurement.  For instance, the average bytes of memory consumed over the last 10 minutes is an InstantVector.
// However, the average bytes of memory consumed, read at steps of 1 second over 10 minutes, would produce a RangeVector:
// a series of InstantVectors representing the moment to moment average value.  This is not supported.
// See https://prometheus.io/docs/prometheus/latest/querying/basics/#expression-language-data-types for more info
// on promQL vector types.
package queries

import (
	"bytes"
	"context"
	"fmt"
	"html/template"
	"time"

	v1 "github.com/prometheus/client_golang/api/prometheus/v1"
	"github.com/prometheus/common/model"
)

const (
	//T_INSTANT toggles the an instant vector query
	T_INSTANT string = "i"
	//T_QUANTILE toggles the 95%ile over time query
	T_QUANTILE string = "q"
	// T_AVERAGE toggles the average over time query
	T_AVERAGE string = "a"
)

type QueryConfig struct {
	// QueryType must specify the query to be executed, defaults to Instant
	QueryType string `json:"queryType"`
	// PrometheusClient must be an initialized prometheus client
	PrometheusClient v1.API `json:"prometheusClient"`
}

type metricQuery struct {
	Metric      string `json:"metric"`
	QueryString string `json:"query"`
}

type QueryResult struct {
	Value    model.Value `json:"value"`
	Warnings v1.Warnings `json:"warnings"`
	Errs     error       `json:"errs"`
}

type Top struct {
	Queries []*metricQuery `json:"queries"`
	config  QueryConfig
}

// Querie Templates
// These templates are combined with targetMetrics to generate the query string respective of the query type
// defined at start time.  Given ONE OF
//     T_INSTANT
//     T_QUANTILE
//     T_AVERAGE
// the corresponding query below is used.  Only ONE query is executed during runtime.
const (
	// TODO range values currently hardcoded to 10min, eventually will be flag configurable
	quantileOverTimeTemplate string = `quantile_over_time(.95, {{.Metric}}[10m])`
	avgOverTimeTemplate      string = `avg_over_time({{.Metric}}[10m])`
	instantTemplate          string = `{{.Metric}}`
)

// targetMetrics specify the metric to be queried.  These values are processed by generateMetricQueriesTemplate()
// to generated the query string
var targetMetrics = []string{
	"pod:container_cpu_usage",              // as a percentage
	"pod:container_memory_usage_bytes:sum", // as Mib
	"container_fs_usage_bytes",             // as Mib
	"container_network_receive_bytes_total",
	"container_network_transmit_bytes_total",
}

func generateMetricQueriesTemplate(query string) ([]*metricQuery, error) {
	mqs := make([]*metricQuery, 0, len(targetMetrics))
	for _, t := range targetMetrics {
		mq, err := newMetricQuery(t, query)
		if err != nil {
			return nil, fmt.Errorf("error creating QueryString list: %v", err)
		}
		mqs = append(mqs, mq)
	}
	return mqs, nil
}

func newMetricQuery(metric, q string) (*metricQuery, error) {
	var queryConfig = struct {
		Metric string
		Range  string
	}{
		metric,
		"10m",
	}
	t, err := template.New("metricQuery").Parse(q)
	if err != nil {
		return nil, fmt.Errorf("template parsing error: %v", err)
	}

	buf := new(bytes.Buffer)
	err = t.Execute(buf, queryConfig)
	if err != nil {
		return nil, fmt.Errorf("templating error: %v", err)
	}

	return &metricQuery{
		Metric:      metric,
		QueryString: buf.String(),
	}, nil
}

//NewTopQuery constructor for generating new
func NewTopQuery(cfg QueryConfig) (*Top, error) {
	var queryTemplate string
	switch cfg.QueryType {
	case T_QUANTILE:
		queryTemplate = quantileOverTimeTemplate
	case T_AVERAGE:
		queryTemplate = avgOverTimeTemplate
	case T_INSTANT:
		queryTemplate = instantTemplate
	default:
		return nil, fmt.Errorf("unsupported QueryString selector: %s", cfg.QueryType)
	}
	qs, err := generateMetricQueriesTemplate(queryTemplate)
	if err != nil {
		return nil, err
	}
	return &Top{
		Queries: qs,
		config:  cfg,
	}, nil
}

type QueryTable []QueryResult

func (t Top) ExecuteQuery(ctx context.Context) (QueryTable, error) {
	qt := make(QueryTable, 0, len(targetMetrics))
	c := t.config.PrometheusClient
	for _, q := range t.Queries {
		v, w, err := c.Query(ctx, q.QueryString, time.Now())
		qt = append(qt, QueryResult{
			Value:    v,
			Warnings: w,
			Errs:     err,
		})
	}
	return qt, nil
}
