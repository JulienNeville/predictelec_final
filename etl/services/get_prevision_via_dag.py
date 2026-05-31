#from airflow import DAG
#from airflow.decorators import task
import dotenv
import pendulum
from datetime import timedelta
import os
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd

# debug : ajoute répertoire parent au PYTHONPATH
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

#  IMPORT code
from api.api_meteo import get_valid_token
from db.base import Database
from models.station import Station
from models.meteo import Meteo

## utilisation .env projet : recherche du chemin relatif du fichier
#from dotenv import load_dotenv
#base_dir = os.path.dirname(__file__)
#dotenv_path = os.path.abspath(
        #os.path.join(base_dir, "..", "plugins", "PREDICTELEC_ETL", ".env")
#)
#print("chargement .env depuis:",dotenv_path)
#load_dotenv(dotenv_path)

import dotenv
dotenv.load_dotenv()

#afficher les variables disponibles
#print(os.environ)

from decimal import Decimal
import re

def parse_decimal_string(value):
    if value is None:
        raise ValueError("Coordonnée vide")

    if isinstance(value, (int, float, Decimal)):
        return float(value)

    if isinstance(value, str):
        value = value.strip()

        # cas simple : "46.3103"
        try:
            return float(value)
        except ValueError:
            pass

        # cas sérialisé : "decimal.Decimal@version=1(46.3103)"
        match = re.search(r"\(([-0-9.]+)\)", value)
        if match:
            return float(match.group(1))

    raise ValueError(f"Valeur de coordonnée non reconnue : {value}")

# -------------------------
# Utils API (adapté)
# -------------------------


def meteo_header(token_user):
    token = get_valid_token(token_user)
    return {"Authorization": f"Bearer {token}"}


def get_coverage_ids(token_user):
    url = "https://public-api.meteofrance.fr/public/arpege/1.0/wcs/MF-NWP-GLOBAL-ARPEGE-025-GLOBE-WCS/GetCapabilities?service=WCS&version=2.0.1&language=fre"
    response = requests.get(url, headers=meteo_header(token_user))

    if response.status_code != 200:
        raise Exception(f"Erreur {response.status_code}. Echec de la requête récupération des coverage IDs : {response.text}")

    root = ET.fromstring(response.text)
    ns = {
        "wcs": "http://www.opengis.net/wcs/2.0",
        "ows": "http://www.opengis.net/ows/2.0",
    }

    weather_parameters = {
        "vent": "Force du vent en niveaux hauteur.",
        "rayonnement": "Flux solaire"
    }

    coverage_ids = {}

    for param, title in weather_parameters.items():
        ids = []
        for cs in root.findall(".//wcs:CoverageSummary", ns):
            t = cs.findtext("ows:Title", default="", namespaces=ns)
            if t == title:
                cov_id = cs.findtext("wcs:CoverageId", default="", namespaces=ns)
                if cov_id:
                    if param == "vent":
                        ids.append(cov_id)
                    elif param == "rayonnement" and cov_id.endswith("PT1H"):
                        ids.append(cov_id)

        coverage_ids[param] = ids[-1]

    return coverage_ids


def get_time_steps(coverage_id, token_user):
    url = f"https://public-api.meteofrance.fr/public/arpege/1.0/wcs/MF-NWP-GLOBAL-ARPEGE-025-GLOBE-WCS/DescribeCoverage?service=WCS&version=2.0.1&coverageID={coverage_id}"
    response = requests.get(url, headers=meteo_header(token_user))

    if response.status_code != 200:
        raise Exception(f"Erreur {response.status_code}. Echec de la requête récupération des times steps : {response.text}")
        
    root = ET.fromstring(response.text)

    ns = {
        "gml": "http://www.opengis.net/gml/3.2",
        "gmlrgrid": "http://www.opengis.net/gml/3.3/rgrid",
    }
    # 1) Date de début (ISO-8601)
    begin = root.findtext(".//gml:beginPosition", namespaces=ns).strip()
    t0 = datetime.fromisoformat(begin.replace("Z", "+00:00"))

    # 2) Coefficients temporels (en secondes depuis begin)
    coeff_elem = root.find(".//gmlrgrid:GeneralGridAxis[gmlrgrid:gridAxesSpanned='time']/gmlrgrid:coefficients", ns)
    coeffs = [int(v) for v in coeff_elem.text.split()]

    # 3) Générer la liste de dates ISO-8601
    dates_iso = [(t0 + timedelta(seconds=sec)).isoformat().replace("+00:00", "Z")
                for sec in coeffs]
    return dates_iso


# -------------------------
# DAG
# -------------------------

#with DAG(
#    dag_id="dag_prevision_v3",
#    start_date=pendulum.now("UTC").subtract(days=1),
#    schedule=None,
#    catchup=False,
#    tags=["predictelec"],
#) as dag:

    # -------------------------
    # 1. Users
    # -------------------------

    #@task
def get_users():
    users = []
    i = 1
    while True:
        token = os.getenv(f"METEOFRANCE_BASIC_AUTH_{i}")
        if not token:
            break
        users.append({"name": f"user_{i}", "token_user":f"METEOFRANCE_BASIC_AUTH_{i}", "token": token})
        i += 1

    if not users:
        raise ValueError("Pas de tokens")

    return users

    # -------------------------
    # 2. Stations DB
    # -------------------------

    #@task
def get_stations():
    db = Database(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )
    db.connect()

    station = Station()
    df = station.getlistStationUtile(db.conn)
    df = pd.DataFrame(df, columns=["id_station", "station_latitude", "station_longitude", "mesure_vent", "mesure_rayonnement"])
    return df.to_dict("records")

    # -------------------------
    # 3. Coverage IDs (1 seul user suffit)
    # -------------------------

    #@task
def get_cov_ids(users):
    return get_coverage_ids(users[0]["token_user"])

    # -------------------------
    # 4. Générer requêtes
    # -------------------------

    #@task
def generate_requests(stations, cov_ids, users):
    # récupérer time_steps UNE fois
    token_user=users[0]["token_user"]
    print("token_user =",token_user)
    
    time_steps = get_time_steps(cov_ids["vent"], token_user)

    requetes = []

    for s in stations:
        for date in time_steps:
            requetes.append({
                "station": s,
                "date": date
            })

    return requetes

    # -------------------------
    # 5. Split batchs
    # -------------------------

    #@task
def split_batches(requetes, users):
    n = len(users)
    batches = [[] for _ in range(n)]

    for i, r in enumerate(requetes):
        batches[i % n].append(r)

    return [
        {"user": users[i], "batch": batches[i]}
        for i in range(n)
    ]

    # ------------------------------------------
    # 6. Récupération données prévisions via API
    # ------------------------------------------

    #@task(retries=2, retry_delay=timedelta(minutes=2))
def process_batch(data_list, cov_ids):
    results = []

    for data in data_list:
        #print("type(data) =", type(data))
        #print("data =", data)

        user = data["user"]
        batch = data["batch"]
        token_user=user["token_user"]
        print("token_user =",token_user)

        headers = meteo_header(token_user)
        
        i = 0
        for req in batch:
            result_partiel=[]
            station = req["station"]
            date = req["date"]
            #mode debug : limiter à 5 requêtes
            if i >= 5:
                break
            i += 1

            #latitude = station["station_latitude"]
            #longitude = station["station_longitude"]
            latitude = parse_decimal_string(station["station_latitude"])
            longitude = parse_decimal_string(station["station_longitude"])
            avec_vent = station["mesure_vent"]
            avec_rayonnement = station["mesure_rayonnement"]
            #réinitialisation des résultats de prévision
            vitesse_vent = None
            rayonnement_solaire = None

            #exemple
            #url = f"https://public-api.meteofrance.fr/public/arpege/1.0/wcs/MF-NWP-GLOBAL-ARPEGE-025-GLOBE-WCS/GetCoverage?service=WCS&version=2.0.1&coverageid={cov_ids['vent']}&subset=time({date})&subset=lat({lat})&subset=long({lon})"


            if avec_vent == True:
                #10 mètres
                height=10
                forecast_url = f"https://public-api.meteofrance.fr/public/arpege/1.0/wcs/MF-NWP-GLOBAL-ARPEGE-025-GLOBE-WCS/GetCoverage?service=WCS&version=2.0.1&coverageid={cov_ids['vent']}&subset=time%28{date}%29%26subset%3Dheight%28{height}%29%26subset%3Dlat%28{latitude}%29%26subset%3Dlong%28{longitude}%29&format=application%2Fwmo-grib"

                r = requests.get(forecast_url, headers=headers)

                if r.status_code == 200:
                    root = ET.fromstring(r.text)
                    ns = {
                        "gml": "http://www.opengis.net/gml/3.2",
                    }
                    tuple_list = root.find(".//gml:tupleList", ns)
                    raw = tuple_list.text.strip()
                    value = float(raw)               
                    #résultat pour le vent
                    vitesse_vent = value
                    
                    print(f"Succès de récupération prévision du vent pour la station {station['id_station']} à la date {date}")
                else:
                    print(f"Echec lors de la récupération prévision du vent pour la station {station['id_station']} à la date {date}")
                    
                # 60s / 100 requêtes soit 0.6 s par requête
                time.sleep(0.6)

            if avec_rayonnement == True:
                forecast_url = f"https://public-api.meteofrance.fr/public/arpege/1.0/wcs/MF-NWP-GLOBAL-ARPEGE-025-GLOBE-WCS/GetCoverage?service=WCS&version=2.0.1&coverageid={cov_ids['rayonnement']}&subset=time%28{date}%29%26subset%3Dlat%28{latitude}%29%26subset%3Dlong%28{longitude}%29&format=application%2Fwmo-grib"

                r = requests.get(forecast_url, headers=headers)

                if r.status_code == 200:
                    root = ET.fromstring(r.text)
                    ns = {
                        "gml": "http://www.opengis.net/gml/3.2",
                    }
                    tuple_list = root.find(".//gml:tupleList", ns)
                    raw = tuple_list.text.strip()
                    value = float(raw)
                    #résultat pour le rayonnement
                    rayonnement_solaire = value
                    
                    print(f"Succès récupération prévision du rayonnement pour la station {station['id_station']} à la date {date}")
                else:
                    print(f"Echec lors de la récupération prévision du rayonnement pour la station {station['id_station']} à la date {date}")     
                
                # 60s / 100 requêtes soit 0.6 s par requête
                time.sleep(0.6)  

            #résultat global pour la station et la date    
            result_partiel.append({
                "id_station": station["id_station"],
                "forecast_time": date,
                "vitesse_vent": vitesse_vent,
                "rayonnement_solaire": rayonnement_solaire
            })   

            #sauvegarde unitaire dans la DB pour éviter de tout perdre en cas d'erreur
            save_unitaire(result_partiel)
            results.extend(result_partiel)       

    return f"Nombres de prévisions récupérées et sauvegardées : {len(results)}"


    # -------------------------
    # 7. Save DB
    # -------------------------

    #@task
def save_all(results_list):
    db = Database(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )
    db.connect()

    all_results = []
    for r in results_list:
        all_results.extend(r)

    meteo = Meteo()
    meteo.save_forecast(all_results, db.conn)

def save_unitaire(results):
    db = Database(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )
    db.connect()

    meteo = Meteo()
    meteo.save_forecast_partiels(results, db.conn)    

#@task
def archivage_historique():
    db = Database(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )
    db.connect()

    meteo = Meteo()
    meteo.archive_forecast_historique(db.conn)

if __name__ == "__main__":
    # -------------------------
    # PIPELINE
    # -------------------------

    users = get_users()

    stations = get_stations()

    cov_ids = get_cov_ids(users)

    requetes = generate_requests(stations, cov_ids, users)

    batches = split_batches(requetes, users)

#dans le dag on fait process_batch.expand(data_list=batches, cov_ids=cov_ids)
    results = process_batch(data_list=batches, cov_ids=cov_ids)

    #save_all(results)
    archivage_historique()