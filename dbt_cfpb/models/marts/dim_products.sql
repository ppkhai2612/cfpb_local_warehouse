
with product_stats as (
    select

        product,
        sub_product,
        
        -- complaint counts
        count(*) as total_complaints,
        count(distinct company) as unique_companies,
        count(distinct state) as unique_states,
        
        -- metrics
        -- count_if(is_consumer_disputed) as disputed_complaints,
        -- round(100.0 * count_if(is_consumer_disputed) / count(*), 2) as pct_disputed_complaints,
        
        -- timely response metrics
        count_if(is_timely_response) as timely_responses,
        round(100.0 * count_if(is_timely_response) / count(*), 2) as pct_timely,
        
        -- narrative metrics
        count_if(has_narrative) as complaints_with_narrative,
        round(100.0 * count_if(has_narrative) / count(*), 2) as pct_with_narrative,
        
        -- response time metrics
        round(avg(days_to_response), 2) as avg_days_to_response,
        median(days_to_response) as median_days_to_response,

        -- date range
        min(date_received) as first_complaint_date,
        max(date_received) as last_complaint_date,
        
        -- most common metrics
        mode() within group (order by issue) as most_commmon_issue,
        mode() within group (order by company) as most_complained_company

    from {{ ref('int_cfpb__complaint_metrics') }}
    where product is not null
    group by product, sub_product
),

product_totals as (
    select
        product,
        null as sub_product,

        -- complaint counts
        sum(total_complaints) as total_complaints,
        count(distinct unique_companies) as unique_companies,
        count(distinct unique_states) as unique_states,

        -- timely reponse metrics
        sum(timely_responses) as timely_responses,
        round(100.0 * sum(timely_responses) / sum(total_complaints), 2) as pct_timely,

        -- sum(disputed_complaints) as disputed_complaints,
        -- round(100.0 * sum(disputed_complaints) / sum(total_complaints), 2) as pct_disputed,

        -- narrative metrics
        sum(complaints_with_narrative) as complaints_with_narrative,
        round(100.0 * sum(complaints_with_narrative) / sum(total_complaints), 2) as pct_with_narrative,

        -- response time metrics
        round(avg(avg_days_to_response), 2) as avg_days_to_response,
        round(avg(median_days_to_response), 2) as median_days_to_response,

        -- date range
        min(first_complaint_date) as first_complaint_date,
        max(last_complaint_date) as last_complaint_date,

        -- most common metrics
        mode() within group (order by most_commmon_issue) as most_commmon_issue,
        mode() within group (order by most_complained_company) as most_complained_company
    
    from product_stats
    group by product
)

select * from product_stats
union all
select * from product_totals
order by product, sub_product nulls first