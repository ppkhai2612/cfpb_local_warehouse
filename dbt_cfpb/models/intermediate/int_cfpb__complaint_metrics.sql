{{
    config(
        materialized="view"
    )
}}

with enriched as (
    select
        *,

        -- no. days to forward complaint to company
        datediff('day', date_received, date_sent_to_company) as days_to_response,

        -- flag for timely response
        case
            when timely = 'Yes' then true
            when timely = 'No' then false
            else null
        end as is_timely_response,

        -- extract year and month for time-based analysis
        extract(year from date_received) as complaint_year,
        extract(month from date_received) as complaint_month,
        date_trunc('month', date_received) as complaint_month_date

    from {{ ref('stg_cfpb__complaints') }} 
)

select * from enriched