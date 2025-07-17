#!/bin/bash

# Setup Google Cloud infrastructure for Sheet to BigQuery service
# This script sets up all required resources in the hkd-reporting project

PROJECT_ID="hkd-reporting"
REGION="us-central1"
REPOSITORY_NAME="github-service-sheettobigquery"

echo "Setting up Google Cloud infrastructure for project: $PROJECT_ID"

# Set the default project
echo "Setting default project..."
gcloud config set project $PROJECT_ID

# Enable all required APIs
echo "Enabling APIs..."
./enable_apis.sh

# Create Artifact Registry repository for Docker images
echo "Creating Artifact Registry repository..."
gcloud artifacts repositories create $REPOSITORY_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository for Sheet to BigQuery service" \
    --project=$PROJECT_ID

# Verify repository creation
echo "Verifying Artifact Registry repository..."
gcloud artifacts repositories describe $REPOSITORY_NAME \
    --location=$REGION \
    --project=$PROJECT_ID

# Show IAM commands for Cloud Build service account
echo ""
echo "=== MANUAL STEPS REQUIRED ==="
echo ""
echo "1. Grant Cloud Build service account permissions:"
echo "   Go to: https://console.cloud.google.com/iam-admin/iam?project=$PROJECT_ID"
echo "   Find: [PROJECT_NUMBER]@cloudbuild.gserviceaccount.com"
echo "   Add roles:"
echo "   - Cloud Run Developer"
echo "   - Artifact Registry Writer"
echo "   - Secret Manager Secret Accessor"
echo ""

echo "2. Create/verify secrets in Secret Manager:"
echo "   Go to: https://console.cloud.google.com/security/secret-manager?project=$PROJECT_ID"
echo "   Required secrets:"
echo "   - google_cloud_hkdreporting (service account JSON)"
echo "   - slack_accessToken (Slack bot token)"
echo ""

echo "3. BigQuery datasets should already exist in this project."
echo "   Verify at: https://console.cloud.google.com/bigquery?project=$PROJECT_ID"
echo ""

echo "4. Deploy the service:"
echo "   gcloud builds submit --config cloudbuild.yaml --project=$PROJECT_ID"
echo ""

echo "Setup complete! Please complete the manual steps above." 