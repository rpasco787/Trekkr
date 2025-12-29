# Stats API Endpoints Design

## Overview

Add two REST endpoints to expose user travel statistics with coverage percentages and visit timestamps. These endpoints power the profile page's progress tracking features.

## Endpoints

### GET /api/v1/stats/countries

Returns all countries the authenticated user has visited with coverage statistics.

**Authentication:** Required (Bearer token)

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sort_by` | string | `last_visited_at` | Options: `coverage_pct`, `first_visited_at`, `last_visited_at`, `name` |
| `order` | string | `desc` | Options: `asc`, `desc` |
| `limit` | int | `50` | Max items to return (cap at 100) |
| `offset` | int | `0` | For pagination |

**Response (200 OK):**

```json
{
  "total_countries_visited": 5,
  "countries": [
    {
      "code": "USA",
      "name": "United States",
      "coverage_pct": 0.0005,
      "first_visited_at": "2024-03-15T10:30:00Z",
      "last_visited_at": "2025-12-20T14:22:00Z"
    }
  ]
}
```

### GET /api/v1/stats/regions

Returns all regions (states/provinces) the authenticated user has visited with coverage statistics.

**Authentication:** Required (Bearer token)

**Query Parameters:** Same as `/stats/countries`

**Response (200 OK):**

```json
{
  "total_regions_visited": 12,
  "regions": [
    {
      "code": "US-CA",
      "name": "California",
      "country_code": "USA",
      "country_name": "United States",
      "coverage_pct": 0.0076,
      "first_visited_at": "2024-03-15T10:30:00Z",
      "last_visited_at": "2025-12-18T09:15:00Z"
    }
  ]
}
```

## Implementation Approach

**Strategy:** Query on-the-fly (Option A)

Calculate statistics at request time by joining:
- `user_cell_visits` (user's visited cells)
- `h3_cells` (cell → region mapping)
- `regions_country` / `regions_state` (region metadata + total cell counts)

**Why this approach:**
- Simpler implementation, no sync logic
- Fast enough for MVP (< 100ms for realistic user data)
- All required indexes already exist
- Can optimize to pre-computed stats later if needed

## Data Flow

```
Request → Router → StatsService → Database Query → Response
```

### Countries Query Logic

```sql
SELECT
    c.iso3 as code,
    c.name,
    COUNT(ucv.id) as cells_visited,
    c.land_cells_total_resolution8 as cells_total,
    MIN(ucv.first_visited_at) as first_visited_at,
    MAX(ucv.last_visited_at) as last_visited_at
FROM user_cell_visits ucv
JOIN h3_cells h ON ucv.h3_index = h.h3_index
JOIN regions_country c ON h.country_id = c.id
WHERE ucv.user_id = :user_id AND ucv.res = 8
GROUP BY c.id
ORDER BY last_visited_at DESC
LIMIT :limit OFFSET :offset
```

Coverage percentage calculated as: `cells_visited / cells_total`

### Regions Query Logic

Similar query but joins to `regions_state` and includes parent country info.

## File Structure

```
backend/
├── routers/
│   └── stats.py          # New router
├── services/
│   └── stats_service.py  # New service
└── schemas/
    └── stats.py          # New schemas
```

## Schema Definitions

### Pydantic Models

```python
class CountryStatResponse(BaseModel):
    code: str
    name: str
    coverage_pct: float
    first_visited_at: datetime
    last_visited_at: datetime

class CountriesStatsResponse(BaseModel):
    total_countries_visited: int
    countries: list[CountryStatResponse]

class RegionStatResponse(BaseModel):
    code: str
    name: str
    country_code: str
    country_name: str
    coverage_pct: float
    first_visited_at: datetime
    last_visited_at: datetime

class RegionsStatsResponse(BaseModel):
    total_regions_visited: int
    regions: list[RegionStatResponse]

class StatsQueryParams(BaseModel):
    sort_by: Literal["coverage_pct", "first_visited_at", "last_visited_at", "name"] = "last_visited_at"
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

## Performance Expectations

| User Activity | Cells Visited | Expected Latency |
|---------------|---------------|------------------|
| New user | 100 | < 5ms |
| Casual (months) | 1,000 | < 10ms |
| Active (1 year) | 10,000 | 10-30ms |
| Power user | 50,000 | 30-80ms |

## Error Responses

- `401 Unauthorized`: Missing or invalid auth token
- `422 Unprocessable Entity`: Invalid query parameters
