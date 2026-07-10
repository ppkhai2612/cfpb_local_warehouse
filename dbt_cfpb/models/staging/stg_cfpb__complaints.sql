{{
    config(
        materialized='view'
    )
}}

select 
    -- identifiers
    complaint_id,

    -- dimensions
    product,
    sub_product,
    issue,
    sub_issue,
    company,
    state,
    zip_code,
    submitted_via,

    -- dates
    date_received::date as date_received,
    date_sent_to_company::date as date_sent_to_company,

    -- responses
    company_response,
    company_public_response,

    -- flags
    timely,
    has_narrative,
    
    -- text
    complaint_what_happened,
    tags,
    
    -- metadata
    extracted_at as dbt_extracted_at,
    -- _dlt_load_id as dbt_load_id

-- from read_parquet('s3://local-lakehouse/cfpb_complaints/bronze/**/*.parquet')
from {{ source('raw', 'cfpb_complaints') }}


-- from READ_PARQUET('s3://raw/cfpb_complaints/**/*.parquet')