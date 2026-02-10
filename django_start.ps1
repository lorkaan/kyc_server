param(
    [string]$managePyPath = ".\kycserver\manage.py",   # Path to manage.py
    [string]$queryJsonPath = ".\test_query.json",      # Path to JSON file
    [string]$userName = "",                            # Optional owner username
    [string]$adminUser = "admin",                      # Admin username to ensure exists
    [string]$adminPassword = "LAUrod92"                # Admin password (required if creating)
)

# -----------------------
# HARD RESET DATABASE (DEV ONLY)
# -----------------------

# Path to db.sqlite3 (adjust if yours lives elsewhere)
$dbPath = Join-Path (Split-Path $managePyPath) ".\db.sqlite3"
$dbPath = Resolve-Path $dbPath -ErrorAction SilentlyContinue

if ($dbPath -and (Test-Path $dbPath)) {
    Write-Host "Deleting existing database at $dbPath"
    Remove-Item $dbPath -Force
} else {
    Write-Host "No existing database found. Skipping delete."
}

# Normalize paths
$managePyPath = Resolve-Path $managePyPath
$queryJsonPath = Resolve-Path $queryJsonPath

# Directory containing manage.py (THIS is what Django needs)
$projectRoot = Split-Path $managePyPath

Write-Host "Project root: $projectRoot"

# -----------------------
# 1. Run migrations
# -----------------------
Write-Host "Running Django migrations..."
python $managePyPath migrate
if ($LASTEXITCODE -ne 0) {
    throw "Migration failed"
}

# -----------------------
# 2. Import queries + ensure admin
# -----------------------
Write-Host "Importing queries from $queryJsonPath ..."

$importScript = @"
import os
import sys
import django

# Ensure Django project root is on sys.path
sys.path.insert(0, r"$projectRoot")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kycserver.settings")
django.setup()

from django.contrib.auth import get_user_model
from utils.load_query_presets import import_queries_from_file

User = get_user_model()

# -----------------------
# Ensure admin user exists
# -----------------------
admin_username = r"$adminUser".strip()
admin_password = r"$adminPassword".strip()

admin_user = None

# Check if the admin user already exists
admin_user = User.objects.filter(username=admin_username).first()

# If the admin user doesn't exist, create it
if not admin_user:
    if not admin_password:
        raise ValueError(f"Admin user '{admin_username}' does not exist and no password was provided.")
    print(f"Creating superuser '{admin_username}'...")
    admin_user = User.objects.create_superuser(username=admin_username, password=admin_password)
else:
    # Check if user is a superuser
    if not admin_user.is_superuser:
        print(f"User '{admin_username}' exists but is not a superuser. You may need to manually upgrade their privileges.")
    else:
        print(f"Admin user '{admin_username}' exists and is a superuser.")

# -----------------------
# Determine query owner
# -----------------------
user = None
owner_username = r"$userName".strip()

if owner_username:
    user = User.objects.filter(username=owner_username).first()
    if not user:
        print(f"Owner user '{owner_username}' does not exist. Queries will be imported as system queries.")

# -----------------------
# Import queries
# -----------------------
created_queries = import_queries_from_file(r"$queryJsonPath", owner=user)

for q in created_queries:
    print(f"Imported query: {q.name} (System: {q.is_system}, Owner: {q.owner})")
"@

# Write temp script
$tempScriptPath = [System.IO.Path]::GetTempFileName() + ".py"
Set-Content -Path $tempScriptPath -Value $importScript -Encoding UTF8

# Run the import script
python $tempScriptPath
if ($LASTEXITCODE -ne 0) {
    Remove-Item $tempScriptPath
    throw "Query import failed"
}

# Cleanup the temporary script
Remove-Item $tempScriptPath

# -----------------------
# 3. Load additional data (optional)
# -----------------------
Write-Host "Loading additional test data..."
python $managePyPath migrate
python $managePyPath load_test_data

# -----------------------
# 4. Start server
# -----------------------
Write-Host "Starting Django development server..."
python $managePyPath runserver
