package main

import (
	"fmt"
	"github.com/Masterminds/squirrel"
	_ "github.com/jackc/pgx/stdlib"
	"github.com/jmoiron/sqlx"
	"github.com/prometheus/common/model"
	"github.com/spf13/viper"
	"log"
	"os"
	"path/filepath"
)

type config struct {
	host     string
	port     int
	database string
	user     string
	password string
	build    string
}

func (c config) ToDSN() string {
	return fmt.Sprintf("postgres://%s:%s@%s:%d/%s", c.user, c.password, c.host, c.port, c.database)
}

const (
	ENV_PGHOST     = `PGHOST`
	ENV_PGPORT     = `PGPORT`
	ENV_PGDATABASE = `PGDATABASE`
	ENV_PGUSER     = `PGUSER`
	ENV_PGPASSWORD = `PGPASSWORD`
	ENV_BUILD      = `PROMTOP_BUILD_TARGET`

	BUILD      string = `build`
	METRIC     string = `metric`
	VALUE      string = `value`
	QUERY_TIME string = `query_time`

	TIME_FORMAT = `2006-01-02 15:04:05`
)

func init() {
	exPath, _ := os.Executable()
	viper.SetConfigFile(filepath.Join(filepath.Dir(exPath), ".env"))
	viper.SetConfigType("dotenv")

	err := viper.BindEnv(ENV_BUILD, ENV_PGHOST, ENV_PGPORT, ENV_PGDATABASE, ENV_PGUSER, ENV_PGPASSWORD)
	if err != nil {
		log.Fatalf("failed to bind env vars: %v", err)
	}
	viper.AutomaticEnv()
	err = viper.ReadInConfig()
	if err != nil {
		log.Fatalf("read config file error: %v", err)
	}
}

func insertVector(vector model.Vector) error {
	cfg := config{
		host:     viper.GetString(ENV_PGHOST),
		port:     viper.GetInt(ENV_PGPORT),
		database: viper.GetString(ENV_PGDATABASE),
		user:     viper.GetString(ENV_PGUSER),
		password: viper.GetString(ENV_PGPASSWORD),
		build:    viper.GetString(ENV_BUILD),
	}

	db, err := sqlx.Connect("pgx", cfg.ToDSN())
	if err != nil {
		log.Fatalf("database connection error: %v", err)
	}

	sq := squirrel.Insert("metrics").Columns(BUILD, METRIC, VALUE, QUERY_TIME).RunWith(db).PlaceholderFormat(squirrel.Dollar)
	for _, s := range vector {
		sq = sq.Values(cfg.build, s.Metric.String(), s.Value.String(), s.Timestamp.Time().Format(TIME_FORMAT))
	}
	c, _, err := sq.ToSql()
	if err != nil {
		return err
	}
	log.Printf("query: %s", c)
	_, err = sq.Exec()
	if err != nil {
		return fmt.Errorf("query exec error: %v", err)
	}
	return nil
}
