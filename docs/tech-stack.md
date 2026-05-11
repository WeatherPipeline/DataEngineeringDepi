# Technology Stack


## Overview

The project uses a local-only architecture. Orchestration runs in Docker
containers on the development workstation, and data lands in a native SQL
Server instance on the same machine.


## Orchestration

### Apache Airflow 3.2.0

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Role            | DAG scheduling, task execution, monitoring    |
| Executor        | CeleryExecutor (distributed task queue)       |
| Image           | apache/airflow:3.2.0 (Debian Bookworm base)   |
| UI Port         | 8080                                          |
| Python version  | 3.13 (bundled in Airflow image)               |

Why Airflow: Declarative DAG definition, built-in retry/scheduling, web UI
for monitoring, and Python-native task development.

Why CeleryExecutor over LocalExecutor: CeleryExecutor distributes task
execution to separate worker containers, isolating the scheduler from task
failures. LocalExecutor runs tasks in the scheduler process, which is simpler
but less resilient.

### Celery 5.6.3

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Role            | Distributed task queue for Airflow workers    |
| Broker          | Redis 7.2                                     |
| Result Backend  | PostgreSQL 16 (via SQLAlchemy)                |
| Concurrency     | 16 prefork workers per worker container       |

Bundled with Airflow, not installed separately.


## Message Broker

### Redis 7.2 (bookworm)

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Role            | Celery message broker                         |
| Image           | redis:7.2-bookworm                            |
| Port            | 6379 (container-internal only)                |
| Persistence     | None (in-memory, data lost on restart)        |
| Authentication  | None                                          |

Why Redis: Required by CeleryExecutor. Lightweight, fast, no configuration
needed for a single-node setup. Version pinned to 7.2 due to Redis licensing
change (RSALv2/SSPLv1) starting with 7.4.

Note: If Redis restarts, in-flight task messages are lost. The scheduler will
re-queue them on the next heartbeat cycle.


## Metadata Database

### PostgreSQL 16

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Role            | Airflow metadata storage                      |
| Image           | postgres:16                                   |
| Port            | 5432 (container-internal only)                |
| Database        | airflow                                       |
| Credentials     | airflow / airflow                             |
| Persistence     | Named Docker volume (postgres-db-volume)      |

Why PostgreSQL: Default and recommended metadata backend for Airflow. Required
by CeleryExecutor for result backend storage.

Why version 16: Latest stable at time of project creation. Strong performance
and compatibility with Airflow 3.x.


## Target Database

### Microsoft SQL Server 17 (MSSQLSERVER)

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Role            | Weather data storage (pipeline target)        |
| Edition         | Developer or Express                          |
| Installation    | Native Windows service (not Dockerized)       |
| Port            | 1433 (TCP/IP, must be enabled manually)       |
| Database        | Weather_DataBase                              |
| Auth            | SQL Server Authentication (sa user)           |
| ODBC Driver     | 17 (installed in container and on host)       |

Why SQL Server: Project requirement. Chosen for familiarity and existing
infrastructure on the development machine.

Why not Dockerized: SQL Server on Docker Desktop for Windows has known
performance limitations with volume mounts on WSL2. Running natively avoids
these issues and simplifies connectivity.


## Data Processing

### Python 3.13

Runs inside Airflow containers. Not installed on the host for DAG execution
(host Python 3.14 is used only for standalone testing).

### pandas 2.3.3

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Role            | DataFrame construction, datetime conversion   |
| Used for        | Building tabular data from API responses      |

### requests 2.33.0

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Role            | HTTP client for Open-Meteo API                |
| Used for        | GET requests with timeout and error handling  |

### SQLAlchemy 2.0.48

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Role            | ORM and database connection engine            |
| Used for        | Connection pooling, raw SQL via text(), to_sql|

### pyodbc 5.3.0

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Role            | Python ODBC driver for SQL Server             |
| Used for        | Low-level database connectivity               |
| Dependency      | Requires ODBC Driver 17 at OS level           |

### scikit-learn 1.8.0

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Role            | Machine learning library                      |
| Used for        | LinearRegression model (temperature prediction)|
| Features        | humidity, wind_speed                          |
| Target          | temperature                                   |

Why LinearRegression: Simple, interpretable, no hyperparameter tuning needed.
Training on 27 observations per batch is fast. A more complex model would
overfit on such a small dataset.

### numpy 2.4.3

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Role            | Numerical computing (dependency of pandas/sklearn) |
| Direct usage    | None (transitive dependency only)             |


## Containerization

### Docker Desktop for Windows

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Backend         | WSL2                                          |
| Compose version | v2 (bundled)                                  |

### Docker Compose

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| File            | airflow-project/docker-compose.yaml           |
| Services        | 9 (7 running + cli profile + flower profile)  |
| Network         | airflow-project_default (bridge)              |
| Volumes         | 1 named (postgres-db-volume) + 4 bind mounts  |

### Custom Dockerfile

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| Base image      | apache/airflow:3.2.0                          |
| OS packages     | gnupg2, curl, ca-certificates, msodbcsql17, unixodbc-dev |
| Python packages | pandas, requests, sqlalchemy, pyodbc, scikit-learn       |
| Image size      | ~3.12 GB                                      |

Why custom image: The stock Airflow image does not include SQL Server ODBC
drivers or the Python packages needed by the DAG. Installing at runtime via
`_PIP_ADDITIONAL_REQUIREMENTS` is slow and non-deterministic. A custom image
ensures reproducible builds.


## External Services

### Open-Meteo Forecast API

| Attribute       | Detail                                        |
|-----------------|-----------------------------------------------|
| URL             | https://api.open-meteo.com/v1/forecast        |
| Auth            | None (free, no API key)                       |
| Rate limit      | ~10,000 requests/day (soft guideline)         |
| Data freshness  | 15-minute intervals                           |
| Used for        | Current temperature, humidity, wind speed     |

See `docs/data-source.md` for full API documentation.


## Development Tools

| Tool                | Version   | Purpose                              |
|---------------------|-----------|--------------------------------------|
| Python (host)       | 3.14      | Standalone script (test_7-5-2026.py) |
| sqlcmd              | 18        | SQL Server CLI queries               |
| SSMS                | 20+       | SQL Server GUI management            |
| Docker CLI          | 24+       | Container management                 |
| Docker Compose      | v2        | Multi-container orchestration        |
| text editor / IDE   | any       | DAG and config editing               |

No CI/CD pipeline is configured. All deployment is manual via docker-compose.
