# ETL Pipeline

This document describes the extract-transform-load logic in detail.


## DAG Configuration

File: `airflow-project/dags/weather_etl_pipeline.py`

```python
dag_id      = "weather_etl_pipeline"
schedule    = "@hourly"          # triggers at the top of every hour (UTC)
catchup     = False              # no backfill for missed intervals
start_date  = 2026-05-07         # earliest possible run date
retries     = 1
retry_delay = 5 minutes
owner       = Mahmoud
```

The DAG defines two tasks with a sequential dependency:

```
create_weather_table  >>  load_weather_data
```


## Task 1: create_weather_table

Callable: `create_table()` (line 105)

This task is idempotent. It checks for the table's existence before creating
it using the SQL Server `sysobjects` catalog view:

```sql
IF NOT EXISTS (
    SELECT * FROM sysobjects WHERE name='WeatherForecast' AND xtype='U'
)
CREATE TABLE WeatherForecast ( ... )
```

If the table already exists, the statement does nothing. This allows the task
to succeed safely on every run.

The connection is opened with `engine.begin()` which auto-commits the DDL
statement and auto-rolls back on error.


## Task 2: load_weather_data

Callable: `load_data()` (line 253)

This task contains the full ETL logic. It calls `extract_transform()` to build
a DataFrame, then iterates over each row to conditionally insert.


### Extract Phase

The extract loop iterates over the `governorates` list (27 entries). For each
governorate, it sends an HTTP GET request to:

```
https://api.open-meteo.com/v1/forecast
```

Query parameters per request:

| Parameter   | Value                                            |
|-------------|--------------------------------------------------|
| latitude    | gov["lat"] (float)                               |
| longitude   | gov["lon"] (float)                               |
| current     | temperature_2m,relative_humidity_2m,wind_speed_10m |
| timezone    | Africa/Cairo                                     |

The `timeout` is set to 10 seconds. If a request fails (network error,
timeout, non-200 status), the exception is caught and the city is skipped.
The loop continues to the next governorate.

Each successful response returns JSON with a `current` object. The pipeline
extracts four fields:

| JSON Key                  | DataFrame Column |
|---------------------------|------------------|
| current.time              | timestamp        |
| current.temperature_2m    | temperature      |
| current.relative_humidity_2m | humidity       |
| current.wind_speed_10m    | wind_speed       |

Also appended from the governorates list: `city` and `country`.

After the loop, the collected list is converted to a pandas DataFrame. If the
DataFrame is empty (all 27 requests failed), a `ValueError` is raised and the
task fails.


### Transform Phase

Three transformations are applied in sequence:

**1. Datetime Conversion**

```python
df["timestamp"] = pd.to_datetime(df["timestamp"])
```

Converts the ISO 8601 string from the API (e.g., "2026-05-10T14:00") to a
pandas Timestamp object. SQLAlchemy will handle conversion to SQL Server
DATETIME on insert.

**2. Alert Classification**

```python
df["alert"] = df["temperature"].apply(
    lambda x: "High Temperature" if x > 36
         else ("Low Temperature" if x < 15 else "Normal")
)
```

Applied per row. The thresholds are in degrees Celsius:

| Temperature Range | Alert             |
|-------------------|-------------------|
| > 36 C            | High Temperature  |
| < 15 C            | Low Temperature   |
| 15 C - 36 C       | Normal            |

**3. ML Prediction**

```python
X = df[["humidity", "wind_speed"]]
y = df["temperature"]
model = LinearRegression()
model.fit(X, y)
df["predicted_temperature"] = model.predict(X).round(1)
```

A new LinearRegression model is trained from scratch on each batch. The model
uses humidity and wind speed as features (X) and actual temperature as the
target (y). The prediction is rounded to one decimal place.

Note: Because the model is trained and discarded per run, there is no model
persistence. Each run produces independent predictions based solely on the
current batch of 27 observations.


### Load Phase

The load phase iterates over the DataFrame row by row:

```python
for _, row in df.iterrows():
```

For each row:

1. Call `record_exists(city, timestamp)` which executes:

   ```sql
   SELECT COUNT(*) FROM WeatherForecast
   WHERE city = :city AND timestamp = :timestamp
   ```

2. If count > 0, print `[SKIPPED]` and move to the next row.

3. If count = 0, wrap the row in a single-row DataFrame and call:

   ```python
   single_row.to_sql("WeatherForecast", con=engine, if_exists="append", index=False)
   ```

   This generates an INSERT statement for one row.

4. If the insert fails (e.g., constraint violation from a concurrent run),
   the exception is caught and logged, and the loop continues.

After all rows are processed, a summary is printed:

```
=========== SUMMARY ===========
Inserted : 13
Skipped  : 14
================================
```


## Deduplication Mechanism

Deduplication operates at two levels:

**Application level**: The `record_exists()` function checks for an existing
row before attempting an insert. This avoids unnecessary INSERT attempts.

**Database level**: The `UNIQUE(city, timestamp)` constraint on the
`WeatherForecast` table acts as a hard guard. Even if two concurrent DAG runs
pass the application-level check simultaneously, only one will succeed. The
other will receive a constraint violation error, which is caught and logged.


## Standalone Script

File: `test_7-5-2026.py`

Contains identical ETL logic for running outside Docker. The only difference
is the SQL Server connection uses `localhost` instead of `host.docker.internal`.

Run directly:

```bash
python test_7-5-2026.py
```

This creates the table, fetches weather data, and loads it in one execution.
Useful for development and debugging without starting the full Airflow stack.
