#!/bin/bash

# Sheet to BigQuery Job Deployment Script
# This script deploys the job-based architecture for Sheet to BigQuery transfers

set -e

PROJECT_ID="hkd-reporting"
REGION="us-central1"
JOB_NAME="sheettobigquery-job"

echo "🚀 Deploying Sheet to BigQuery Job Architecture"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Job Name: $JOB_NAME"
echo ""

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ No active gcloud authentication found. Please run 'gcloud auth login'"
    exit 1
fi

# Set project
echo "📋 Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Build and deploy the Cloud Run Job
echo "🔨 Building and deploying Cloud Run Job..."
gcloud builds submit --config cloudbuild-job.yaml --project=$PROJECT_ID

# Verify deployment
echo "✅ Verifying job deployment..."
if gcloud run jobs describe $JOB_NAME --region=$REGION >/dev/null 2>&1; then
    echo "✅ Job deployed successfully!"
    
    # Display job details
    echo ""
    echo "📊 Job Details:"
    gcloud run jobs describe $JOB_NAME --region=$REGION --format="table(
        metadata.name,
        spec.template.spec.template.spec.containers[0].image,
        spec.template.spec.template.spec.containers[0].resources.limits.memory,
        spec.template.spec.template.spec.containers[0].resources.limits.cpu,
        spec.template.spec.taskTimeout
    )"
else
    echo "❌ Job deployment verification failed"
    exit 1
fi

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "Next steps:"
echo "1. Test job execution:"
echo "   python job_helper.py example"
echo "   python job_helper.py execute --config-file your_config.json"
echo ""
echo "2. Set up job orchestrator (optional):"
echo "   python job_orchestrator.py --dry-run --postgres-host=... --postgres-db=... --postgres-user=... --postgres-password=..."
echo ""
echo "3. Monitor job executions:"
echo "   python job_helper.py status"
echo "   python job_helper.py list"
echo ""
echo "📚 Documentation:"
echo "   - README-JOB.md - Job architecture overview"
echo "   - MIGRATION_GUIDE.md - Step-by-step migration guide" 