# services/email_service.py
# This script uses the resend library to manage all outgoing email communications.
# It is configured to pull the necessary API key and sender information directly from your .env file.

import os
from typing import Dict

import resend
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
# Initialise the Resend client with the API key from your .env file.
# Ensure RESEND_API_KEY is set.
resend.api_key = os.getenv("RESEND_API_KEY")

# Fetch sender details from environment variables for flexible configuration.
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_NAME = os.getenv("SENDER_NAME", "Kai from Tenacious")


def send_email(to_email: str, subject: str, body: str) -> Dict:
    """
    Sends an email using the Resend API.

    Args:
        to_email: The recipient's email address.
        subject: The subject line of the email.
        body: The plain text body of the email.

    Returns:
        A dictionary containing the API response from Resend or an error message.
    """
    if not resend.api_key:
        error_msg = "Error: RESEND_API_KEY is not set in environment variables."
        print(error_msg)
        return {"error": error_msg}

    if not SENDER_EMAIL:
        error_msg = "Error: SENDER_EMAIL is not configured in environment variables."
        print(error_msg)
        return {"error": error_msg}

    params = {
        "from": f"{SENDER_NAME} <{SENDER_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "html": body.replace(
            "\n", "<br>"
        ),  # Basic conversion of newlines to <br> for HTML clients
        "text": body,
    }

    try:
        print(f"Sending email via Resend to: {to_email} with subject: '{subject}'")
        email_response = resend.Emails.send(params)
        print("Email sent successfully.")
        return email_response
    except Exception as e:
        error_msg = f"Failed to send email via Resend: {e}"
        print(error_msg)
        return {"error": str(e)}


if __name__ == "__main__":
    # --- Example Usage ---
    # To run this test, ensure your .env file in the project root contains:
    # RESEND_API_KEY="re_..."
    # SENDER_EMAIL="your_verified_resend_domain_email"
    # SENDER_NAME="Your Name"
    # TARGET_EMAIL="a_test_recipient@example.com"

    target_email = os.getenv("TARGET_EMAIL")

    if not target_email:
        print("Skipping email_service test: TARGET_EMAIL not set in .env file.")
    else:
        print("\n--- Testing Email Service ---")
        test_subject = "Test from the Conversion Engine"
        test_body = "Hello there,\n\nThis is a test to confirm the Resend service is correctly configured.\n\nBest,\nKai"

        response = send_email(
            to_email=target_email, subject=test_subject, body=test_body
        )

        if "error" in response:
            print(f"Test Failed. Error: {response['error']}")
        else:
            print("Test Succeeded. Response from Resend:")
            print(response)
