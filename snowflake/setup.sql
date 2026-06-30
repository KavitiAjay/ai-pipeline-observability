-- Setup objects for the dbt failure analysis pipeline.
-- Run as a role that can create databases and use Cortex.

USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS ANALYTICS;
CREATE SCHEMA IF NOT EXISTS ANALYTICS.OBSERVABILITY;

CREATE WAREHOUSE IF NOT EXISTS DE_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE;

-- Table that stores the LLM classification of each failure.
CREATE TABLE IF NOT EXISTS ANALYTICS.OBSERVABILITY.DBT_FAILURE_ANALYSIS (
    run_id            STRING,
    node_name         STRING,
    status            STRING,
    raw_message       STRING,
    category          STRING,   -- e.g. SCHEMA_DRIFT, PERMISSION, DATA_QUALITY, SYNTAX
    likely_fix        STRING,
    severity          STRING,   -- LOW, MEDIUM, HIGH
    classified_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Example of the Cortex call the Python loader runs per failure.
-- Kept here so reviewers can see the prompt without reading Python.
/*
SELECT SNOWFLAKE.CORTEX.COMPLETE(
    'mistral-large2',
    'You are a dbt failure triage assistant. Classify the failure below and respond ONLY '
    || 'with JSON: {"category":..., "likely_fix":..., "severity":...}. '
    || 'category is one of SCHEMA_DRIFT, PERMISSION, DATA_QUALITY, SYNTAX, RESOURCE, OTHER. '
    || 'Failure message: ' || :error_text
);
*/
