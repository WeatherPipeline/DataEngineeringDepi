# Development Standards


## Coding Standards

### Python Style

All DAG code follows these conventions, consistent with the existing codebase:

- Indentation: 4 spaces, no tabs
- Line length: no strict limit, but keep readable (existing code averages ~70 chars)
- String quotes: double quotes for strings, single quotes only inside f-strings
    if needed to avoid escaping
- Blank lines: one blank line between functions, two blank lines between
    sections (separated by comment headers)
- Trailing whitespace: none

### Section Headers

The DAG file uses comment blocks to separate logical sections:

```python
# =====================================================
# Section Name
# =====================================================
```

New sections should follow this pattern for consistency.

### Variable Naming

| Context              | Convention          | Example                         |
|----------------------|---------------------|---------------------------------|
| Constants            | UPPER_SNAKE_CASE    | SERVER, DATABASE, DRIVER        |
| Functions            | snake_case          | create_table, load_data         |
| Variables            | snake_case          | all_data, inserted, skipped     |
| DataFrame columns    | snake_case          | temperature, wind_speed         |
| DAG IDs              | snake_case          | weather_etl_pipeline            |
| Task IDs             | snake_case          | create_weather_table            |

### Function Structure

Functions should:
- Be defined with `def` on its own line
- Have a blank line after the definition
- Use a single blank line between logical steps inside the function
- Print status messages using the `[SUCCESS]`, `[ERROR]`, `[SKIPPED]`,
  `[INSERTED]` prefix pattern
- Return values explicitly (no implicit None returns for void functions)

### SQL in Python

- Use triple-quoted multi-line strings for SQL queries
- Use SQLAlchemy `text()` with named parameters (`:city`, `:timestamp`)
    for parameterized queries
- Never use string formatting or f-strings to build SQL queries
- Use `engine.begin()` for DDL and write operations (auto-commit)
- Use `engine.connect()` for read operations

### Error Handling

- Use specific exception types where possible
- The existing pattern uses a generic `except Exception as e` in the extract
    loop to catch all API failures per city -- this is acceptable for network
    calls but avoid it for database or logic errors
- Always log the error context (city name, query, etc.)


## DAG File Structure

A DAG file should follow this order:

```python
# 1. Imports
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
import requests
# ... other imports

# 2. Default arguments
default_args = { ... }

# 3. DAG definition
dag = DAG( ... )

# 4. Configuration constants
SERVER = "..."
DATABASE = "..."
# ... connection setup

# 5. Data definitions (lists, dicts)
governorates = [ ... ]

# 6. Helper functions
def create_table(): ...
def extract_transform(): ...
def record_exists(): ...
def load_data(): ...

# 7. Task definitions
create_table_task = PythonOperator( ... )
load_weather_task = PythonOperator( ... )

# 8. Pipeline dependencies
create_table_task >> load_weather_task
```

No executable code at module level beyond definitions and the DAG object.
Airflow imports the file top-to-bottom on every parse cycle.


## Import Conventions

Order of imports (separated by blank lines):

```python
# 1. Airflow imports
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# 2. Python standard library
from datetime import datetime, timedelta

# 3. Third-party packages
import requests
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.linear_model import LinearRegression
```

Import path for PythonOperator in Airflow 3.x:

```python
# Correct (Airflow 3.x)
from airflow.providers.standard.operators.python import PythonOperator

# Deprecated (Airflow 2.x, generates warning in 3.x)
from airflow.operators.python import PythonOperator
```


## Git Workflow

### Branching

| Branch       | Purpose                              |
|--------------|--------------------------------------|
| main         | Stable, deployed code                |
| dev          | Active development                   |
| feature/*    | New features (e.g., feature/add-alerting) |
| fix/*        | Bug fixes (e.g., fix/api-timeout)    |

### Commit Messages

Format:

```
<type>: <short description>

<optional longer description>
```

Types:

| Type     | Usage                                   |
|----------|-----------------------------------------|
| feat     | New feature or functionality            |
| fix      | Bug fix                                 |
| docs     | Documentation changes only              |
| refactor | Code restructuring without behavior change |
| config   | Configuration or infrastructure change  |
| chore    | Maintenance (cleanup, dependencies)     |

Examples:

```
feat: add air_pressure to weather metrics collection
fix: increase API timeout from 10s to 30s for Red Sea governorate
docs: add deployment architecture diagram to docs
config: upgrade Airflow from 2.8.1 to 3.2.0
refactor: extract connection config into Airflow variables
```

### Files to Ignore

The `.gitignore` excludes:

- `__pycache__/` and `*.pyc` (Python bytecode)
- `.venv/` (local virtual environment)
- `airflow-project/logs/` (runtime logs, regenerated)
- `airflow-project/.env` (secrets and Fernet key)
- `.vscode/`, `.idea/` (IDE configs)
- `desktop.ini`, `Thumbs.db` (OS files)
- `*.docx` (binary documents)


## Adding a New Python Dependency

1. Add the package to the `RUN pip install` line in `airflow-project/Dockerfile`
2. Add the pinned version to `requirements.txt`
3. Rebuild: `docker-compose build && docker-compose up -d`

Do not use `_PIP_ADDITIONAL_REQUIREMENTS` in docker-compose.yaml for permanent
dependencies. It reinstalls on every container start, adding 30+ seconds to
startup time.


## Adding a New DAG

1. Create a new `.py` file in `airflow-project/dags/`
2. Follow the DAG file structure above
3. The dag-processor will detect the new file within 30 seconds
4. No container restart needed

Each DAG should be in its own file. Do not define multiple DAGs in one file.


## Configuration Management

### Secrets

Currently, the SQL Server password is hardcoded in the DAG file. This is a
known security gap. The recommended migration path is:

1. Store credentials in Airflow Connections (UI > Admin > Connections)
2. Reference them in the DAG via environment variables or the Airflow secrets
    backend
3. Never commit `.env` files or passwords to version control

### Environment-Specific Values

The only environment-specific value is `SERVER`:
- `host.docker.internal` inside Docker
- `localhost` for standalone testing

If deploying to multiple environments, use Airflow Variables or environment
variables to avoid hardcoding.
