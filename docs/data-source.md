# Data Source: Open-Meteo API


## Overview

The pipeline uses the Open-Meteo Forecast API to retrieve current weather
conditions for each Egyptian governorate. Open-Meteo is a free, open-source
weather API that does not require registration or API keys.

Base URL: `https://api.open-meteo.com/v1/forecast`


## Rate Limits

Open-Meteo does not enforce strict rate limits for non-commercial use. The
documentation mentions a soft guideline of approximately 10,000 requests per
day. This pipeline makes 27 requests per hourly run, totaling approximately
648 requests per day, well within the acceptable range.

No rate-limit headers (`X-RateLimit-Remaining`, `Retry-After`) are returned
in responses.


## Request Format

Method: `GET`

Parameters used by this pipeline:

| Parameter       | Type   | Required | Description                                      |
|-----------------|--------|----------|--------------------------------------------------|
| latitude        | float  | yes      | Geographic latitude of the city                  |
| longitude       | float  | yes      | Geographic longitude of the city                 |
| current         | string | yes      | Comma-separated list of current weather variables |
| timezone        | string | no       | IANA timezone identifier for time formatting     |

The `current` parameter in this pipeline requests:

- `temperature_2m`: air temperature at 2 meters above ground in Celsius
- `relative_humidity_2m`: relative humidity at 2 meters in percent (0-100)
- `wind_speed_10m`: wind speed at 10 meters above ground in km/h

The `timezone` parameter is set to `Africa/Cairo` (UTC+2 or UTC+3 with DST).


## Response Format

The API returns JSON. The structure relevant to this pipeline:

```json
{
    "latitude": 30.0444,
    "longitude": 31.2357,
    "timezone": "Africa/Cairo",
    "timezone_abbreviation": "EET",
    "utc_offset_seconds": 7200,
    "current": {
        "time": "2026-05-10T14:00",
        "interval": 900,
        "temperature_2m": 32.5,
        "relative_humidity_2m": 45,
        "wind_speed_10m": 18.3
    }
}
```

Fields extracted by the pipeline:

| JSON Path                       | Mapped To       | Type    |
|---------------------------------|-----------------|---------|
| current.time                    | timestamp       | string  |
| current.temperature_2m          | temperature     | float   |
| current.relative_humidity_2m    | humidity        | float   |
| current.wind_speed_10m          | wind_speed      | float   |

The `time` field is returned in the requested timezone (Africa/Cairo) as an
ISO 8601 string. The `interval` field indicates the measurement window in
seconds (900 = 15 minutes).


## Error Handling in the Pipeline

Each API request is wrapped in a try/except block with a 10-second timeout:

```python
response = requests.get(url, params=params, timeout=10)
response.raise_for_status()
```

Failure scenarios:

| Scenario                | Behavior                                         |
|-------------------------|--------------------------------------------------|
| Connection timeout      | Logged as [ERROR], city skipped, loop continues  |
| HTTP 4xx/5xx            | raise_for_status() triggers except, city skipped |
| JSON parse error        | Caught by generic except, city skipped           |
| Missing JSON key        | Caught by generic except, city skipped           |

If all 27 cities fail, the DataFrame will be empty and the task raises
`ValueError("No weather data extracted")`, causing the task to fail and
trigger a retry after 5 minutes.


## Data Freshness

The `current` weather values are updated by Open-Meteo every 15 minutes
(the `interval` field in the response). Running the pipeline hourly means
each run captures the most recently available observation. Consecutive runs
within the same 15-minute window may return identical `time` values, in
which case the deduplication logic will skip the duplicate insert.


## Governorate Coordinates

The 27 coordinates are hardcoded in the DAG file. They represent the
administrative capitals of each Egyptian governorate:

| # | City             | Latitude  | Longitude |
|---|------------------|-----------|-----------|
| 1 | Cairo            | 30.0444   | 31.2357   |
| 2 | Giza             | 30.0131   | 31.2089   |
| 3 | Alexandria       | 31.2001   | 29.9187   |
| 4 | Dakahlia         | 31.0409   | 31.3785   |
| 5 | Red Sea          | 24.6826   | 34.1532   |
| 6 | Beheira          | 30.8481   | 30.3436   |
| 7 | Fayoum           | 29.3084   | 30.8428   |
| 8 | Gharbia          | 30.8754   | 31.0335   |
| 9 | Ismailia         | 30.5965   | 32.2715   |
| 10| Menofia          | 30.5972   | 30.9876   |
| 11| Minya            | 28.1099   | 30.7503   |
| 12| Qalyubia         | 30.3292   | 31.2165   |
| 13| New Valley       | 25.4514   | 30.5466   |
| 14| Suez             | 29.9668   | 32.5498   |
| 15| Aswan            | 24.0889   | 32.8998   |
| 16| Assiut           | 27.1783   | 31.1859   |
| 17| Beni Suef        | 29.0661   | 31.0994   |
| 18| Port Said        | 31.2653   | 32.3019   |
| 19| Damietta         | 31.4165   | 31.8133   |
| 20| Sharkia          | 30.7326   | 31.7195   |
| 21| South Sinai      | 28.7670   | 33.6405   |
| 22| Kafr El Sheikh   | 31.1107   | 30.9388   |
| 23| Matrouh          | 31.3543   | 27.2373   |
| 24| Luxor            | 25.6872   | 32.6396   |
| 25| Qena             | 26.1551   | 32.7160   |
| 26| North Sinai      | 31.1313   | 33.7984   |
| 27| Sohag            | 26.5591   | 31.6957   |
