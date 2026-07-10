
with state_stats as (

    select
        state,

        -- complaint counts
        count(*) as total_complaints,
        count(distinct company) as unique_companies,
        count(distinct product) as unique_products,
        count(distinct issue) as unique_issues,
        count(distinct zip_code) as unique_zip_codes,

        -- metrics
        -- count_if(is_consumer_disputed) as disputed_complaints,
        -- round(100.0 * count_if(is_consumer_disputed) / count(*), 2) as pct_disputed_complaints,
        
        -- timely reponse metrics
        count_if(is_timely_response) as timely_responses,
        round(100.0 * count_if(is_timely_response) / count(*), 2) as pct_timely,
        
        -- narrative metrics
        count_if(has_narrative) as complaints_with_narrative,
        round(100.0 * count_if(has_narrative) / count(*), 2) as pct_with_narrative,
        
        -- response time metrics
        round(avg(days_to_response), 2) as avg_days_to_response,
        median(days_to_response) as median_days_to_response,
        min(days_to_response) as min_days_to_response,
        max(days_to_response) as max_days_to_response,

        -- date range
        min(date_received) as first_complaint_date,
        max(date_received) as last_complaint_date,
        
        -- most common metrics
        mode() within group (order by issue) as most_commmon_issue,
        mode() within group (order by product) as most_common_product,
        mode() within group (order by submitted_via) as most_common_submission_method,
        mode() within group (order by company) as most_complained_company

    from {{ ref('int_cfpb__complaint_metrics') }}
    where state is not null
    group by state
)

select *
from state_stats
order by total_complaints desc