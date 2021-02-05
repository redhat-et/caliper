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
package dbhandler

import (
	"fmt"
	"log"
	"os"
	"path/filepath"

	_ "github.com/jackc/pgx/stdlib"
	"github.com/jmoiron/sqlx"
	"github.com/spf13/viper"
)

type Row struct {
	Version   string  `db:"version"`
	Metric    string  `db:"metric"`
	Pod       string  `db:"pod"`
	Range     string  `db:"range"`
	Namespace string  `db:"namespace"`
	LabelApp  string  `db:"label_app"`
	Node      string  `db:"node"`
	QueryTime string  `db:"query_time"`
	Q95Value  float64 `db:"q95_value"`
	AvgValue  float64 `db:"avg_value"`
	MaxValue  float64 `db:"max_value"`
	MinValue  float64 `db:"min_value"`
	InstValue float64 `db:"inst_value"`
}

func (r *Row) String() string {
	return fmt.Sprintf("%s [%s]{%s, %s, %s, %s} => {@%s, Q95(%f), AVG(%f), MAX(%f), MIN(%f), INST(%f)}",
	r.Metric,
	r.Range,
	r.Pod,
	r.Namespace,
	r.LabelApp,
	r.Node,
	r.QueryTime,
	r.Q95Value,
	r.AvgValue,
	r.MaxValue,
	r.MinValue,
	r.InstValue,
	)
}

// ColumnsHeaders defines the expected headers` for the metrics table and exists
// to provide a source of truth for our table format.
func ColumnsHeaders() []string {
	return []string{
		"version",
		"metric",
		"node",
		"pod",
		"namespace",
		"label_app",
		"avg_value",
		"q95_value",
		"max_value",
		"min_value",
		"inst_value",
		"query_time",
		"range",
	}
}

const TimestampFormat = `2006-01-02 15:04:05`

// Table is a hardcoded table name.  Will be replaced with dynamically set names.
const Table = "metrics"

const (
	host     = "PGHOST"
	port     = "PGPORT"
	database = "PGDATABASE"
	user     = "PGUSER"
	password = "PGPASSWORD"
)

type PostgresConfig struct {
	host     string
	port     int
	database string
	user     string
	password string
}

func (p PostgresConfig) String() string {
	return fmt.Sprintf("postgres://%s:%s@%s:%d/%s", p.user, p.password, p.host, p.port, p.database)
}

func initConfig() PostgresConfig {
	exPath, _ := os.Executable()
	viper.SetConfigFile(filepath.Join(filepath.Dir(exPath), ".env"))
	viper.SetConfigType("dotenv")
	err := viper.BindEnv(
		host,
		port,
		database,
		user,
		password)
	if err != nil {
		log.Fatalf("failed to bind env vars: %v", err)
	}
	viper.AutomaticEnv()
	err = viper.ReadInConfig()

	if err != nil {
		log.Printf("no postgress config found: %v", err)
	}

	return PostgresConfig{
		host:     viper.GetString(host),
		port:     viper.GetInt(port),
		database: viper.GetString(database),
		user:     viper.GetString(user),
		password: viper.GetString(password),
	}
}

func NewPostgresClient() (*sqlx.DB, error) {
	cfg := initConfig()
	return sqlx.Connect("pgx", cfg.String())
}
