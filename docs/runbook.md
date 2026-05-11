# Operational Runbook


## RBO-01: Force a Manual DAG Run

When you need to trigger the pipeline outside the hourly schedule.

```bash
# Option A: Via Airflow UI
# 1. Open http://localhost:8080
# 2. Find weather_etl_pipeline
# 3. Click the play button (Trigger DAG)

# Option B: Via CLI
docker exec airflow-project-airflow-apiserver-1 \
    airflow dags trigger weather_etl_pipeline
```

Verify the run:

```bash
docker exec airflow-project-airflow-apiserver-1 \
    airflow dags list-runs -d weather_etl_pipeline
```


## RBO-02: Restart the Entire Pipeline

When containers are unhealthy or behaving unexpectedly.

```bash
cd airflow-project
docker-compose restart
```

If restart does not resolve the issue:

```bash
docker-compose down
docker-compose up -d
```

Verify all 7 containers are healthy:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Wait 2-3 minutes for all health checks to pass.


## RBO-03: Restart a Single Container

When one service is failing but others are fine.

```bash
# Example: restart only the worker
docker-compose restart airflow-worker

# Example: restart only the scheduler
docker-compose restart airflow-scheduler
```

The DAG run history and task state are preserved in PostgreSQL. In-flight
tasks will be re-queued by the scheduler after restart.


## RBO-04: Check Recent DAG Run Results

```bash
# View the latest task logs
$files = Get-ChildItem -LiteralPath "airflow-project\logs\dag_id=weather_etl_pipeline" `
    -Recurse -Filter "*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 3
foreach ($f in $files) { Get-Content $f.FullName -Tail 15 }

# Check row count in SQL Server
sqlcmd -S localhost -U sa -P "Test1234!" -C -Q `
    "USE Weather_DataBase; SELECT COUNT(*) FROM WeatherForecast"
```


## RBO-05: Add a New Governorate

1. Open `airflow-project/dags/weather_etl_pipeline.py`
2. Find the `governorates` list (line 40)
3. Add a new entry:

```python
{"city": "New City", "country": "Egypt", "lat": 00.0000, "lon": 00.0000}
```

4. Save the file
5. The dag-processor will detect the change within 30 seconds
6. No container restart needed
7. The new city will be included in the next hourly run (or trigger manually
   with RBO-01)


## RBO-06: Change SQL Server Password

1. Change the `sa` password in SQL Server:

```sql
ALTER LOGIN sa WITH PASSWORD = 'NewPassword123!';
```

2. Update the DAG file `airflow-project/dags/weather_etl_pipeline.py` line 84:

```python
PASSWORD = "NewPassword123!"
```

3. Update the standalone script `test_7-5-2026.py` line 48:

```python
PASSWORD = "NewPassword123!"
```

4. The dag-processor picks up the change within 30 seconds
5. Verify connectivity:

```bash
docker exec airflow-project-airflow-worker-1 python -c \
    "import pyodbc; \
     conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server}; \
     SERVER=host.docker.internal;DATABASE=Weather_DataBase; \
     UID=sa;PWD=NewPassword123!;TrustServerCertificate=yes'); \
     print('OK'); conn.close()"
```


## RBO-07: Rebuild the Docker Image

When the Dockerfile is modified (new OS package or Python dependency).

```bash
cd airflow-project
docker-compose build
docker-compose up -d
```

This recreates all containers with the new image. The PostgreSQL data volume
is preserved.

If you want a completely clean build (no cache):

```bash
docker-compose build --no-cache
docker-compose up -d
```


## RBO-08: Reset Airflow to Clean State

When you want to clear all run history and start fresh.

Warning: This deletes all DAG run history and task logs. SQL Server data is
not affected.

```bash
# 1. Stop all Airflow services
cd airflow-project
docker-compose stop airflow-scheduler airflow-worker airflow-apiserver `
                  airflow-dag-processor airflow-triggerer

# 2. Drop and recreate the metadata database
docker exec airflow-project-postgres-1 psql -U airflow -d postgres `
    -c "DROP DATABASE airflow;"
docker exec airflow-project-postgres-1 psql -U airflow -d postgres `
    -c "CREATE DATABASE airflow;"

# 3. Clean logs
Remove-Item -LiteralPath "logs\*" -Recurse -Force

# 4. Start fresh
docker-compose up -d
```

The init container will run migrations and recreate the admin user.


## RBO-09: Clean Old Data from SQL Server

When the WeatherForecast table grows large and you want to remove old records.

```sql
-- Delete records older than 30 days
DELETE FROM WeatherForecast
WHERE timestamp < DATEADD(DAY, -30, GETUTCDATE());

-- Or delete records older than 90 days
DELETE FROM WeatherForecast
WHERE timestamp < DATEADD(DAY, -90, GETUTCDATE());

-- Check current row count
SELECT COUNT(*) FROM WeatherForecast;

-- Check size on disk
EXEC sp_spaceused 'WeatherForecast';
```


## RBO-10: View Container Resource Usage

```bash
# Live resource monitor (CPU, memory, network, disk I/O)
docker stats

# Disk usage summary
docker system df

# Per-container resource usage (snapshot)
docker ps --format "table {{.Names}}\t{{.Size}}" -s
```


## RBO-11: Diagnose a Failed DAG Run

Step-by-step diagnostic flow:

```bash
# Step 1: Check which task failed
$files = Get-ChildItem -LiteralPath "airflow-project\logs\dag_id=weather_etl_pipeline" `
    -Recurse -Filter "*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 3
foreach ($f in $files) { Write-Output "=== $($f.Name) ==="; Get-Content $f.FullName -Tail 10 }

# Step 2: If error contains "Login timeout expired"
# -> SQL Server TCP/IP is not listening
# -> See RBO-12

# Step 3: If error contains "ImportError" or "ModuleNotFoundError"
# -> Missing Python dependency in Docker image
# -> See RBO-07 to rebuild with the missing package

# Step 4: If error contains "Connection refused" or "ConnectTimeout"
# -> API network issue from Docker to Open-Meteo
# -> Usually transient, retry with RBO-01

# Step 5: If error contains "UNIQUE constraint"
# -> Duplicate insert attempt (expected, not an error)
# -> The row already exists, no action needed
```


## RBO-12: Fix SQL Server Connectivity Issues

When tasks fail with "Login timeout expired" or "Connection refused".

```bash
# Step 1: Check if SQL Server service is running
Get-Service -Name 'MSSQLSERVER'

# Step 2: Check if port 1433 is listening
netstat -an | findstr ":1433"

# Step 3: If not listening, enable TCP/IP
#    Open SQL Server Configuration Manager
#    SQL Server Network Configuration > Protocols for MSSQLSERVER > Enable TCP/IP
#    Properties > IP Addresses > IPAll > TcpPort = 1433
#    Restart SQL Server service:
Restart-Service -Name 'MSSQLSERVER'

# Step 4: Verify from host
sqlcmd -S localhost,1433 -U sa -P "Test1234!" -C -Q "SELECT 1"

# Step 5: Verify from Docker
docker exec airflow-project-airflow-worker-1 python -c \
    "import pyodbc; \
     conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server}; \
     SERVER=host.docker.internal;DATABASE=Weather_DataBase; \
     UID=sa;PWD=Test1234!;TrustServerCertificate=yes'); \
     print('OK'); conn.close()"
```


## RBO-13: Create a Backup

### Airflow Metadata + Logs

```bash
# Dump PostgreSQL
docker exec airflow-project-postgres-1 pg_dump -U airflow airflow `
    > airflow_metadata_backup.sql

# Package everything
Compress-Archive -Path "logs", "airflow_metadata_backup.sql" `
    -DestinationPath "airflow_backup.zip" -Force
```

### SQL Server Data

```sql
BACKUP DATABASE Weather_DataBase
TO DISK = 'C:\Backups\Weather_DataBase.bak'
WITH FORMAT, INIT, NAME = 'Weather_DataBase-Full Backup';
```

Or via SSMS: Right-click database > Tasks > Back Up.


## RBO-14: Stop Everything

```bash
# Stop containers but keep data
cd airflow-project
docker-compose down

# Resume later
docker-compose up -d
```

To also remove the PostgreSQL data volume (full cleanup):

```bash
docker-compose down -v
```

Warning: `down -v` deletes all Airflow run history permanently.
