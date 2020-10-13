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
	//span       string
	//output     string
)

func init() {
	home, _ := os.UserHomeDir()
	kubeconfigDefault := filepath.Join(home, `/.kube/config`)
	queryTypeDefault := "q" // 95th quantile

	pflag.StringVar(&kubeconfig, "kubeconfig", kubeconfigDefault, "path to kubeconfig file")
	pflag.StringVarP(&queryType, "type", "t", queryTypeDefault,
		`Designate the query type to execute
One of:
	"i"  most recent, instantaneous metric values
	"q"  95th quantile from last 10min of metric values
	"a"  average from the last 10min of metric values
Example:
	$ prom-top -t i # query instant vectors
`,
	)
	//pflag.StringVar(&span, "span", "", "the span from now back in time to compute")
	//pflag.StringVarP(&output, "output", "o", "pretty", "format to print data to stdout [ json | pretty ]")
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
