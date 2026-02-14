from datetime import datetime, timedelta, date
from typing import Tuple


def get_date_range(filter_type: str) -> Tuple[date, date]:
    """
    Returns (start_date, end_date) for filter types.
    
    Supported filter types:
    - 'today': Current day
    - 'yesterday': Previous day
    - 'this_week' or 'current_week': Monday to Sunday of current week
    - 'last_week': Monday to Sunday of previous week
    - 'this_month': First to last day of current month
    - 'last_month': First to last day of previous month
    - 'this_year': First to last day of current year
    - 'last_year': First to last day of previous year
    """
    today = date.today()
    
    if filter_type == 'today':
        return (today, today)
    
    elif filter_type == 'yesterday':
        yesterday = today - timedelta(days=1)
        return (yesterday, yesterday)
    
    elif filter_type == 'this_week' or filter_type == 'current_week':
        # Monday of current week (weekday: 0=Monday, 6=Sunday)
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)  # Sunday
        return (start, end)
    
    elif filter_type == 'last_week':
        # Monday of last week
        current_week_start = today - timedelta(days=today.weekday())
        start = current_week_start - timedelta(days=7)
        end = start + timedelta(days=6)  # Sunday
        return (start, end)
    
    elif filter_type == 'this_month':
        start = today.replace(day=1)
        # Last day of current month
        if today.month == 12:
            end = today.replace(day=31)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
            end = next_month - timedelta(days=1)
        return (start, end)
    
    elif filter_type == 'last_month':
        # First day of last month
        first_of_this_month = today.replace(day=1)
        last_of_last_month = first_of_this_month - timedelta(days=1)
        start = last_of_last_month.replace(day=1)
        end = last_of_last_month
        return (start, end)
    
    elif filter_type == 'this_year':
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
        return (start, end)
    
    elif filter_type == 'last_year':
        last_year = today.year - 1
        start = date(last_year, 1, 1)
        end = date(last_year, 12, 31)
        return (start, end)
    
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")
