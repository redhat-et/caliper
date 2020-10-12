package main

import (
	"github.com/spf13/pflag"
	"os"
)

const kubeconfigEnv = "KUBECONFIG"

var (
	kubeconfig string
	span       string
	output     string
	//queryType  string
)

func init() {
	kubeconfig = os.Getenv(kubeconfigEnv)
	pflag.StringVar(&kubeconfig, "kubeconfig", kubeconfig, "path to kubeconfig file")
	pflag.StringVar(&span, "span", "", "the span from now back in time to compute")
	pflag.StringVarP(&output, "output", "o", "pretty", "format to print data to stdout [ json | pretty ]")
	//pflag.StringVarP(&queryType) "type", "t", "95", "type of query to execute [ 95, instant, ]")
	pflag.Parse()
}
