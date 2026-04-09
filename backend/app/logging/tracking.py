"""Tracking ID generator for error reporting."""

import random
import string

from app.utils.time import utc_now

def generate_tracking_id():
    """Generate a unique tracking ID for error reporting."""
    date_part = utc_now().strftime("%Y%m%d")
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ERR-{date_part}-{random_part}"
