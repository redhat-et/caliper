package targets

import "time"

const (
	container_cpu string = ""
	container_mem string = ""
)

const (
	defaultRange = 10 // minutes
)

func DefaultSeriesRange() time.Duration {
	return defaultRange * time.Minute
}