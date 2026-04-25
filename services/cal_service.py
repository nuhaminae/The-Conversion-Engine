# services/cal_service.py
# This script's purpose is to generate the appropriate Cal.com booking link.
# Since the project uses a local instance of Cal.com via Docker, the base URL is configurable.
# This service is simple but essential for the "book a meeting" step of your funnel.

import os
from typing import Any, Dict, List

# --- Configuration ---
# The base URL for your Cal.com instance. Defaults to the local Docker setup.
# You can override this in your .env file if you deploy Cal.com elsewhere.
CAL_BASE_URL = os.getenv("CAL_COM_BASE_URL", "http://localhost:3000")

# The event type slug for the discovery call.
# This should match the event type you set up in your Cal.com instance.
DISCOVERY_CALL_SLUG = "discovery-call-15"


def get_booking_link(partner_name: str) -> str:
    """
    Generates a booking link for a specific partner at Tenacious.

    Args:
        partner_name: The name of the partner (e.g., "nuhamin"), which corresponds
                      to their Cal.com username.

    Returns:
        The full Cal.com booking link.
    """
    if not partner_name:
        raise ValueError("Partner name cannot be empty.")

    # The structure of a Cal.com link is {base_url}/{username}/{event_slug}
    booking_link = f"{CAL_BASE_URL}/{partner_name.lower()}/{DISCOVERY_CALL_SLUG}"

    print(f"Generated Cal.com booking link: {booking_link}")
    return booking_link


if __name__ == "__main__":
    # --- Example Usage ---
    print("\n--- Testing Cal.com Service ---")

    # Test case 1: Standard partner name
    partner = "nuhamin"
    link = get_booking_link(partner)
    print(f"Booking link for {partner}: {link}")
    expected_link = f"{CAL_BASE_URL}/nuhamin/{DISCOVERY_CALL_SLUG}"
    assert link == expected_link, f"Test Failed: Expected {expected_link}, got {link}"
    print("Test 1 Passed.")

    # Test case 2: Partner name with different casing
    partner_caps = "Sarah"
    link_caps = get_booking_link(partner_caps)
    print(f"Booking link for {partner_caps}: {link_caps}")
    expected_link_caps = f"{CAL_BASE_URL}/sarah/{DISCOVERY_CALL_SLUG}"
    assert (
        link_caps == expected_link_caps
    ), f"Test Failed: Expected {expected_link_caps}, got {link_caps}"
    print("Test 2 Passed.")

    # You can also test the environment variable override
    os.environ["CAL_COM_BASE_URL"] = "https://cal.tenacious.com"
    overridden_base_url = os.getenv("CAL_COM_BASE_URL")
    link_override = get_booking_link(partner)
    expected_override = f"{overridden_base_url}/nuhamin/{DISCOVERY_CALL_SLUG}"
    assert (
        link_override == expected_override
    ), f"Test Failed: Expected {expected_override}, got {link_override}"
    print(f"Booking link with overridden base URL: {link_override}")
    print("Test 3 Passed.")
