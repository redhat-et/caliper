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
	"context"
	"encoding/json"
	"fmt"
	"github.com/copejon/prometheus-query/cmd/queries"
	"github.com/spf13/pflag"
	"k8s.io/client-go/rest"
	"os"
	"time"

	promapi "github.com/prometheus/client_golang/api"
	promv1 "github.com/prometheus/client_golang/api/prometheus/v1"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/klog/v2"

	apiroute "github.com/openshift/api/route/v1"
	routev1 "github.com/openshift/client-go/route/clientset/versioned/typed/route/v1"
)

const (
	promNamespace = `openshift-monitoring`
	promRoute     = `prometheus-k8s`
)

func main() {
	defer klog.Flush()

	klog.Info("initializing openshift client")
	cfg, err := clientcmd.BuildConfigFromFlags("", kubeconfig)
	if err != nil {
		klog.Error(err)
		os.Exit(1)
	}

	if ! hasBearerToken(cfg) {
		klog.Error("error: bearer token not found, required to prometheus oauth access.  login to cluster with 'oc'")
		os.Exit(1)
	}

	rc := routev1.NewForConfigOrDie(cfg)

	klog.Infof("fetching prometheus route")
	route, err := rc.Routes(promNamespace).Get(context.Background(), promRoute, metav1.GetOptions{})
	if err != nil {
		klog.Error(err)
		os.Exit(1)
	}

	transport, err := rest.TransportFor(cfg)
	if err != nil {
		klog.Error(err)
		os.Exit(1)
	}

	host := prometheusHost(route)
	klog.Infof("initializing connection for host: %s", host)
	conn, err := promapi.NewClient(promapi.Config{
		Address:      host,
		RoundTripper: transport,
	})

	pc := promv1.NewAPI(conn)
	if err != nil {
		klog.Error(err)
		os.Exit(1)
	}

	klog.Info("creating prometheus api client")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	results := queries.DoQuery(pc, ctx)
	out, _ := json.MarshalIndent(results, "", "  ")
	klog.Infof("%s", string(out))
}

func hasBearerToken(cfg *rest.Config) bool {
	if len(cfg.BearerToken) == 0 && len(cfg.BearerTokenFile) == 0 {
		return false
	}
	return true
}

func prometheusHost(r *apiroute.Route) string {
	return fmt.Sprintf("https://%s", r.Spec.Host)
}

const kubeconfigEnv = "KUBECONFIG"

var kubeconfig string

func init() {

	kubeconfig = os.Getenv(kubeconfigEnv)
	pflag.StringVarP(&kubeconfig, "kubeconfig", "", kubeconfig, "path to kubeconfig file")
	pflag.Parse()
}
