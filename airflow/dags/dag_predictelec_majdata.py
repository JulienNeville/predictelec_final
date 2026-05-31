from airflow import DAG
from airflow.decorators import task
import subprocess
import pendulum

with DAG(
        dag_id="run_pipeline_predictelec_data",
        start_date=pendulum.now("UTC").subtract(days=1),
        #tous les jours du mois à 1h00 (utc+0) sauf le 1er du mois
        schedule="0 1 2-31 * *",
        catchup=False,
        tags=["predictelec","data","production","meteo"],
) as dag:
    # -------------------------
    # MAJ DONNEES PRODUCTION
    # -------------------------

    @task
    def run_production ():
      subprocess.run(
        ["python", "/opt/predictelec/current/predictelec/main.py","MAJ_PROD"],
        check=True
    )

    # -------------------------
    # MAJ DONNEES METEO VEILLE
    # -------------------------
 
    @task
    def run_meteo ():
      subprocess.run(
        ["python", "/opt/predictelec/current/predictelec/main.py","MAJ_METEO"],
        check=True
    )

    # -------------------------
    # PIPELINE
    # -------------------------

    run_production()

    run_meteo() 
