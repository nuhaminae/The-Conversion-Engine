# enrichment/core.py
# 
# Orchestrator that calls the other scripts, gathers all the data, and performs a basic analysis to generate the `hiring_signal_brief.json`.
#

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# --- Custom Modules ---
from . import crunchbase, jobs, layoffs

# --- Configuration ---
# Make file paths robust by basing them on this file's location
BASE_DIR = (
    Path(__file__).resolve().parent.parent
)  # This gets the project root directory
CRUNCHBASE_FILE_PATH = BASE_DIR / "data" / "crunchbase_odm.csv"
LAYOFFS_FILE_PATH = BASE_DIR / "data" / "layoffs.csv"


async def enrich_prospect(company_name: str, jobs_page_url: str) -> Dict[str, Any]:
    """
    Orchestrates the enrichment process. It will gracefully handle if the
    Crunchbase file is missing.
    """
    print(f"Starting enrichment for '{company_name}'...")

    # --- Handle optional Crunchbase data ---
    # We will build the list of tasks to run dynamically.
    tasks_to_run = [
        asyncio.to_thread(layoffs.get_layoff_info, company_name, LAYOFFS_FILE_PATH),
        jobs.scrape_job_postings(company_name, jobs_page_url),
    ]

    cb_data = None
    if CRUNCHBASE_FILE_PATH.exists():
        print("Crunchbase file found. Including it in enrichment.")
        # If the file exists, add the task to the list
        crunchbase_task = asyncio.to_thread(
            crunchbase.get_crunchbase_info, company_name, CRUNCHBASE_FILE_PATH
        )
        tasks_to_run.insert(0, crunchbase_task)  # Add it to the front

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks_to_run)
        cb_data, layoff_data, job_data = results
    else:
        print("Warning: Crunchbase file not found. Proceeding without Crunchbase data.")
        # Run only the layoff and jobs tasks
        results = await asyncio.gather(*tasks_to_run)
        layoff_data, job_data = results
        cb_data = {"error": "Crunchbase data not available."}

    print("Data gathering complete. Analyzing and building brief...")

    # --- Analysis (remains the same) ---
    hiring_velocity = "Not available"
    if job_data["status"] == "success":
        job_count = job_data["job_count"]
        if job_count > 20:
            hiring_velocity = "High"
        elif job_count > 5:
            hiring_velocity = "Medium"
        elif job_count > 0:
            hiring_velocity = "Low"
        else:
            hiring_velocity = "None"

    is_hiring_leadership = any(
        "manager" in j["title"].lower()
        or "director" in j["title"].lower()
        or "vp" in j["title"].lower()
        or "head of" in j["title"].lower()
        for j in job_data.get("jobs", [])
    )

    layoff_summary = (
        f"{len(layoff_data)} layoff events found."
        if layoff_data
        else "No recent layoff events found."
    )

    # --- Brief Construction (remains the same) ---
    brief = {
        "brief_version": "1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "prospect_company": company_name,
        "crunchbase_summary": cb_data,  # This contains the error or be null
        "recent_layoffs": {"summary": layoff_summary, "data": layoff_data or []},
        "job_postings": {
            "scrape_status": job_data["status"],
            "jobs_page_url": job_data["jobs_page_url"],
            "error_message": job_data["error"],
            "job_count": job_data.get("job_count", 0),
            "postings": job_data.get("jobs", []),
        },
        "derived_signals": {
            "confidence": "Medium",
            "hiring_velocity": hiring_velocity,
            "is_hiring_leadership": is_hiring_leadership,
            "summary": f"{company_name} shows a '{hiring_velocity}' hiring velocity with {job_data.get('job_count', 0)} open roles. "
            f"Leadership hiring is {'detected' if is_hiring_leadership else 'not detected'}. "
            f"{layoff_summary}",
        },
    }

    return brief
