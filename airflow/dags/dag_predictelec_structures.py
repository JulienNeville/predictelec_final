from airflow import DAG
from airflow.decorators import task
import subprocess
import pendulum
#from airflow.operators.bash import BashOperator


with DAG(
	dag_id="run_pipeline_predictelec_globale",
        start_date=pendulum.now("UTC").subtract(days=1),
	#tous les 1ers jours du mois à 0h05 (utc+0)
	schedule="5 0 1 * *",
	catchup=False,
	tags=["predictelec","global","structure","production","meteo"],
) as dag:

  #maj structure : centrales electriques+stations météos+liens entre elles
  @task
  def run_structures (): 
    subprocess.run(
	["python","/opt/predictelec/current/predictelec/main.py","MAJ_STRUCTURES"],
	check=True
  )

  #maj données production
  @task
  def run_production ():
    subprocess.run(
        ["python", "/opt/predictelec/current/predictelec/main.py","MAJ_PROD"],
        check=True
   )

  #maj données meteo veille (données non validées
  @task
  def run_meteo ():
    subprocess.run(
        ["python", "/opt/predictelec/current/predictelec/main.py","MAJ_METEO"],
        check=True
  )

  #maj données meteo mois précédent jusqu'à hier (données validées)
  @task
  def run_meteo_prec ():
    subprocess.run(
        ["python", "/opt/predictelec/current/predictelec/main.py","MAJ_METEO_PREC"],
        check=True
  )

  run_structures() >> [run_production(),run_meteo()] >> run_meteo_prec()
