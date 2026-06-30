select
    order_date,
    count(*)            as order_count,
    sum(order_amount)   as total_amount
from {{ ref('stg_orders') }}
group by order_date
