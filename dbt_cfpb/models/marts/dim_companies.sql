with company_stats as (
    select
        company,

        -- complaint counts
        count(*) as total_complaints,
        countif(is_timely_response) as timely_responses,
        countif(has_narrative) as complaints_with_narrative,

        -- percentages        
        round(countif(is_timely_response) / count(*) * 100.0, 2) as pct_timely,


        -- response time metrics
        round(avg(days_to_response), 2) as avg_days_to_response,
        median(days_to_response) as median_days_to_response,
        min(days_to_response) as min_days_to_response,
        max(days_to_response) as max_days_to_response,

        -- date range
        min(date_received) as first_complaint_date,
        max(date_received) as last_complaint_date

    from {{ ref('int_cfpb__complaint_metrics') }}
    where company is not null
    group by company
)

select * from company_stats
order by total_complaints desc