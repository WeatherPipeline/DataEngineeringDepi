# System Architecture

## Overview

The system is a batch ETL pipeline that runs on an hourly schedule. It is composed
of three layers: orchestration (Airflow), processing (Python), and storage
(SQL Server). All infrastructure runs locally on a single Windows machine.


## Component Map

```
                        +---------------------------+
                        |     Windows Host Machine   |
                        |                           |
  +----------+          |  +---------------------+  |
  | Open-Mete|          |  |  Docker Desktop      |  |
  | API      |          |  |  (WSL2 backend)      |  |
  | (cloud)  |          |  |                      |  |
  +----+-----+          |  |  +----------------+  |  |
       |                |  |  | airflow-project|  |  |
       | HTTPS GET      |  |  | (docker-compose|  |  |
       | (27 requests)  |  |  |  network)      |  |  |
       |                |  |  |                |  |  |
       +----------------+-->+  | postgres:16   |  |  |
                        |  |  | redis:7.2     |  |  |
                        |  |  | apiserver     |  |  |
                        |  |  | scheduler     |  |  |
                        |  |  | dag-processor |  |  |
                        |  |  | worker        |  |  |
                        |  |  | triggerer     |  |  |
                        |  |  +-------+--------+  |  |
                        |  |          |           |  |
                        |  +----------|-----------+  |
                        |             |              |
                        |   host.docker.internal     |
                        |   (port 1433)              |
                        |             |              |
                        |  +----------v-----------+  |
                        |  | SQL Server (MSSQL17)  |  |
                        |  |                       |  |
                        |  | Weather_DataBase      |  |
                        |  |   -> WeatherForecast  |  |
                        |  |   -> weather_day (vw) |  |
                        |  +-----------------------+  |
                        +---------------------------+
```


## Orchestration Layer (Airflow)

Airflow 3.2.0 runs inside Docker Compose using the CeleryExecutor pattern.
This means task execution is distributed across multiple containers.

### Service Responsibilities

- **apiserver**: Exposes the web UI on port 8080 and the REST API. All DAG
  management, manual triggers, and monitoring happen here.

- **scheduler**: Evaluates DAG schedules and decides when to create DagRuns.
  It places task instances into the executor queue every 5 seconds.

- **dag-processor**: Parses Python files in the `dags/` directory, serializes
  DAG definitions, and writes them to the metadata database. Re-parses on file
  change.

- **worker**: A Celery worker that picks up task instances from the Redis queue
  and executes them. This is where the actual Python code (API calls, SQL
  inserts) runs.

- **triggerer**: Manages async triggers (deferrable operators). Not used by
  the current pipeline but required by Airflow 3.x.

- **init**: Runs once at startup. Initializes the metadata database, runs
  migrations, creates the admin user, and sets file permissions. Exits after
  completion.

### Metadata Storage

PostgreSQL 16 stores all Airflow state: DAG definitions, run history, task
instance states, connection configs, variables, and audit logs. The data
persists in the Docker volume `postgres-db-volume`.

### Message Broker

Redis 7.2 acts as the Celery message broker. The scheduler pushes task
execution requests to a Redis queue. Workers pull from this queue. Results
are written back to PostgreSQL.


## Processing Layer (Python)

All data processing logic lives in `airflow-project/dags/weather_etl_pipeline.py`.
It runs inside the worker container.

Libraries installed in the custom Docker image are documented in detail in
[tech-stack.md](tech-stack.md#data-processing).

| Package       | Installed Version | Purpose                              |
|---------------|-------------------|--------------------------------------|
| pandas        | 2.3.3             | DataFrame construction and datetime  |
| requests      | 2.33.0            | HTTP calls to Open-Meteo API         |
| SQLAlchemy    | 2.0.48            | Database connection and query engine |
| pyodbc        | 5.3.0             | ODBC driver for SQL Server           |
| scikit-learn  | 1.8.0             | LinearRegression model               |

The worker container also has Microsoft ODBC Driver 17 installed at the OS
level (via apt in the Dockerfile) to enable pyodbc connectivity to SQL Server.


## Storage Layer (SQL Server)

Microsoft SQL Server (MSSQL17) runs natively on the Windows host, outside Docker.
The pipeline connects from inside the Docker network using the hostname
`host.docker.internal` on port 1433.

The target database is `Weather_DataBase`. The pipeline creates and manages
a single table (`WeatherForecast`) and an optional view (`weather_day`).

Connection string pattern:

```
mssql+pyodbc:///?odbc_connect=
  DRIVER={ODBC Driver 17 for SQL Server};
  SERVER=host.docker.internal;
  DATABASE=Weather_DataBase;
  UID=sa;
  PWD=***;
  TrustServerCertificate=yes;
```


## Network Topology

Docker Compose creates a default bridge network named `airflow-project_default`.
All Airflow containers share this network and resolve each other by service
name (e.g., `postgres`, `redis`, `airflow-apiserver`).

To reach the host machine from inside a container, Docker provides the special
DNS name `host.docker.internal`. This resolves to the host's internal IP
(192.168.65.254 on Docker Desktop for Windows).

SQL Server must have TCP/IP enabled and listening on 0.0.0.0:1433 for
containers to connect. Shared memory or named pipes alone are insufficient
because containers are network-isolated from the host.


## Data Flow Sequence

The following sequence occurs on every hourly DAG run:

```
1. scheduler        creates DagRun for the current hour
2. dag-processor    has already parsed and registered the DAG
3. scheduler        queues create_weather_table task
4. worker           picks up task, connects to SQL Server via host.docker.internal
5. worker           executes CREATE TABLE IF NOT EXISTS
6. scheduler        queues load_weather_data task (depends on step 5 success)
7. worker           picks up task
8. worker           loops through 27 governorates:
                      - sends HTTPS GET to api.open-meteo.com
                      - parses JSON response
                      - appends to in-memory list
9. worker           constructs pandas DataFrame from collected data
10. worker          transforms:
                      - converts timestamp strings to datetime
                      - classifies alert (High/Normal/Low)
                      - trains LinearRegression on batch
                      - predicts temperature column
11. worker          loads row by row:
                      - checks SELECT COUNT WHERE city=X AND timestamp=Y
                      - if count=0: INSERT via pandas to_sql
                      - if count>0: skip
12. worker          prints summary (inserted/skipped counts)
```


## Volume Mounts

The docker-compose.yaml mounts the following host directories into every
Airflow container:

| Host Path                        | Container Path            | Purpose                  |
|----------------------------------|---------------------------|--------------------------|
| airflow-project/dags             | /opt/airflow/dags         | DAG source files         |
| airflow-project/logs             | /opt/airflow/logs         | Task execution logs      |
| airflow-project/config           | /opt/airflow/config       | airflow.cfg overrides    |
| airflow-project/plugins          | /opt/airflow/plugins      | Custom plugins           |

Changes to files in `dags/` are picked up by the dag-processor within one
parse cycle (approximately 30 seconds). No container restart is needed
to pick up DAG code changes.


## Failure and Retry Behavior

- Each task has 1 retry with a 5-minute delay between attempts.
- Individual city API failures (timeout, network error) are caught inside
  the extract loop and do not fail the task. The city is skipped and the
  loop continues.
- If zero cities return data, the task raises `ValueError` and the task fails.
- The `UNIQUE(city, timestamp)` constraint prevents duplicate inserts at the
  database level even if a DAG run overlaps with a retry or manual trigger.
