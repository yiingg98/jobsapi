from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from typing import Optional
from datetime import datetime

app = FastAPI(
    title="JobSphere API",
    description="Real-time job listings, salary data, and market trends powered by Adzuna.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "be7a9442")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "1128b1012a494fdda131cf149247c9f3")
ADZUNA_BASE = "https://api.adzuna.com/v1/api"


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {
        "name": "JobSphere API",
        "version": "1.0.0",
        "status": "live",
        "endpoints": ["/jobs/search", "/jobs/salary", "/jobs/trending", "/jobs/categories"],
        "docs": "/docs"
    }


@app.get("/jobs/search")
async def search_jobs(
    keyword: str = Query(..., description="Job title or skill, e.g. 'python developer'"),
    country: str = Query("gb", description="Country code: us, gb, au, ca, de, fr, in, sg, nl, za"),
    page: int = Query(1, description="Page number"),
    results: int = Query(10, description="Results per page (max 50)", le=50),
    location: Optional[str] = Query(None, description="City or region, e.g. 'London'"),
    salary_min: Optional[int] = Query(None, description="Minimum salary filter"),
    full_time: Optional[bool] = Query(None, description="Filter full-time jobs only")
):
    """
    Search live job listings by keyword and country.
    Returns job title, company, location, salary, description, and apply URL.
    """
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": results,
        "what": keyword,
        "content-type": "application/json"
    }
    if location:
        params["where"] = location
    if salary_min:
        params["salary_min"] = salary_min
    if full_time:
        params["full_time"] = 1

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{ADZUNA_BASE}/jobs/{country}/search/{page}", params=params)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="Adzuna API error")
        except Exception:
            raise HTTPException(status_code=503, detail="Could not reach job data source")

    jobs = []
    for job in data.get("results", []):
        jobs.append({
            "id": job.get("id"),
            "title": job.get("title"),
            "company": job.get("company", {}).get("display_name"),
            "location": job.get("location", {}).get("display_name"),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "description": job.get("description", "")[:300] + "...",
            "url": job.get("redirect_url"),
            "created": job.get("created"),
            "category": job.get("category", {}).get("label")
        })

    return {
        "keyword": keyword,
        "country": country,
        "total_results": data.get("count", 0),
        "page": page,
        "results_shown": len(jobs),
        "jobs": jobs
    }


@app.get("/jobs/salary")
async def salary_data(
    keyword: str = Query(..., description="Job title, e.g. 'data scientist'"),
    country: str = Query("gb", description="Country code: us, gb, au, ca, de, fr, in, sg, nl, za"),
    location: Optional[str] = Query(None, description="City or region")
):
    """
    Get salary insights for a specific job title and country.
    Returns average, min, max salary and number of jobs sampled.
    """
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": keyword,
        "content-type": "application/json"
    }
    if location:
        params["where"] = location

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{ADZUNA_BASE}/jobs/{country}/histogram", params=params)
            r.raise_for_status()
            hist = r.json()

            r2 = await client.get(f"{ADZUNA_BASE}/jobs/{country}/search/1", params={**params, "results_per_page": 1})
            r2.raise_for_status()
            search = r2.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="Adzuna API error")
        except Exception:
            raise HTTPException(status_code=503, detail="Could not reach salary data source")

    histogram = hist.get("histogram", {})
    salaries = [float(k) for k in histogram.keys() if histogram[k] > 0]

    return {
        "keyword": keyword,
        "country": country,
        "location": location or "nationwide",
        "salary_insights": {
            "average": round(sum(salaries) / len(salaries), 2) if salaries else None,
            "min_bracket": min(salaries) if salaries else None,
            "max_bracket": max(salaries) if salaries else None,
            "salary_distribution": histogram
        },
        "total_jobs_with_salary": search.get("count", 0),
        "note": "Salaries in local currency per year"
    }


@app.get("/jobs/trending")
async def trending_jobs(
    country: str = Query("gb", description="Country code: us, gb, au, ca, de, fr, in, sg, nl, za"),
    category: Optional[str] = Query(None, description="Category tag e.g. 'it-jobs', 'engineering-jobs'")
):
    """
    Get trending job categories and vacancy counts for a country.
    Useful for understanding which roles are in highest demand.
    """
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "content-type": "application/json"
    }
    if category:
        params["category"] = category

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{ADZUNA_BASE}/jobs/{country}/history", params=params)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="Adzuna API error")
        except Exception:
            raise HTTPException(status_code=503, detail="Could not reach trend data source")

    month_data = data.get("month", {})
    trend_list = [{"month": k, "vacancies": v} for k, v in sorted(month_data.items())]

    return {
        "country": country,
        "category": category or "all",
        "trend": trend_list,
        "latest_vacancy_count": trend_list[-1]["vacancies"] if trend_list else None,
        "fetched_at": datetime.utcnow().isoformat()
    }


@app.get("/jobs/categories")
async def job_categories(
    country: str = Query("gb", description="Country code: us, gb, au, ca, de, fr, in, sg, nl, za")
):
    """
    List all available job categories for a given country.
    Use the 'tag' field as the category parameter in other endpoints.
    """
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "content-type": "application/json"
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{ADZUNA_BASE}/jobs/{country}/categories", params=params)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="Adzuna API error")
        except Exception:
            raise HTTPException(status_code=503, detail="Could not reach category data source")

    categories = [
        {"label": c.get("label"), "tag": c.get("tag")}
        for c in data.get("results", [])
    ]

    return {
        "country": country,
        "total_categories": len(categories),
        "categories": categories
    }
