# enrichment/layoffs.py
# Similar to the Crunchbase script, this handles querying the layoff data.

from typing import Any, Dict, List, Optional

import pandas as pd


def get_layoff_info(
    company_name: str, layoffs_file_path: str
) -> Optional[List[Dict[str, Any]]]:
    """Searches for a company in the layoffs.fyi CSV and returns its layoff data."""
    try:
        df = pd.read_csv(layoffs_file_path)
        search_name = company_name.strip().lower()

        # Use the case-sensitive column name 'Company' from the CSV file.
        result_df = df[df["Company"].str.lower() == search_name]

        if not result_df.empty:
            layoff_events = result_df.to_dict(orient="records")
            return layoff_events
    except FileNotFoundError:
        print(f"Error: Layoffs file not found at {layoffs_file_path}")
        return None
    except Exception as e:
        print(f"An error occurred while processing the layoffs file: {e}")
        return None

    return None


if __name__ == "__main__":
    # Example usage:
    # Assumes your layoffs.csv is in a 'data' folder at the root of the project
    relative_path = "../../data/layoffs.csv"

    # Test case 1: Company with layoffs
    layoff_info = get_layoff_info("Meta", relative_path)
    if layoff_info:
        print(f"Found {len(layoff_info)} layoff events for Meta:")
        for event in layoff_info:
            print(f"  - Date: {event.get('date')}, Laid Off: {event.get('laid_off')}")
    else:
        print("Meta not found or has no recorded layoffs.")

    # Test case 2: Company with no recorded layoffs
    layoff_info_none = get_layoff_info("Tenacious Consulting", relative_path)
    if not layoff_info_none:
        print("\n'Tenacious Consulting' not found, as expected.")
