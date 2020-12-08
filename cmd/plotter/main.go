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
