# SuperCPE Backend v2

A clean, simplified backend for CPA compliance tracking in New Hampshire.

## Features

- **Monthly CPA Import**: Upload OPLC Excel files to automatically sync NH CPA database
- **Freemium Model**: Free compliance tracking, premium certificate management  
- **PostgreSQL + Alembic**: Proper database migrations for production deployment
- **FastAPI**: Modern, fast API with automatic documentation

## Prerequisites

- **Python 3.13+** (check with `python3 --version`)
- **PostgreSQL** (Homebrew recommended: `brew install postgresql`)
- **Git** (for cloning)

## Installation & Setup

### 1. Clone and Navigate to Project

```bash
git clone https://github.com/djahern-max/supercpe-backend-v2.git
cd supercpe-backend-v2
```

### 2. Set Up Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment (macOS/Linux)
source venv/bin/activate

# Activate virtual environment (Windows)
# venv\Scripts\activate

# Verify you're in the virtual environment (should show (venv))
which python
```

### 3. Install Dependencies

```bash
# Make sure you're in the virtual environment first!
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Set Up PostgreSQL Database

```bash
# Start PostgreSQL service (if not running)
brew services start postgresql

# Create the database
createdb -U postgres supercpe_v2

# Test connection
psql -U postgres supercpe_v2 -c "SELECT version();"
```

### 5. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit the .env file with your database credentials
nano .env
# OR
code .env
```

**Update .env file:**
```bash
# Database - Update username if different
DATABASE_URL=postgresql://postgres@localhost/supercpe_v2

# API Configuration
API_TITLE=SuperCPE v2
API_VERSION=2.0.0

# Security - Change this in production!
SECRET_KEY=your-secret-key-change-in-production-make-this-long-and-random
```

### 6. Run Database Migrations

```bash
# Create database tables
alembic upgrade head

# Verify tables were created
psql -U postgres supercpe_v2 -c "\dt"
```

## Running the Application

### Start the Development Server

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Start the FastAPI development server
python run.py

# Server will start on http://localhost:8000
```

### Verify Application is Running

Open another terminal and test:

```bash
# Test basic endpoints
curl http://localhost:8000/
curl http://localhost:8000/health
curl http://localhost:8000/api/cpas/stats/summary

# View interactive API docs in browser
open http://localhost:8000/docs
```

## Importing CPA Data

### Upload OPLC Excel File

```bash
# Upload the monthly OPLC CPA list
curl -X POST http://localhost:8000/api/admin/upload-cpa-list \
  -F "file=@path/to/Active_NH_CPAs.xlsx"

# Check import results
curl http://localhost:8000/api/cpas/stats/summary
```

### Find a Specific CPA

```bash
# Get CPA by license number
curl http://localhost:8000/api/cpas/07308

# List first 10 CPAs
curl "http://localhost:8000/api/cpas/?limit=10"
```

## Development Commands

### Working with Virtual Environment

```bash
# Activate virtual environment
source venv/bin/activate

# Deactivate virtual environment
deactivate

# Install new package
pip install package-name
pip freeze > requirements.txt

# Check if you're in virtual environment
which python  # Should show path with /venv/
```

### Database Operations

```bash
# Create new migration after model changes
alembic revision --autogenerate -m "description of changes"

# Apply migrations
alembic upgrade head

# Check current migration
alembic current

# View migration history
alembic history

# Connect to database directly
psql -U postgres supercpe_v2
```

### Useful Database Queries

```bash
# Count total CPAs
psql -U postgres supercpe_v2 -c "SELECT count(*) FROM cpas;"

# View recent imports
psql -U postgres supercpe_v2 -c "SELECT license_number, full_name, last_oplc_sync FROM cpas ORDER BY last_oplc_sync DESC LIMIT 5;"

# Check renewal dates distribution
psql -U postgres supercpe_v2 -c "SELECT license_expiration_date, count(*) FROM cpas GROUP BY license_expiration_date ORDER BY license_expiration_date;"
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API status and version |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Interactive API documentation |
| `GET` | `/api/cpas/` | List all CPAs (paginated) |
| `GET` | `/api/cpas/{license_number}` | Get specific CPA |
| `GET` | `/api/cpas/stats/summary` | CPA statistics |
| `POST` | `/api/admin/upload-cpa-list` | Upload monthly OPLC Excel file |

## Project Structure

```
supercpe-backend-v2/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── api/
│   │   ├── cpas.py            # CPA endpoints
│   │   └── uploads.py         # File upload endpoints
│   ├── core/
│   │   ├── config.py          # Configuration settings
│   │   └── database.py        # Database connection
│   ├── models/
│   │   ├── cpa.py             # CPA database model
│   │   └── compliance.py      # Compliance requirements model
│   └── services/
│       └── cpa_import.py      # OPLC Excel import logic
├── alembic/                   # Database migration files
├── requirements.txt           # Python dependencies
├── run.py                     # Development server startup
├── .env                       # Environment variables (local)
├── .env.example              # Environment template
└── README.md                 # This file
```

## Common Issues & Solutions

### Virtual Environment Issues

```bash
# If virtual environment command not found
python3 -m pip install --user virtualenv

# If wrong Python version in venv
rm -rf venv
python3.13 -m venv venv
source venv/bin/activate
```

### Database Connection Issues

```bash
# If PostgreSQL not running
brew services start postgresql

# If database doesn't exist
createdb -U postgres supercpe_v2

# If permission denied
createuser -s postgres  # Create postgres user with superuser rights
```

### Import Errors

```bash
# If module not found errors
source venv/bin/activate  # Make sure venv is active
pip install -r requirements.txt

# If alembic command not found
pip install alembic
```

## Monthly Update Process

1. **Download new OPLC file** (Monthly from NH OPLC)
2. **Upload via API**:
   ```bash
   curl -X POST http://localhost:8000/api/admin/upload-cpa-list \
     -F "file=@New_Monthly_File.xlsx"
   ```
3. **Review results** - Check created/updated counts
4. **Commit to git** if any code changes

## Deployment

Designed for Digital Ocean droplets with managed PostgreSQL:

1. Create DO droplet (Ubuntu 22.04)
2. Set up managed PostgreSQL database
3. Update `.env` with production database URL
4. Run migrations: `alembic upgrade head`
5. Start with production WSGI server (Gunicorn)

## Development Workflow

1. **Activate virtual environment**: `source venv/bin/activate`
2. **Make model changes** in `app/models/`
3. **Generate migration**: `alembic revision --autogenerate -m "description"`
4. **Review migration file** in `alembic/versions/`
5. **Apply migration**: `alembic upgrade head`
6. **Test changes**: `python run.py`
7. **Commit to git**: `git add . && git commit -m "description"`

## License

MIT License - see LICENSE file for details.

---

## Quick Reference

**Start Development:**
```bash
cd supercpe-backend-v2
source venv/bin/activate
python run.py
```

**Stop Development:**
```bash
# Ctrl+C to stop server
deactivate  # Exit virtual environment
```

**Database Reset:**
```bash
dropdb supercpe_v2
createdb -U postgres supercpe_v2
alembic upgrade head
```
