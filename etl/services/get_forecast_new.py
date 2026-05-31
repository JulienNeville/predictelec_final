from api.api_meteo import get_valid_token
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import os
from db.base import Database
import pandas as pd
import time
from datetime import date, datetime
from pathlib import Path
from models.meteo import Meteo
from models.station import Station
from dotenv import load_dotenv
import logging

load_dotenv(dotenv_path=".env.local")

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)

def meteo_header():
    '''
    Récupère un token d'authentification valide pour l'API Météo France et retourne les headers à utiliser pour les requêtes.
    '''
    TOKEN = get_valid_token()
    if not TOKEN:
        raise ValueError("Pas de TOKEN METEO_FRANCE valide généré.")
    HEADERS = {"Authorization": f"Bearer {TOKEN}"}
    return HEADERS

def merge_dfs(forecast_vent, forecast_rayonnement):
    rows = []
    for id_station, times in forecast_vent.items():
        for forecast_time, vals in times.items():
            rows.append({
                "id_station": id_station,
                "forecast_time": forecast_time,
                "coverage_id_vitesse_vent": vals.get("coverage_id_vitesse_vent"),
                "vitesse_vent": vals.get("vitesse_vent"),
                "coverage_id_rayonnement_solaire": None,
                "rayonnement_solaire": None,
            })

    if forecast_rayonnement is not None:
        for id_station, times in forecast_rayonnement.items():
            for forecast_time, vals in times.items():
                match = next(
                    (r for r in rows
                    if r["id_station"] == id_station and r["forecast_time"] == forecast_time),
                    None,
                )
                if match is not None:
                    match["coverage_id_rayonnement_solaire"] = vals.get("coverage_id_rayonnement_solaire")
                    match["rayonnement_solaire"] = vals.get("rayonnement_solaire")
                else:
                    rows.append({
                        "id_station": id_station,
                        "forecast_time": forecast_time,
                        "coverage_id_vitesse_vent": vals.get("coverage_id_vitesse_vent"),
                        "vitesse_vent": vals.get("vitesse_vent"),
                        "coverage_id_rayonnement_solaire": vals.get("coverage_id_rayonnement_solaire"),
                        "rayonnement_solaire": vals.get("rayonnement_solaire"),
                    })
    df = pd.DataFrame(rows)
    return df

def get_coverage_ids(weather_parameters):
    '''
    Récupère les coverage IDs pour les paramètres de vent et de rayonnement solaire à partir de l'API GetCapabilities de Météo France.
    '''
    capabilities_url = "https://public-api.meteofrance.fr/public/arpege/1.0/wcs/MF-NWP-GLOBAL-ARPEGE-025-GLOBE-WCS/GetCapabilities?service=WCS&version=2.0.1&language=fre"
    response = requests.get(capabilities_url,headers=meteo_header())
    if response.status_code == 200:
        root = ET.fromstring(response.text)
        ns = {
            "wcs": "http://www.opengis.net/wcs/2.0",
            "ows": "http://www.opengis.net/ows/2.0",
            }
        coverage_ids = {}
        # récupérer tous les CoverageSummary avec ce Title
        for param, title in weather_parameters.items():
            ids = []
            for cs in root.findall(".//wcs:CoverageSummary", ns):
                title = cs.findtext("ows:Title", default="", namespaces=ns)
                if title == weather_parameters[param]:
                    cov_id = cs.findtext("wcs:CoverageId", default="", namespaces=ns)
                    if cov_id:
                        if param == "vent":
                            ids.append(cov_id)
                        elif param == "rayonnement" and cov_id.endswith("PT1H"):
                            ids.append(cov_id)
            if len(ids) > 0:
                last_id = ids[-1]   # dernier dans l'ordre du XML
                coverage_ids[param] = last_id
            else:
                print(f"Aucun CoverageId trouvé pour le paramètre de titre'{param}'")
                return None
        return coverage_ids
    else:
        msg = f"Erreur {response.status_code}. Echec de la requête récupération des coverage IDs : {response.text}"
        print(msg)
        logger.error(msg)
        return None

def get_time_steps(coverage_id,day):
    '''
    Récupère les pas de temps disponibles pour un coverage ID donné à partir de l'API DescribeCoverage de Météo France.
    '''
    describe_coverage_url = f"https://public-api.meteofrance.fr/public/arpege/1.0/wcs/MF-NWP-GLOBAL-ARPEGE-025-GLOBE-WCS/DescribeCoverage?service=WCS&version=2.0.1&coverageID={coverage_id}"

    response = requests.get(describe_coverage_url, headers=meteo_header())
    if response.status_code == 200:
        root = ET.fromstring(response.text)
        ns = {
            "gml": "http://www.opengis.net/gml/3.2",
            "gmlrgrid": "http://www.opengis.net/gml/3.3/rgrid",
        }
        # 1) Date de début (ISO-8601)
        begin_text = root.findtext(".//gml:beginPosition", namespaces=ns).strip()
        t0 = datetime.fromisoformat(begin_text.replace("Z", "+00:00"))

        # 2) Coefficients temporels (en secondes depuis begin)
        coeff_elem = root.find(".//gmlrgrid:GeneralGridAxis[gmlrgrid:gridAxesSpanned='time']/gmlrgrid:coefficients", ns)
        coeffs = [int(v) for v in coeff_elem.text.split()]

        # 3) Générer la liste de dates ISO-8601
        dates_iso = [(t0 + timedelta(seconds=sec)).isoformat().replace("+00:00", "Z")
                    for sec in coeffs]
        j_plus_1_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        j_plus_2_str = (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")
        j_plus_3_str = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
        j_plus_4_str = (date.today() + timedelta(days=4)).strftime("%Y-%m-%d")
        match day:
            case "J+1":
                dates_iso = [d for d in dates_iso if d.startswith(j_plus_1_str)]
            case "J+2":
                dates_iso = [d for d in dates_iso if d.startswith(j_plus_2_str)]
            case "J+3":
                dates_iso = [d for d in dates_iso if d.startswith(j_plus_3_str)]
            case "J+4":
                dates_iso = [d for d in dates_iso if d.startswith(j_plus_4_str)]
        return dates_iso
    else:
        print(f"Failed to retrieve time steps for {coverage_id}")
        return None

def get_forecast_parameter(coverage_ids,parameter,df,J_plus_i):
    '''    Récupère les prévisions pour un paramètre donné (vent ou rayonnement solaire) à partir de l'API GetCoverage de Météo France pour chaque station météo associée à une centrale et les enregistre en base de données.
    '''
    time_steps = get_time_steps(coverage_ids[parameter],J_plus_i)
    if time_steps:
        j=0
        i = 0
        stations_dict = {}
        for index, row in df.iterrows():
            if j < 1:
                date_dict = {}
                for date in time_steps:
                    parameter_dict = {}
                    i+=1
                    if i >=98:
                        time.sleep(60) #attente pour ne pas sursolliciter le serveur : limite de 100 requêtes par minute
                        i=0
                    latitude = row["station_latitude"]
                    longitude = row["station_longitude"]
                    if parameter == "vent":
                        height = "10"
                        forecast_url = f"https://public-api.meteofrance.fr/public/arpege/1.0/wcs/MF-NWP-GLOBAL-ARPEGE-025-GLOBE-WCS/GetCoverage?service=WCS&version=2.0.1&coverageid={coverage_ids['vent']}&subset=time%28{date}%29%26subset%3Dheight%28{height}%29%26subset%3Dlat%28{latitude}%29%26subset%3Dlong%28{longitude}%29&format=application%2Fwmo-grib"
                    elif parameter == "rayonnement":
                        forecast_url = f"https://public-api.meteofrance.fr/public/arpege/1.0/wcs/MF-NWP-GLOBAL-ARPEGE-025-GLOBE-WCS/GetCoverage?service=WCS&version=2.0.1&coverageid={coverage_ids['rayonnement']}&subset=time%28{date}%29%26subset%3Dlat%28{latitude}%29%26subset%3Dlong%28{longitude}%29&format=application%2Fwmo-grib"

                    response = requests.get(forecast_url, headers=meteo_header())
                    if response.status_code == 200:
                        root = ET.fromstring(response.text)
                        ns = {
                            "gml": "http://www.opengis.net/gml/3.2",
                        }
                        tuple_list = root.find(".//gml:tupleList", ns)
                        raw = tuple_list.text.strip()
                        value = float(raw)
                        if parameter == "vent":
                            parameter_dict["coverage_id_vitesse_vent"] = coverage_ids['vent']
                            parameter_dict["vitesse_vent"] = value
                        elif parameter == "rayonnement":
                            parameter_dict["coverage_id_rayonnement_solaire"] = coverage_ids['rayonnement']
                            parameter_dict["rayonnement_solaire"] = value
                        print(f"Successfully retrieved {parameter} forecast for station {row['id_station']} at {date}")
                    else:
                        print(f"Failed to retrieve {parameter} forecast for station {row['id_station']} at {date}")
                    date_dict[date] = parameter_dict
                stations_dict[row["id_station"]] = date_dict
            j+=1
        return stations_dict
    else:
        print(f"Time steps for {parameter} is empty.")
        return None

def update_forecast_days(conn, weather_parameters, J_plus_i):
    station = Station()
    df_stations = station.getlistStationUtile(conn)
    df_vent = df_stations[df_stations["mesure_vent"] == True].copy()
    df_rayonnement = df_stations[df_stations["mesure_rayonnement"] == True].copy()
    coverage_ids = get_coverage_ids(weather_parameters)
    if coverage_ids:
        logger.debug(f"Coverage IDs retenus pour {J_plus_i} : {coverage_ids}")
        pd.set_option("display.max_columns", None)
        forecast_vent = get_forecast_parameter(coverage_ids,"vent",df_vent,J_plus_i)
        forecast_rayonnement = get_forecast_parameter(coverage_ids,"rayonnement",df_rayonnement,J_plus_i)
        df_forecast = merge_dfs(forecast_vent, forecast_rayonnement)
        meteo = Meteo()
        meteo.save_forecast(df_forecast,conn)
    else:
        msg = f"Impossible de récupérer les coverage IDs pour les paramètres météorologiques. Abandon de la mise à jour des prévisions pour le jour {J_plus_i}."
        print(msg)
        logger.error(msg)
        raise ValueError(msg)

def update_forecast_db():
    """
    Met à jour la base de données en:
    - supprimant les prévisions du jour (anciennes J+1);
    - ajoutant les prévisions à J+5 (nouvelles J+4);
    - mettant à jour les prévisions à J+2 (nouvelles J+1),
      J+3 (nouvelles J+2) et J+4 (nouvelles J+3).
    """
    logger.info(
            f"--- Mise à jour des prévisions météorologiques le "
            f"{datetime.now().isoformat()} ---\n"
        )

    db = Database(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT"),
    )
    db.connect()
    meteo = Meteo()

    weather_parameters = {
        "vent": "Force du vent en niveaux hauteur.",
        "rayonnement": "Flux solaire",
    }

    logger.info("Suppression des prévisions du jour")
    today_str = date.today().strftime("%Y-%m-%d")
    i_success = meteo.delete_forecast(db.conn,today_str)
    if i_success:
        logger.info("Prévisions du jour supprimées avec succès")
    else:
        logger.error("Erreur lors de la suppression des prévisions du jour")

    horizons = ["J+1", "J+2", "J+3", "J+4"]

    for h in horizons:
        try:
            logger.info(f"Rafraîchissement des prévisions {h}")
            update_forecast_days(db.conn, weather_parameters, h)
        except Exception as e:
            msg = f"Erreur lors de la récupération des prévisions {h} : {e}"
            logger.error(msg)