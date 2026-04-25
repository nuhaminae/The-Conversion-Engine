# services/hubspot_service.py

# This script handles all interactions with the HubSpot CRM using the official hubspot-api-client.
# It provides functions to find, create, and update contacts, which are essential for tracking the prospect's journey.

import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv

load_dotenv()
from hubspot import HubSpot
from hubspot.crm.contacts import PublicObjectSearchRequest, SimplePublicObjectInput

# --- Configuration ---
hubspot_client = HubSpot(access_token=os.getenv("HUBSPOT_API_KEY"))


def find_contact_by_email(email: str) -> Optional[str]:
    """Finds a HubSpot contact by their email address."""
    if not os.getenv("HUBSPOT_API_KEY"):
        print("Error: HUBSPOT_API_KEY not set.")
        return None

    search_request = PublicObjectSearchRequest(
        filter_groups=[
            {"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}
        ],
        properties=["email"],
    )
    try:
        print(f"Searching for HubSpot contact with email: {email}")
        response = hubspot_client.crm.contacts.search_api.do_search(
            public_object_search_request=search_request
        )
        if response.total > 0:
            contact_id = response.results[0].id
            print(f"Contact found with ID: {contact_id}")
            return contact_id
        else:
            print("Contact not found.")
            return None
    except Exception as e:
        print(f"An error occurred while searching for contact: {e}")
        return None


def create_contact(
    email: str, firstname: str, lastname: str, company: str
) -> Optional[str]:
    """
    Creates a new contact in HubSpot with only core contact information.
    The hs_lead_status will be set in a subsequent update call.
    """
    if not os.getenv("HUBSPOT_API_KEY"):
        print("Error: HUBSPOT_API_KEY not set.")
        return None

    # REVISED: Create contact with only the guaranteed core properties first.
    properties = {
        "email": email,
        "firstname": firstname,
        "lastname": lastname,
        "company": company,
    }
    contact_input = SimplePublicObjectInput(properties=properties)

    try:
        print(f"Creating new HubSpot contact for: {email} with core info.")
        response = hubspot_client.crm.contacts.basic_api.create(
            simple_public_object_input_for_create=contact_input
        )
        contact_id = response.id
        print(f"Successfully created contact with ID: {contact_id}")
        return contact_id
    except Exception as e:
        print(f"An error occurred while creating contact: {e}")
        return None


def update_contact_property(contact_id: str, properties: Dict[str, Any]) -> bool:
    """Updates properties for an existing HubSpot contact."""
    if not os.getenv("HUBSPOT_API_KEY"):
        print("Error: HUBSPOT_API_KEY not set.")
        return False

    contact_input = SimplePublicObjectInput(properties=properties)
    try:
        print(
            f"Updating HubSpot contact ID: {contact_id} with properties: {properties}"
        )
        hubspot_client.crm.contacts.basic_api.update(
            contact_id=contact_id, simple_public_object_input=contact_input
        )
        print("Contact updated successfully.")
        return True
    except Exception as e:
        print(f"An error occurred while updating contact: {e}")
        return False

def get_contact_property(contact_id: str, property_name: str) -> Optional[str]:
    """Fetches a specific property value for a HubSpot contact."""
    if not os.getenv("HUBSPOT_API_KEY"):
        print("Error: HUBSPOT_API_KEY not set.")
        return None

    try:
        print(f"Fetching property '{property_name}' for HubSpot contact ID: {contact_id}")
        contact = hubspot_client.crm.contacts.basic_api.get_by_id(
            contact_id, properties=[property_name]
        )
        return contact.properties.get(property_name)
    except Exception as e:
        print(f"An error occurred while fetching contact property: {e}")
        return None

if __name__ == "__main__":
    # --- Example Usage ---

    if not os.getenv("HUBSPOT_API_KEY"):
        print("Skipping hubspot_service test: HUBSPOT_API_KEY not set in .env file.")
    else:
        print("\n--- Testing HubSpot Service ---")
        test_email = "hubspot-test-contact-2@tenacious-demo.com"  # Using a new email for a clean test

        # 1. Try to find the contact
        existing_id = find_contact_by_email(test_email)

        # 2. If not found, create it
        if not existing_id:
            contact_id = create_contact(
                email=test_email,
                firstname="HubSpot",
                lastname="Test Two",
                company="Tenacious Demo Inc.",
            )
        else:
            contact_id = existing_id

        # 3. Update the contact's hs_lead_status property
        if contact_id:
            # Now we set the sales property in an update call
            success = update_contact_property(
                contact_id,
                {
                    "hs_lead_status": "NEW"
                },  # Use a valid default option for hs_lead_status
            )
            if success:
                print("Test Succeeded: Contact found/created and lead status updated.")
            else:
                print("Test Failed: Could not update hs_lead_status.")
        else:
            print("Test Failed: Could not find or create contact.")
