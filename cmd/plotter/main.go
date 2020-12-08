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
	"fmt"
	"github.com/copejon/prometheus-query/pkg/dbclient"
	"log"
	"time"

	_ "github.com/jackc/pgx/stdlib"
)

type Row struct {
	Build     string
	Metric    string
	Value     float64
	QueryTime time.Time `db:"query_time"`
}

func (r Row) String() string {
	return fmt.Sprintf("Ver: %s | Metric: %s | Val: %f | Time: %v", r.Build, r.Metric, r.Value, r.QueryTime)
}

func main() {

	db, err := dbclient.NewPostgresClient()
	if err != nil {
		log.Fatalf("db connect failed: %v", err)
	}
	defer db.Close()

	rows := make([]Row, 0)
	err = db.Select(&rows, "SELECT * FROM metrics")
	if err != nil {
		log.Fatalf("select failed: %v", err)
	}
	log.Printf("got %d rows\n", len(rows))
	for _, r := range rows {
		log.Println("Row --- " + r.String())
	}
}
