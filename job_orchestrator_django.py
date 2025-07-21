#!/usr/bin/env python3
"""
Standalone Job Orchestrator for Sheet to BigQuery Jobs

This script connects directly to the Django database to fetch configurations
and triggers individual Cloud Run Jobs for each configuration.
"""

import os
import json
import logging
import subprocess
import tempfile
import time
from typing import List, Dict, Optional
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DjangoJobOrchestrator:
    def __init__(self, postgres_host: str, postgres_db: str, postgres_user: str, 
                 postgres_password: str, postgres_port: int = 5432, 
                 job_name: str = "sheettobigquery-job", region: str = "us-central1"):
        """Initialize the Django job orchestrator with database connection"""
        self.postgres_config = {
            'host': postgres_host,
            'database': postgres_db,
            'user': postgres_user,
            'password': postgres_password,
            'port': postgres_port
        }
        self.job_name = job_name
        self.region = region
        
    def get_active_configs(self) -> List[Dict]:
        """Fetch active sheet-to-bigquery configurations from Django database"""
        try:
            logger.info("Connecting to Django database...")
            with psycopg2.connect(**self.postgres_config) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Query the Django model table
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
                        run_frequency_hours,
                        created_at,
                        updated_at
                    FROM sheet_to_bigquery_sheettobigqueryconfig 
                    WHERE is_active = true
                    ORDER BY created_at DESC
                    """
                    
                    cursor.execute(query)
                    configs = cursor.fetchall()
                    
                    # Convert to list of dicts and add should_run logic
                    config_dicts = []
                    for config in configs:
                        config_dict = dict(config)
                        
                        # Add should_run logic (mimics Django model property)
                        config_dict['should_run'] = self._should_run_config(config_dict)
                        
                        config_dicts.append(config_dict)
                    
                    logger.info(f"Found {len(config_dicts)} active configurations")
                    return config_dicts
                    
        except Exception as e:
            logger.error(f"Error fetching configurations from Django database: {e}")
            raise
    
    def _should_run_config(self, config: Dict) -> bool:
        """Determine if a config should run based on frequency and last run time"""
        if not config.get('is_active'):
            return False
        
        run_frequency_hours = config.get('run_frequency_hours', 24)
        if run_frequency_hours == 0:
            return False  # Manual execution only
            
        last_run = config.get('last_run')
        if not last_run:
            return True  # Never run before
            
        # Check if enough time has passed since last run
        if isinstance(last_run, str):
            last_run = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
        
        time_since_last_run = datetime.now(last_run.tzinfo) - last_run
        required_interval = timedelta(hours=run_frequency_hours)
        
        return time_since_last_run >= required_interval
    
    def should_run_config(self, config: Dict) -> bool:
        """Determine if a config should run based on frequency and last run time"""
        return config.get('should_run', False)
    
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
            # Handle both string and dict formats
            if isinstance(config['custom_schema'], str):
                env_vars['CUSTOM_SCHEMA'] = config['custom_schema']
            else:
                env_vars['CUSTOM_SCHEMA'] = json.dumps(config['custom_schema'])
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        
        # Write environment variables in YAML format for gcloud
        for key, value in env_vars.items():
            # Escape single quotes in values
            escaped_value = str(value).replace("'", "''")
            temp_file.write(f"{key}: '{escaped_value}'\n")
        
        temp_file.close()
        
        logger.info(f"Created environment file: {temp_file.name}")
        return temp_file.name
    
    def execute_job(self, config: Dict) -> bool:
        """Execute a Cloud Run Job for the given configuration"""
        env_file = None
        try:
            logger.info(f"Starting job for config: {config['name']} (ID: {config['config_id']})")
            
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
                self.update_last_run_django(config['config_id'])
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
    
    def update_last_run_django(self, config_id: int):
        """Update the last_run timestamp for a configuration in Django database"""
        try:
            with psycopg2.connect(**self.postgres_config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE sheet_to_bigquery_sheettobigqueryconfig SET last_run = NOW() WHERE id = %s",
                        (config_id,)
                    )
                    conn.commit()
                    logger.info(f"Updated last_run for config ID: {config_id}")
        except Exception as e:
            logger.error(f"Error updating last_run for config ID {config_id}: {e}")
    
    def run_orchestrator(self, max_parallel_jobs: int = 5, dry_run: bool = False, 
                        filter_configs: List[str] = None):
        """Main orchestrator method that fetches configs and runs jobs"""
        try:
            logger.info("Starting Django Sheet to BigQuery Job Orchestrator")
            
            # Fetch active configurations
            configs = self.get_active_configs()
            
            if not configs:
                logger.info("No active configurations found")
                return
            
            # Filter configs if specified
            if filter_configs:
                configs = [c for c in configs if c['name'] in filter_configs]
                logger.info(f"Filtered to {len(configs)} specified configurations")
            
            # Filter configs that should run
            configs_to_run = [config for config in configs if self.should_run_config(config)]
            
            if not configs_to_run:
                logger.info("No configurations are due to run")
                # Show status of all configs
                logger.info("Configuration status:")
                for config in configs:
                    frequency = config.get('run_frequency_hours', 'Unknown')
                    last_run = config.get('last_run', 'Never')
                    status = "Due" if config.get('should_run') else "Not due"
                    logger.info(f"  - {config['name']}: {status} (freq: {frequency}h, last: {last_run})")
                return
            
            logger.info(f"Processing {len(configs_to_run)} configurations")
            
            if dry_run:
                logger.info("DRY RUN MODE - would process these configs:")
                for config in configs_to_run:
                    frequency = config.get('run_frequency_hours', 'Unknown')
                    last_run = config.get('last_run', 'Never')
                    logger.info(f"  - {config['name']} (ID: {config['config_id']}) - "
                              f"Frequency: {frequency}h, Last run: {last_run}")
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
    parser = argparse.ArgumentParser(description='Django Sheet to BigQuery Job Orchestrator')
    parser.add_argument('--postgres-host', required=True, help='Django database host')
    parser.add_argument('--postgres-db', required=True, help='Django database name')
    parser.add_argument('--postgres-user', required=True, help='Django database username')
    parser.add_argument('--postgres-password', required=True, help='Django database password')
    parser.add_argument('--postgres-port', type=int, default=5432, help='Django database port')
    parser.add_argument('--max-parallel-jobs', type=int, default=5, help='Maximum parallel jobs')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be executed without running')
    parser.add_argument('--config-names', nargs='*', help='Specific configuration names to process')
    
    args = parser.parse_args()
    
    # Create orchestrator
    orchestrator = DjangoJobOrchestrator(
        postgres_host=args.postgres_host,
        postgres_db=args.postgres_db,
        postgres_user=args.postgres_user,
        postgres_password=args.postgres_password,
        postgres_port=args.postgres_port
    )
    
    # Run orchestrator
    orchestrator.run_orchestrator(
        max_parallel_jobs=args.max_parallel_jobs,
        dry_run=args.dry_run,
        filter_configs=args.config_names
    )

if __name__ == "__main__":
    main() 