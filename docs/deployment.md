# Deployment and Operations


## Deployment Architecture

```
 Windows Host (192.168.1.x)
 |
 +-- SQL Server (MSSQL17)              Native Windows service
 |   |-- Listening on 0.0.0.0:1433
 |   |-- Database: Weather_DataBase
 |   |-- Auth: SQL Server (sa)
 |
 +-- Docker Desktop (WSL2 backend)
     |
     +-- Docker Network: airflow-project_default (bridge)
         |
         +-- postgres:16                   Container
         |   |-- Port: 5432 (internal only)
         |   |-- Volume: postgres-db-volume
         |   |-- Credentials: airflow / airflow
         |
         +-- redis:7.2-bookworm            Container
         |   |-- Port: 6379 (internal only)
         |   |-- No authentication
         |
         +-- airflow-apiserver             Container
         |   |-- Port: 8080 -> 8080 (exposed to host)
         |   |-- Login: airflow / airflow
         |
         +-- airflow-scheduler             Container
         |   |-- Port: 8974 (health, internal)
         |
         +-- airflow-dag-processor         Container
         |
         +-- airflow-worker                Container
         |   |-- Connects to host SQL Server via
         |       host.docker.internal:1433
         |
         +-- airflow-triggerer             Container
         |
         +-- airflow-init                  Container (exits after setup)
```

### Container-to-Host Communication

Containers reach SQL Server through Docker's DNS resolver. The hostname
`host.docker.internal` resolves to `192.168.65.254` (Docker Desktop gateway).
Traffic is routed from the WSL2 virtual machine to the Windows host network
stack and arrives at SQL Server on port 1433.

Firewall note: Windows Defender Firewall must allow inbound connections on
port 1433 from the WSL2 subnet. Docker Desktop typically configures this
automatically.

### Volume Mapping

```
 Host Path                              Container Path             Type
 -------------------------------------  -------------------------  ------
 airflow-project/dags                   /opt/airflow/dags          bind
 airflow-project/logs                   /opt/airflow/logs          bind
 airflow-project/config                 /opt/airflow/config        bind
 airflow-project/plugins                /opt/airflow/plugins       bind
 postgres-db-volume                     /var/lib/postgresql/data   named
```

Bind mounts allow live editing of DAG files on the host. The named volume
persists PostgreSQL data across container recreations and docker-compose down
(unless `docker-compose down -v` is used).


## Environment Details

### Host Requirements

| Resource       | Minimum          | Recommended       |
|----------------|------------------|-------------------|
| OS             | Windows 10 64-bit| Windows 10/11 64-bit |
| CPU            | 2 cores          | 4 cores           |
| RAM            | 8 GB (4 GB for Docker) | 16 GB       |
| Disk           | 20 GB free       | 50 GB free        |
| Docker version | 24.0+            | Latest stable     |
| SQL Server     | 2019 Express     | 2022 Developer    |

### Software Versions (Current Deployment)

| Component            | Version          | Source                       |
|----------------------|------------------|------------------------------|
| Windows              | 10/11            | Host OS                      |
| Docker Desktop       | Latest           | docker.com                   |
| WSL2 Kernel          | Latest           | Docker Desktop bundled       |
| Docker Compose       | v2 (bundled)     | Docker Desktop               |
| SQL Server           | MSSQL17          | Native Windows install       |
| ODBC Driver          | 17               | Microsoft (host + container) |
| Airflow              | 3.2.0            | apache/airflow:3.2.0 image   |
| PostgreSQL           | 16               | postgres:16 image            |
| Redis                | 7.2-bookworm     | redis:7.2-bookworm image     |
| Python (in container)| 3.13            | Airflow base image           |

### Environment Variables

File: `airflow-project/.env`

| Variable                      | Value                                | Purpose                      |
|-------------------------------|--------------------------------------|------------------------------|
| AIRFLOW_IMAGE_NAME            | apache/airflow:3.2.0                 | Base image for build         |
| AIRFLOW_UID                   | 50000                                | Container user ID            |
| AIRFLOW__CORE__FERNET_KEY     | RYITNM0V5hwAyF0_U6K8G32d4oAoSat...  | Encryption key for secrets   |

File: `airflow-project/docker-compose.yaml` (environment section)

| Variable                                  | Value                                    |
|-------------------------------------------|------------------------------------------|
| AIRFLOW__CORE__EXECUTOR                   | CeleryExecutor                           |
| AIRFLOW__CORE__AUTH_MANAGER               | airflow.providers.fab.auth_manager...    |
| AIRFLOW__DATABASE__SQL_ALCHEMY_CONN       | postgresql+psycopg2://airflow:airflow... |
| AIRFLOW__CELERY__RESULT_BACKEND           | db+postgresql+psycopg2://airflow:airflow |
| AIRFLOW__CELERY__BROKER_URL               | redis://:@redis:6379/0                   |
| AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION | true                                    |
| AIRFLOW__CORE__LOAD_EXAMPLES              | false                                    |
| _AIRFLOW_WWW_USER_USERNAME                | airflow                                  |
| _AIRFLOW_WWW_USER_PASSWORD                | airflow                                  |

### Network Ports

| Port  | Service           | Bound To         | Accessible From     |
|-------|-------------------|------------------|---------------------|
| 8080  | airflow-apiserver | 0.0.0.0:8080    | Host browser        |
| 5432  | postgres          | Container only   | Other containers    |
| 6379  | redis             | Container only   | Other containers    |
| 8974  | scheduler health  | Container only   | Internal healthcheck|
| 1433  | SQL Server        | 0.0.0.0:1433    | Docker containers   |


## Fresh Installation

### Step 1: Install Docker Desktop

Download and install Docker Desktop for Windows with the WSL2 backend.
Allocate at least 4 GB RAM and 2 CPUs to Docker.

Verify:

```bash
docker --version
docker-compose --version
```

### Step 2: Prepare SQL Server

Install SQL Server 2019 or later (Express edition is sufficient).
Enable mixed-mode authentication during setup.

After installation, open SQL Server Configuration Manager:

1. Navigate to SQL Server Network Configuration > Protocols for MSSQLSERVER
2. Enable TCP/IP
3. Right-click TCP/IP > Properties > IP Addresses > IPAll > set TcpPort to 1433
4. Restart the SQL Server service

Create the target database:

```sql
CREATE DATABASE Weather_DataBase;
```

Verify TCP connectivity:

```bash
sqlcmd -S localhost,1433 -U sa -P "YourPassword" -C -Q "SELECT 1"
```

### Step 3: Deploy Airflow

```bash
cd airflow-project
docker-compose build
docker-compose up -d
```

Monitor container startup:

```bash
docker-compose logs -f
```

Wait for all 7 containers to report healthy. This typically takes 2-3 minutes.

### Step 4: Configure and Unpause

Open http://localhost:8080. Login with airflow / airflow.

Find the `weather_etl_pipeline` DAG and toggle it from paused to active.
The first run will trigger at the top of the next hour.


## Configuration Changes

### Changing SQL Server Credentials

Edit the connection parameters in `airflow-project/dags/weather_etl_pipeline.py`
at lines 78-86:

```python
SERVER   = "host.docker.internal"
DATABASE = "Weather_DataBase"
USERNAME = "sa"
PASSWORD = "YourNewPassword"
```

Then the dag-processor will pick up the change within 30 seconds. No restart
required.

### Changing the Schedule

In the same file, modify line 32:

```python
schedule="@hourly",        # options: @daily, @weekly, "0 */2 * * *", etc.
```

### Adding or Removing Governorates

Edit the `governorates` list at line 40. Each entry requires:

```python
{"city": "Name", "country": "Egypt", "lat": 00.0000, "lon": 00.0000}
```

Coordinates can be looked up at https://open-meteo.com/en/docs.


## Rebuilding After Code Changes

If the DAG Python code changes, the dag-processor detects the file change
automatically. No action needed.

If the Dockerfile changes (new system package or pip dependency):

```bash
cd airflow-project
docker-compose build
docker-compose up -d
```

This rebuilds the image and recreates all containers. The PostgreSQL metadata
and Redis state are preserved across rebuilds because they use Docker volumes.


## Resetting Airflow to Clean State

This removes all DAG run history, task logs, and UI state. It does not touch
SQL Server data.

```bash
# Stop all Airflow services (keep postgres and redis running)
docker-compose stop airflow-scheduler airflow-worker airflow-apiserver \
                  airflow-dag-processor airflow-triggerer

# Drop and recreate the metadata database
docker exec airflow-project-postgres-1 psql -U airflow -d postgres \
    -c "DROP DATABASE airflow;"
docker exec airflow-project-postgres-1 psql -U airflow -d postgres \
    -c "CREATE DATABASE airflow;"

# Clean old logs
rm -rf airflow-project/logs/*

# Start everything fresh
docker-compose up -d
```

The init container will re-run migrations and create the admin user.


## Backup and Recovery

### Backup

The `airflow_backup.zip` file contains a PostgreSQL dump and logs archive.
To create one manually:

```bash
# Dump metadata
docker exec airflow-project-postgres-1 pg_dump -U airflow airflow \
    > airflow_metadata_backup.sql

# Package
Compress-Archive -Path logs, airflow_metadata_backup.sql \
    -DestinationPath airflow_backup.zip
```

### Recovery

```bash
# Restore metadata
Get-Content airflow_metadata_backup.sql | docker exec -i \
    airflow-project-postgres-1 psql -U airflow airflow
```

Note: SQL Server data (`Weather_DataBase`) must be backed up separately using
SQL Server native backup (`.bak` files via SSMS or sqlcmd).


## Health Checks

Verify the entire stack:

```bash
# Container health
docker ps --format "table {{.Names}}\t{{.Status}}"

# Airflow internal health
docker exec airflow-project-airflow-apiserver-1 \
    curl -s http://localhost:8080/api/v2/monitor/health

# SQL Server connectivity from Docker
docker exec airflow-project-airflow-worker-1 python -c \
    "import pyodbc; \
     conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server}; \
     SERVER=host.docker.internal;DATABASE=Weather_DataBase; \
     UID=sa;PWD=Test1234!;TrustServerCertificate=yes'); \
     print('OK'); conn.close()"
```

All three should return positive results for the pipeline to function.


## Stopping the Pipeline

```bash
cd airflow-project
docker-compose down          # stop and remove containers
docker-compose down -v       # also remove volumes (deletes metadata DB)
```

Using `down` without `-v` preserves the PostgreSQL data volume, so the next
`docker-compose up -d` will resume with all history intact.


## Troubleshooting

### DAG not appearing in the UI

Check the dag-processor logs for import errors:

```bash
docker-compose logs airflow-dag-processor
```

Common causes: Python syntax error, missing import, wrong import path.

### Task fails with "Login timeout expired"

SQL Server TCP/IP is not listening. Verify:

```bash
netstat -an | findstr ":1433"
```

If no listener is found, open SQL Server Configuration Manager, enable TCP/IP,
and restart the SQL Server service.

### Some cities return API errors

This is expected behavior. The Open-Meteo API may timeout for individual
requests. The 10-second timeout is conservative. Affected cities are logged
and skipped; they will be retried on the next hourly run.

### Container keeps restarting

Check the container logs:

```bash
docker-compose logs <service-name>
```

Common causes: insufficient memory (requires 4 GB for Docker), port 8080
already in use by another process.
