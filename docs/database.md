# Database Documentation

Target: Microsoft SQL Server 17 (MSSQLSERVER instance)
Database: `Weather_DataBase`


## WeatherForecast Table

This is the single fact table in the pipeline. It is created by the DAG on
first run and grows over time as new weather observations are appended.

### Schema

```
Column                  Type            Nullable  Description
---------------------   -------------   --------  -------------------------------
id                      INT             NO        Identity primary key (auto-increment)
city                    NVARCHAR(100)   YES       English name of the governorate
country                 NVARCHAR(100)   YES       Always "Egypt"
timestamp               DATETIME        YES       Observation time from API (UTC, Africa/Cairo)
temperature             FLOAT           YES       Current temperature in Celsius
humidity                FLOAT           YES       Relative humidity percentage (0-100)
wind_speed              FLOAT           YES       Wind speed at 10m altitude in km/h
predicted_temperature   FLOAT           YES       ML-predicted temperature (LinearRegression)
alert                   NVARCHAR(100)   YES       Classification: High Temperature,
                                                    Low Temperature, or Normal
```

### Constraints

```sql
PRIMARY KEY        (id)                        -- clustered, identity(1,1)
UNIQUE             (city, timestamp)           -- prevents duplicate observations
```

The unique constraint on `(city, timestamp)` ensures that each governorate can
have at most one record per distinct timestamp. This is the deduplication
anchor for the entire pipeline.


### Indexes

The unique constraint `uq_city_timestamp` automatically creates a non-clustered
unique index on `(city, timestamp)`. No additional indexes are defined.

For query patterns that filter by city and date range, this index provides
efficient lookups.


### Growth Estimate

At full capacity (27 cities, hourly inserts):

| Period     | Rows (approx) | Disk (approx) |
|------------|---------------|---------------|
| 1 day      | 648           | ~200 KB       |
| 1 week     | 4,536         | ~1.5 MB       |
| 1 month    | ~19,440       | ~6 MB         |
| 1 year     | ~236,520      | ~75 MB        |

These are conservative estimates. Actual size depends on how many API calls
succeed per run and whether manual triggers add additional rows.


## weather_day View

File: `SQLQuery7-5-2026.sql`

A read-only view over `WeatherForecast` that renames columns to human-friendly
aliases and adds a computed `Day` column.

```sql
CREATE VIEW weather_day AS
SELECT
    id                      AS ID,
    city                    AS City,
    country                 AS Country,
    [timestamp]             AS [Timestamp],
    temperature             AS Temperature,
    humidity                AS Humidity,
    wind_speed              AS [Wind Speed],
    predicted_temperature   AS [Predicted Temperature],
    alert                   AS Alert,
    DATENAME(WEEKDAY, [timestamp]) AS Day
FROM WeatherForecast;
```

The `Day` column returns the full weekday name in English (e.g., "Monday",
"Tuesday") based on the timestamp value. This is computed at query time and
not stored on disk.

Usage:

```sql
SELECT * FROM [dbo].[weather_day];
```

Note: As of the current deployment, this view is defined in the SQL file but
may need to be created manually in SQL Server Management Studio or via sqlcmd
if it does not already exist in the database.


## Connection Details

The DAG connects using the following configuration:

```
Driver:    ODBC Driver 17 for SQL Server
Server:    host.docker.internal     (from Docker containers)
           localhost                (from standalone script)
Database:  Weather_DataBase
User:      sa
Password:  stored in DAG source (plaintext)
Options:   TrustServerCertificate=yes
```

The SQLAlchemy connection URL format:

```
mssql+pyodbc:///?odbc_connect=<URL-encoded connection string>
```


## Common Queries

Recent observations for a specific city:

```sql
SELECT TOP 10 * FROM WeatherForecast
WHERE city = 'Cairo'
ORDER BY timestamp DESC;
```

Cities with high temperature alerts in the last 24 hours:

```sql
SELECT city, temperature, timestamp
FROM WeatherForecast
WHERE alert = 'High Temperature'
  AND timestamp >= DATEADD(HOUR, -24, GETUTCDATE())
ORDER BY temperature DESC;
```

Average temperature by city today:

```sql
SELECT city, AVG(temperature) AS avg_temp
FROM WeatherForecast
WHERE CAST(timestamp AS DATE) = CAST(GETDATE() AS DATE)
GROUP BY city
ORDER BY avg_temp DESC;
```

Prediction accuracy (mean absolute error) for the latest run:

```sql
SELECT TOP 1
    AVG(ABS(temperature - predicted_temperature)) AS mae,
    MAX(timestamp) AS run_time
FROM WeatherForecast
WHERE predicted_temperature IS NOT NULL
GROUP BY CAST(timestamp AS DATE)
ORDER BY run_time DESC;
```
