/*
Copyright 2020 Red Hat, Inc. jcope@redhat.com

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
package main

import (
	"os"
	"path/filepath"

	"github.com/spf13/pflag"
)

const kubeconfigEnv = "KUBECONFIG"

var (
	kubeconfig string
	queryType  string
	queryRange string
	outFormat  string
	version    string
)

const rangeHelp = `The range of time over which metrics are collected, starting from now() - range until now()
Input must adhere to Prometheus time format where time is an int and time unit is a single
character.
  Time units are:
    ms milliseconds
    s = seconds
    m = minutes
    h = hours
    d = days
    w = weeks
    m = months
    y = years
The time format concatenates the int and unit: ##unit, e.g. 10 minutes == 10m`

const queryHelp = `Designate the query type to execute
One of:
	"i"  most recent, instantaneous metric values
	"q"  95th quantile from last 10min of metric values
	"a"  average from the last 10min of metric values
Example:
	$ prom-top -t i # query instant vectors`

func init() {
	home, _ := os.UserHomeDir()
	kubeconfigDefault := filepath.Join(home, `.kube/config`)

	pflag.StringVar(&kubeconfig, "kubeconfig", kubeconfigDefault, "Path to kubeconfig file")
	pflag.StringVarP(&queryType, "type", "t", "", queryHelp)
	pflag.StringVar(&queryRange, "range", "", rangeHelp)
	pflag.StringVarP(&outFormat, "output", "o", "raw", "query return format: [csv, raw, postgres]")
	pflag.StringVarP(&version, "ocp-version", "v", "", "the version of ocp executed against")
	pflag.Parse()

	// If kubeconfig env var was set and no kubeconfig was provided via flag, use
	// env var value.  Else leave it as default kubeconfig path ($HOME/.kube/config)
	f := pflag.Lookup("kubeconfig")
	if !f.Changed {
		if kc, ok := os.LookupEnv(kubeconfigEnv); ok {
			kubeconfig = kc
		}
	}
}
