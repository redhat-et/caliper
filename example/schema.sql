--
-- PostgreSQL database dump
--

-- Dumped from database version 13.2 (Debian 13.2-1.pgdg100+1)
-- Dumped by pg_dump version 13.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: collated_metrics; Type: TABLE; Schema: public; Owner: caliper_user
--

CREATE TABLE public.collated_metrics (
    version text NOT NULL,
    metric text NOT NULL,
    node text NOT NULL,
    pod text NOT NULL,
    namespace text NOT NULL,
    label_app text,
    avg_value numeric,
    q95_value numeric,
    max_value numeric,
    min_value numeric,
    inst_value numeric,
    query_time timestamp without time zone,
    range text NOT NULL
);


ALTER TABLE public.collated_metrics OWNER TO caliper_user;

--
-- PostgreSQL database dump complete
--

