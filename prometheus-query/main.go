package main

import (
	"github.com/prometheus/client_golang/api"
	"github.com/prometheus/client_golang/api/prometheus/v1"
)

func main(){
	conn, err := api.NewClient(api.Config{
		Address:      "",
	})
	if err != nil {
		panic(err)
	}
	c := v1.NewAPI(conn)
	var _ = c
}
