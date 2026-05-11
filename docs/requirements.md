# Requirements


## Functional Requirements

| ID    | Requirement                                                          | Priority |
|-------|----------------------------------------------------------------------|----------|
| FR-01 | The system shall fetch weather data for 27 Egyptian governorates     | Must     |
| FR-02 | The system shall fetch temperature, humidity, and wind speed         | Must     |
| FR-03 | The system shall run the pipeline on an hourly schedule              | Must     |
| FR-04 | The system shall store results in SQL Server                         | Must     |
| FR-05 | The system shall prevent duplicate records per (city, timestamp)     | Must     |
| FR-06 | The system shall classify temperatures into alert categories         | Must     |
| FR-07 | The system shall predict temperature using a linear regression model | Should   |
| FR-08 | The system shall continue processing if individual city API calls fail | Must |
| FR-09 | The system shall log success, skip, and error for each city          | Must     |
| FR-10 | The system shall print a summary of inserted and skipped records     | Must     |
| FR-11 | The system shall create the target table automatically if absent     | Must     |
| FR-12 | The system shall provide a standalone test script outside Docker     | Should   |


## Non-Functional Requirements

### Performance

| ID     | Requirement                                                        | Target                    |
|--------|--------------------------------------------------------------------|---------------------------|
| NFR-01 | A full pipeline run (27 cities) shall complete within 5 minutes   | 5 min max                 |
| NFR-02 | A single API request shall timeout after 10 seconds                | 10s timeout               |
| NFR-03 | The system shall not exceed 4 GB RAM for Docker                    | 4 GB Docker allocation    |
| NFR-04 | The system shall not exceed 3.5 GB Docker image size               | ~3.1 GB actual            |

### Availability

| ID     | Requirement                                                        | Target                    |
|--------|--------------------------------------------------------------------|---------------------------|
| NFR-05 | The pipeline shall recover automatically from individual API failures | Built-in retry + skip    |
| NFR-06 | Airflow containers shall auto-restart on failure                    | restart: always in compose|
| NFR-07 | The system shall tolerate a SQL Server restart without data loss    | Unique constraint guard   |

### Reliability

| ID     | Requirement                                                        | Target                    |
|--------|--------------------------------------------------------------------|---------------------------|
| NFR-08 | No duplicate data shall be inserted under any condition             | UNIQUE constraint enforced|
| NFR-09 | Failed tasks shall retry once with a 5-minute delay                 | 1 retry, 5 min backoff    |
| NFR-10 | DAG code changes shall take effect without container restart        | dag-processor auto-parses |

### Security

| ID     | Requirement                                                        | Current State             |
|--------|--------------------------------------------------------------------|---------------------------|
| NFR-11 | Database credentials shall not be exposed in plaintext              | Plaintext in DAG (risk)   |
| NFR-12 | Container-to-SQL traffic shall be encrypted                         | TrustServerCertificate=yes|
| NFR-13 | Airflow UI shall require authentication                             | Username/password         |
| NFR-14 | The Fernet key shall not be committed to version control            | In .env (gitignored)      |

### Maintainability

| ID     | Requirement                                                        | Target                    |
|--------|--------------------------------------------------------------------|---------------------------|
| NFR-15 | Adding a new city shall require editing only the governorates list  | Single list in DAG        |
| NFR-16 | Changing the schedule shall require editing only the schedule param | Single line in DAG        |
| NFR-17 | Adding a new Python dependency shall require Dockerfile change only | pip install line          |


## Technical Requirements

| ID    | Requirement                                                                 |
|-------|-----------------------------------------------------------------------------|
| TR-01 | Docker Desktop for Windows with WSL2 backend                                |
| TR-02 | Docker Compose v2                                                           |
| TR-03 | SQL Server 2019+ with TCP/IP enabled on port 1433                           |
| TR-04 | ODBC Driver 17 for SQL Server (host for standalone, container for DAG)      |
| TR-05 | Python 3.13+ (container runtime)                                            |
| TR-06 | Apache Airflow 3.2.0                                                        |
| TR-07 | CeleryExecutor with Redis broker and PostgreSQL backend                     |
| TR-08 | Network connectivity to api.open-meteo.com (port 443) from Docker containers|
| TR-09 | Host disk space: minimum 20 GB free                                         |
| TR-10 | Host RAM: minimum 8 GB (4 GB allocated to Docker)                           |


## Infrastructure Requirements

| ID     | Requirement                                                        | Notes                              |
|--------|--------------------------------------------------------------------|------------------------------------|
| IR-01  | Single Windows machine (development workstation)                   | No cloud or multi-node setup       |
| IR-02  | Docker Desktop running with WSL2 kernel                            | Not Hyper-V backend                |
| IR-03  | SQL Server running as native Windows service                       | Not inside Docker                  |
| IR-04  | Persistent Docker volume for PostgreSQL metadata                   | postgres-db-volume                 |
| IR-05  | Bind-mounted directories for DAGs, logs, config, plugins           | Shared with host filesystem        |
| IR-06  | Host firewall allowing port 1433 inbound from WSL2 subnet          | Usually auto-configured            |
| IR-07  | DNS resolution for api.open-meteo.com from inside containers       | Docker uses host DNS               |


## Business Requirements

| ID    | Requirement                                                          | Priority |
|-------|----------------------------------------------------------------------|----------|
| BR-01 | Collect weather observations for all 27 Egyptian governorates        | Must     |
| BR-02 | Identify cities with extreme temperatures for alert purposes          | Must     |
| BR-03 | Store historical weather data for trend analysis                     | Must     |
| BR-04 | Use a free external weather data source to avoid licensing costs      | Must     |
| BR-05 | Predict temperature from other weather variables using ML             | Should   |
| BR-06 | Provide a human-readable view with day-of-week information           | Should   |


## Assumptions and Constraints

### Assumptions

- Open-Meteo API remains free and available with no authentication required
- SQL Server Express edition storage limits (10 GB) are sufficient for
  projected data growth (~75 MB per year)
- A single worker container can process 27 sequential API calls within the
  5-minute target
- The host machine remains powered on and connected to the internet for
  scheduled runs to execute

### Constraints

- No cloud infrastructure (runs entirely on local machine)
- No horizontal scaling (single worker container)
- No persistent ML model (retrained per batch, discarded)
- No alerting or notification system (alerts stored in DB only)
- No data archival mechanism (table grows indefinitely)
- No CI/CD pipeline (manual deployment via docker-compose)
