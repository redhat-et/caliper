package queries

import (
	"context"
	"time"

	v1 "github.com/prometheus/client_golang/api/prometheus/v1"
	"github.com/prometheus/common/model"

	"k8s.io/klog/v2"
)

const (
	defaultRange = 10 // minutes

	QueryPodContainerCpuUsage     = "pod:container_cpu_usage"
	QueryPodContainerMemUsage     = "pod:container_memory_working_set_bytes"
	QueryContainerFileSystemUsage = "container_fs_usage_bytes"
	QueryContainerNetworkRec      = "container_network_receive_bytes_total"
	QueryContainerNetworkSent     = "container_network_transmit_bytes_total"
)

type result struct {
	Metric   string
	Value    model.Value
	Warnings v1.Warnings
	Errs     error
}

// TODO templatize queries
// TODO enable configurable queries via flags
func DoQuery(c v1.API, ctx context.Context) []*result {

	results := make([]*result, 0, 5)
	results = append(results, QueryCPU(c, ctx))
	results = append(results, QueryMem(c, ctx))
	results = append(results, QueryFSUsage(c, ctx))
	results = append(results, QueryNetworkSent(c, ctx))
	results = append(results, QueryNetworkRec(c, ctx))

	return results
}

func QueryCPU(c v1.API, ctx context.Context) *result {
	v, w, err := c.Query(ctx, `quantile_over_time(.95, pod:container_cpu_usage:sum[10m])`, time.Now())
	if err != nil {
		klog.Errorf("Query(CPU) error: %v", err)
	}
	return &result{
		Metric:   QueryPodContainerCpuUsage,
		Value:    v,
		Warnings: w,
		Errs:     err,
	}
}

func QueryMem(c v1.API, ctx context.Context) *result {
	v, w, err := c.Query(ctx, `quantile_over_time(.95, pod:container_memory_working_set_bytes[10m])`, time.Now())
	if err != nil {
		klog.Errorf("Query(MEM) error: %v", err)
	}
	return &result{
		Metric:   QueryPodContainerMemUsage,
		Value:    v,
		Warnings: w,
		Errs:     err,
	}
}

func QueryFSUsage(c v1.API, ctx context.Context) *result {
	v, w, err := c.Query(ctx, `quantile_over_time(.95, container_fs_usage_bytes[10m])`, time.Now())
	if err != nil {
		klog.Errorf("Query(FS) error: %v", err)
	}
	return &result{
		Metric:   QueryContainerFileSystemUsage,
		Value:    v,
		Warnings: w,
		Errs:     err,
	}
}

func QueryNetworkRec(c v1.API, ctx context.Context) *result {
	v, w, err := c.Query(ctx, `quantile_over_time(.95, container_network_receive_bytes_total[10m])`, time.Now())
	if err != nil {
		klog.Errorf("Query(Net-Rec) error: %v", err)
	}
	return &result{
		Metric:   QueryContainerNetworkRec,
		Value:    v,
		Warnings: w,
		Errs:     err,
	}
}

func QueryNetworkSent(c v1.API, ctx context.Context) *result {
	v, w, err := c.Query(ctx, `quantile_over_time(.95, container_network_transmit_bytes_total[10m])`, time.Now())
	if err != nil {
		klog.Errorf("Query(Net-Sent) error: %v", err)
	}
	return &result{
		Metric:   QueryContainerNetworkSent,
		Value:    v,
		Warnings: w,
		Errs:     err,
	}
}
