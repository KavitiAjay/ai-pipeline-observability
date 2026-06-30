-- INTENTIONALLY BROKEN so the analyzer has a real failure to classify on first run.
-- The column o_total_amount does not exist in the TPCH source (it is o_totalprice).
-- Fix the column name to make the pipeline pass once you have seen the triage work.
select
    o_orderkey      as order_id,
    o_custkey       as customer_id,
    o_total_amount  as order_amount,   -- wrong column on purpose
    o_orderdate     as order_date
from snowflake_sample_data.tpch_sf1.orders
