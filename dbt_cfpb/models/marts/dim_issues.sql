
with issue_stats as (
    select
        issue,
        sub_issue,

        -- complaint counts
        count(*) as total_complaints,
        count(distinct company) as unique_companies,
        count(distinct product) as unique_products,
        count(distinct state) as unique_states,

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
        mode() within group (order by product) as most_common_product,
        mode() within group (order by company) as most_complained_company

    from {{ ref('int_cfpb__complaint_metrics') }}
    where issue is not null
    group by issue, sub_issue
),

issue_totals as (
    select
        issue,
        null as sub_issue,

        -- complaint counts
        sum(total_complaints) as total_complaints,
        count(distinct unique_companies) as unique_companies,
        count(distinct unique_products) as unique_products,
        count(distinct unique_states) as unique_states,

        -- timely response metrics
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
        mode() within group (order by most_common_product) as most_common_product,
        mode() within group (order by most_complained_company) as most_complained_company

    from issue_stats
    group by issue
)

select * from issue_stats
union all
select * from issue_totals
order by issue, sub_issue nulls first