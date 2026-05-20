import re


def standardize_company_name(name: str) -> str:
    """Stadardize the company name, which is used in filenames
    
    Params:
        name: A company name to standardize (e.g., Early Warning Services, LLC)

    Returns:
        A standardized company name (e.g., early_warning_services__llc)
    """
    # {safe_company}_{date_received_min}_{date_received_min + 1}.parquet
    return re.sub(r"[^a-z0-9_]", "_", name.strip().strip('.').lower())


def is_minio_running(minio_client):
    """Check if MinIO instance is running"""
    try:
        # perform any operation to check if MinIO is running, e.g., list buckets
        minio_client.list_buckets()
        return True
    except Exception:
        # any errors happen, return False
        return False


print(standardize_company_name("Early Warning Services, LLC"))
print(standardize_company_name("Kriya Capital, LLC"))
