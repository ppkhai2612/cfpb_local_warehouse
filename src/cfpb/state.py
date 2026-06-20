"""Pipeline State Management

This script includes state-relevant functions that support for full/incremental load process
"""

from pathlib import Path
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Variable for tracking state file
STATE_FILE = Path("state.json")


def reset_state():
    """Function to reset the state file"""
    
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        logger.info("State file deleted")
    else:
        logger.info("State file does not exist")


def get_last_loaded_date():
    """Get the last loaded date from the state file

    Returns:
        The last loaded date (YYYY-MM-DD), or None if no previous load exists
    """
    if not STATE_FILE.exists():
        return None

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            return state.get("last_loaded_date")
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Error happens while reading or decoding the JSON file: {e}")
        return None


def get_next_load_date(start_date):
    """Determine the date range for the next load

    Params:
        start_date: The date to start the load from (for full load)

    Returns:
        A tuple of (start date / next date, today) for the next load
    """
    today = datetime.now().strftime("%Y-%m-%d")
    last_loaded_date = get_last_loaded_date()

    # Full load
    if last_loaded_date is None:
        logger.info(f"Full loading: {start_date} to {today}")
        return start_date, today

    # Incremental load
    last_date_obj = datetime.strptime(last_loaded_date, "%Y-%m-%d")
    next_date_obj = last_date_obj + timedelta(days=1)
    next_date = next_date_obj.strftime("%Y-%m-%d")

    logger.info(f"Incremental loading: {next_date} to {today}")
    return next_date, today

# print(get_next_load_date("2026-03-23")) # ('2026-03-23', '2026-03-28')

def update_last_loaded_date(date):
    """Function to update the last loaded date in the state file
    
    Params:
        date: The last loaded date (YYYY-MM-DD)
    """
    state = {
        "last_loaded_date": date,
        "updated_at": datetime.now().isoformat()
    }

    try:
        with open(STATE_FILE, "w") as file:
            json.dump(state, file, indent=2)
        logger.info(f"State is updated with last_loaded_date: {date}")
    except OSError as e:
        logger.error(f"Errors when updating state file: {e}")
        raise