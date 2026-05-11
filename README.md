# JobSphere API

Real-time job listings, salary insights, and market trends — powered by Adzuna.

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /jobs/search` | Search live job listings by keyword and country |
| `GET /jobs/salary` | Salary insights for any job title |
| `GET /jobs/trending` | Vacancy trends over time by country |
| `GET /jobs/categories` | All job categories for a country |

## Supported Countries

`us` `gb` `au` `ca` `de` `fr` `in` `sg` `nl` `za`

## Quick Start

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

API docs available at `http://localhost:8000/docs`
