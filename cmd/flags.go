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
	i most recent, instantaneous metric values
	q 95th quantile from last 10min of metric values
	a average from the last 10min of metric values
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
