# Enable required Google Cloud APIs for Sheet to BigQuery service
# This script enables APIs in the hkd-reporting project

$PROJECT_ID = "hkd-reporting"

Write-Host "Enabling required APIs for project: $PROJECT_ID" -ForegroundColor Green

# Enable Google Sheets API
Write-Host "Enabling Google Sheets API..." -ForegroundColor Yellow
gcloud services enable sheets.googleapis.com --project=$PROJECT_ID

# Enable BigQuery API  
Write-Host "Enabling BigQuery API..." -ForegroundColor Yellow
gcloud services enable bigquery.googleapis.com --project=$PROJECT_ID

# Enable Google Drive API (needed for accessing sheets)
Write-Host "Enabling Google Drive API..." -ForegroundColor Yellow
gcloud services enable drive.googleapis.com --project=$PROJECT_ID

# Enable Cloud Run API (for deployment)
Write-Host "Enabling Cloud Run API..." -ForegroundColor Yellow
gcloud services enable run.googleapis.com --project=$PROJECT_ID

# Enable Cloud Build API (for CI/CD)
Write-Host "Enabling Cloud Build API..." -ForegroundColor Yellow
gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID

# Enable Artifact Registry API (for Docker images)
Write-Host "Enabling Artifact Registry API..." -ForegroundColor Yellow
gcloud services enable artifactregistry.googleapis.com --project=$PROJECT_ID

# Enable Secret Manager API (for secrets)
Write-Host "Enabling Secret Manager API..." -ForegroundColor Yellow
gcloud services enable secretmanager.googleapis.com --project=$PROJECT_ID

# Check enabled services
Write-Host "Checking enabled services..." -ForegroundColor Yellow
gcloud services list --enabled --project=$PROJECT_ID --filter="name:(sheets.googleapis.com OR bigquery.googleapis.com OR drive.googleapis.com OR run.googleapis.com OR cloudbuild.googleapis.com OR artifactregistry.googleapis.com OR secretmanager.googleapis.com)"

Write-Host "API enablement complete!" -ForegroundColor Green 