#!/usr/bin/env python3
"""
Job Orchestrator for Sheet to BigQuery Jobs

This script fetches active configurations from Postgres and triggers
individual Cloud Run Jobs for each configuration.
"""

import os
import json
import logging
import subprocess
import tempfile
import time
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JobOrchestrator:
    def __init__(self, postgres_host: str, postgres_db: str, postgres_user: str, 
                 postgres_password: str, postgres_port: int = 5432):
        """Initialize the job orchestrator with database connection details"""
        self.postgres_config = {
            'host': postgres_host,
            'database': postgres_db,
            'user': postgres_user,
            'password': postgres_password,
            'port': postgres_port
        }
        self.job_name = "sheettobigquery-job"
        self.region = "us-central1"
        
    def get_active_configs(self) -> List[Dict]:
        """Fetch active sheet-to-bigquery configurations from Postgres"""
        try:
            logger.info("Connecting to Postgres database...")
            with psycopg2.connect(**self.postgres_config) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Adjust this query based on your actual table structure
                    query = """
                    SELECT 
                        id as config_id,
                        name,
                        google_sheet_url,
                        google_sheet_tab_name,
                        google_cloud_project_id,
                        bigquery_dataset_id,
                        bigquery_table_id,
                        schema_handling,
                        custom_schema,
                        is_active,
                        last_run,
                        run_frequency_hours
                    FROM sheet_to_bigquery_configs 
                    WHERE is_active = true
                    """
                    
                    cursor.execute(query)
                    configs = cursor.fetchall()
                    
                    logger.info(f"Found {len(configs)} active configurations")
                    return [dict(config) for config in configs]
                    
        except Exception as e:
            logger.error(f"Error fetching configurations from database: {e}")
            raise
    
    def should_run_config(self, config: Dict) -> bool:
        """Determine if a config should run based on frequency and last run time"""
        try:
            if not config.get('run_frequency_hours'):
                # If no frequency specified, run every time
                return True
                
            last_run = config.get('last_run')
            if not last_run:
                # Never run before, should run now
                return True
                
            # Check if enough time has passed since last run
            from datetime import datetime, timedelta
            
            if isinstance(last_run, str):
                last_run = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
            
            time_since_last_run = datetime.now(last_run.tzinfo) - last_run
            required_interval = timedelta(hours=config['run_frequency_hours'])
            
            should_run = time_since_last_run >= required_interval
            
            if should_run:
                logger.info(f"Config '{config['name']}' is due to run (last run: {last_run})")
            else:
                logger.info(f"Config '{config['name']}' not due yet (last run: {last_run})")
                
            return should_run
            
        except Exception as e:
            logger.warning(f"Error checking run frequency for config '{config.get('name')}': {e}")
            # If we can't determine, err on the side of running
            return True
    
    def create_env_vars_file(self, config: Dict) -> str:
        """Create a temporary environment variables file for the job"""
        env_vars = {
            'CONFIG_ID': str(config['config_id']),
            'CONFIG_NAME': config['name'],
            'GOOGLE_SHEET_URL': config['google_sheet_url'],
            'GOOGLE_CLOUD_PROJECT_ID': config['google_cloud_project_id'],
            'BIGQUERY_DATASET_ID': config['bigquery_dataset_id'],
            'BIGQUERY_TABLE_ID': config['bigquery_table_id'],
            'SCHEMA_HANDLING': config.get('schema_handling', 'auto_detect')
        }
        
        # Add optional parameters
        if config.get('google_sheet_tab_name'):
            env_vars['GOOGLE_SHEET_TAB_NAME'] = config['google_sheet_tab_name']
        
        if config.get('custom_schema'):
            env_vars['CUSTOM_SCHEMA'] = json.dumps(config['custom_schema']) if isinstance(config['custom_schema'], dict) else config['custom_schema']
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        
        # Write environment variables in YAML format for gcloud
        for key, value in env_vars.items():
            temp_file.write(f"{key}: '{value}'\n")
        
        temp_file.close()
        
        logger.info(f"Created environment file: {temp_file.name}")
        return temp_file.name
    
    def execute_job(self, config: Dict) -> bool:
        """Execute a Cloud Run Job for the given configuration"""
        env_file = None
        try:
            logger.info(f"Starting job for config: {config['name']}")
            
            # Create environment variables file
            env_file = self.create_env_vars_file(config)
            
            # Build gcloud command
            cmd = [
                'gcloud', 'run', 'jobs', 'execute', self.job_name,
                '--region', self.region,
                '--env-vars-file', env_file,
                '--wait'  # Wait for job completion
            ]
            
            logger.info(f"Executing command: {' '.join(cmd)}")
            
            # Execute the job
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2400  # 40 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Job completed successfully for config: {config['name']}")
                self.update_last_run(config['config_id'])
                return True
            else:
                logger.error(f"Job failed for config: {config['name']}")
                logger.error(f"Error output: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Job timed out for config: {config['name']}")
            return False
        except Exception as e:
            logger.error(f"Error executing job for config: {config['name']}: {e}")
            return False
        finally:
            # Clean up temporary file
            if env_file and os.path.exists(env_file):
                os.unlink(env_file)
    
    def update_last_run(self, config_id: int):
        """Update the last_run timestamp for a configuration"""
        try:
            with psycopg2.connect(**self.postgres_config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE sheet_to_bigquery_configs SET last_run = NOW() WHERE id = %s",
                        (config_id,)
                    )
                    conn.commit()
                    logger.info(f"Updated last_run for config ID: {config_id}")
        except Exception as e:
            logger.error(f"Error updating last_run for config ID {config_id}: {e}")
    
    def run_orchestrator(self, max_parallel_jobs: int = 5, dry_run: bool = False):
        """Main orchestrator method that fetches configs and runs jobs"""
        try:
            logger.info("Starting Sheet to BigQuery Job Orchestrator")
            
            # Fetch active configurations
            configs = self.get_active_configs()
            
            if not configs:
                logger.info("No active configurations found")
                return
            
            # Filter configs that should run
            configs_to_run = [config for config in configs if self.should_run_config(config)]
            
            if not configs_to_run:
                logger.info("No configurations are due to run")
                return
            
            logger.info(f"Processing {len(configs_to_run)} configurations")
            
            if dry_run:
                logger.info("DRY RUN MODE - would process these configs:")
                for config in configs_to_run:
                    logger.info(f"  - {config['name']} (ID: {config['config_id']})")
                return
            
            # Execute jobs (simple sequential execution for now)
            # TODO: Implement parallel execution with max_parallel_jobs limit
            successful_jobs = 0
            failed_jobs = 0
            
            for config in configs_to_run:
                try:
                    success = self.execute_job(config)
                    if success:
                        successful_jobs += 1
                    else:
                        failed_jobs += 1
                        
                    # Small delay between jobs to avoid overwhelming the system
                    time.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Unexpected error processing config {config['name']}: {e}")
                    failed_jobs += 1
            
            logger.info(f"Orchestrator completed. Successful: {successful_jobs}, Failed: {failed_jobs}")
            
        except Exception as e:
            logger.error(f"Error in orchestrator: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Sheet to BigQuery Job Orchestrator')
    parser.add_argument('--postgres-host', required=True, help='Postgres host')
    parser.add_argument('--postgres-db', required=True, help='Postgres database name')
    parser.add_argument('--postgres-user', required=True, help='Postgres username')
    parser.add_argument('--postgres-password', required=True, help='Postgres password')
    parser.add_argument('--postgres-port', type=int, default=5432, help='Postgres port')
    parser.add_argument('--max-parallel-jobs', type=int, default=5, help='Maximum parallel jobs')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be executed without running')
    
    args = parser.parse_args()
    
    # Create orchestrator
    orchestrator = JobOrchestrator(
        postgres_host=args.postgres_host,
        postgres_db=args.postgres_db,
        postgres_user=args.postgres_user,
        postgres_password=args.postgres_password,
        postgres_port=args.postgres_port
    )
    
    # Run orchestrator
    orchestrator.run_orchestrator(
        max_parallel_jobs=args.max_parallel_jobs,
        dry_run=args.dry_run
    )

if __name__ == "__main__":
    main() 