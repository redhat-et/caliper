package queries

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"html/template"
	"time"

	v1 "github.com/prometheus/client_golang/api/prometheus/v1"
	"github.com/prometheus/common/model"
)

/*
         | 95th-%ile | Avg | Instant|
CPU      |___________|_____|________|
Memory   |___________|_____|________|
FS I/O   |___________|_____|________|
Net Send |___________|_____|________|
Net Rcv  |___________|_____|________|
*/

const (
	T_INSTANT  string = "i"
	T_QUANTILE string = "q"
	T_AVERAGE  string = "a"
)

type QueryConfig struct {
	QueryType        string `json:"queryType"`
	PrometheusClient v1.API `json:"prometheusClient"`
	Output           string `json:"output"`
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

func (t Top) String() string {
	out, err := json.Marshal(t)
	if err != nil {
		panic(err)
	}
	return string(out)
}

const (
	// TODO range values currently hardcoded to 10min, eventually will be flag configurable
	quantileOverTimeTemplate string = `quantile_over_time(.95, {{.Metric}}[10m])`
	avgOverTimeTemplate      string = `avg_over_time({{.Metric}}[10m])`
	instantTemplate          string = `{{.Metric}}`
)

var targetMetrics = []string{
	"pod:container_cpu_usage", // as a percentage
	"pod:container_memory_usage_bytes:sum", // as Mib
	"container_fs_usage_bytes", // as Mib
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

func NewTopQuery(cfg QueryConfig) (*Top, error) {
	var queryTemplate string
	switch cfg.QueryType {
	case T_INSTANT:
		queryTemplate = instantTemplate
	case T_QUANTILE:
		queryTemplate = quantileOverTimeTemplate
	case T_AVERAGE:
		queryTemplate = avgOverTimeTemplate
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
