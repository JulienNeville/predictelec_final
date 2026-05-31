from airflow import DAG
from airflow.decorators import task
import pendulum
import os

with DAG(
    dag_id="dag_test_repertoire_projet",
    start_date=pendulum.now("UTC").subtract(days=1),
    schedule=None,
    catchup=False,
    tags=["predictelec"],
) as dag:

	@task 
	def debug_pythonpath(): 
		import sys
		print("PYTHONPATH =", sys.path)
		from predictelec.api.api_meteo import get_valid_token
		print("import ok")
		print(f"test accès .env:{os.getenv('DB_NAME')}")


	debug_pythonpath()
