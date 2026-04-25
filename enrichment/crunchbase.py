# enrichment/crunchbase.py
# To load the Crunchbase data and provide a clean function to query it for a specific company.

from typing import Any, Dict, Optional

import pandas as pd


def get_crunchbase_info(
    company_name: str, crunchbase_file_path: str
) -> Optional[Dict[str, Any]]:
    """
    Searches for a company in the Crunchbase ODM CSV and returns its data.

    Args:
        company_name: The name of the company to search for (case-insensitive).
        crunchbase_file_path: The path to the crunchbase_odm.csv file.

    Returns:
        A dictionary containing the company's data if found, otherwise None.
    """
    try:
        df = pd.read_csv(crunchbase_file_path)

        # Normalise company name for a more robust search
        search_name = company_name.strip().lower()

        # Find the company, ignoring case
        result_df = df[df["name"].str.lower() == search_name]

        if not result_df.empty:
            # Return the first match as a dictionary
            company_data = result_df.iloc[0].to_dict()
            # Clean up NaN values to None for better JSON compatibility
            return {k: (None if pd.isna(v) else v) for k, v in company_data.items()}

    except FileNotFoundError:
        print(f"Error: Crunchbase file not found at {crunchbase_file_path}")
        return None
    except Exception as e:
        print(f"An error occurred while processing the Crunchbase file: {e}")
        return None

    return None


if __name__ == "__main__":
    # Example usage:
    # This assumes your crunchbase_odm.csv is in a 'data' folder at the root of the project
    relative_path = "../../data/crunchbase_odm.csv"

    # Test case 1: Company exists
    company_info = get_crunchbase_info("Gainsight", relative_path)
    if company_info:
        print("Found Gainsight:")
        print(f"  - Description: {company_info.get('short_description')}")
        print(f"  - Country: {company_info.get('country_code')}")
        print(f"  - Total Funding: ${company_info.get('funding_total_usd', 0):,}")
    else:
        print("Gainsight not found.")

    # Test case 2: Company does not exist
    company_info_none = get_crunchbase_info("NonExistent Company", relative_path)
    if not company_info_none:
        print("\n'NonExistent Company' not found, as expected.")
