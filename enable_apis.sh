#!/bin/bash

# Enable required Google Cloud APIs for Sheet to BigQuery service
# This script enables APIs in the hkd-reporting project

PROJECT_ID="hkd-reporting"

echo "Enabling required APIs for project: $PROJECT_ID"

# Enable Google Sheets API
echo "Enabling Google Sheets API..."
gcloud services enable sheets.googleapis.com --project=$PROJECT_ID

# Enable BigQuery API  
echo "Enabling BigQuery API..."
gcloud services enable bigquery.googleapis.com --project=$PROJECT_ID

# Enable Google Drive API (needed for accessing sheets)
echo "Enabling Google Drive API..."
gcloud services enable drive.googleapis.com --project=$PROJECT_ID

# Enable Cloud Run API (for deployment)
echo "Enabling Cloud Run API..."
gcloud services enable run.googleapis.com --project=$PROJECT_ID

# Enable Cloud Build API (for CI/CD)
echo "Enabling Cloud Build API..."
gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID

# Enable Artifact Registry API (for Docker images)
echo "Enabling Artifact Registry API..."
gcloud services enable artifactregistry.googleapis.com --project=$PROJECT_ID

# Enable Secret Manager API (for secrets)
echo "Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project=$PROJECT_ID

# Check enabled services
echo "Checking enabled services..."
gcloud services list --enabled --project=$PROJECT_ID --filter="name:(sheets.googleapis.com OR bigquery.googleapis.com OR drive.googleapis.com OR run.googleapis.com OR cloudbuild.googleapis.com OR artifactregistry.googleapis.com OR secretmanager.googleapis.com)"

echo "API enablement complete!" 