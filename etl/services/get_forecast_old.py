# Enregistrer en base de données les prévisions de vitesse de vent et d'ensoleillement à partir de la date du jour aux points correspondants à chaque station météo associée à une centrale.
# 1. Récupérer avec API GetCapabilities le dernier coverageid disponible pour les paramètres WIND_SPEED__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND et DOWNWARD_SHORT_WAVE_RADIATION_FLUX__GROUND_OR_WATER_SURFACE
# 2. Récupérer avec l'API DescribeCoverage la date de début et les pas de temps disponibles pour chaque paramètre
# 3. Récupérer les lat et lon de chaque station météo associée à une centrale
# 4. Récupérer avec l'API GetCoverage les prévisions de vitesse de vent et d'ensoleillement à partir de la date du jour aux points correspondants à chaque station météo associée à une centrale.

from api.api_meteo import get_valid_token,get_valid_token_debugwindows
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import dotenv
import io
import os
from db.base import Database
import pandas as pd
import time
from models.meteo import Meteo
from models.station import Station

dotenv.load_dotenv()

def meteo_header():
    '''
    Récupère un token d'authentification valide pour l'API Météo France et retourne les headers à utiliser pour les requêtes.
    '''
    if os.getenv('MODE') == "PROD":
        TOKEN = get_valid_token()
    if os.getenv('MODE') == "DEV":
        TOKEN = get_valid_token_debugwindows()        
    if not TOKEN:
        raise ValueError("Pas de TOKEN METEO_FRANCE valide généré.")
    HEADERS = {"Authorization": f"Bearer {TOKEN}"}
    return HEADERS

def maj_prevision():
    '''
    Récupère les prévisions météorologiques pour les stations météo associées à une centrale et les enregistre en base de données.
    '''
    coverage_ids = get_coverage_ids()
    print("coverage_ids:", coverage_ids)
    get_forecast_stations(coverage_ids,height=10)

def get_coverage_ids():
    '''
    Récupère les coverage IDs pour les paramètres de vent et de rayonnement solaire à partir de l'API GetCapabilities de Météo France.
    '''
    weather_parameters = {"vent": "Force du vent en niveaux hauteur.",
                          "rayonnement": "Flux solaire"}
    capabilities_url = "https://public-api.meteofrance.fr/public/arpege/1.0/wcs/MF-NWP-GLOBAL-ARPEGE-025-GLOBE-WCS/GetCapabilities?service=WCS&version=2.0.1&language=fre"
    #print("meteo_header():",meteo_header())
    response = requests.get(capabilities_url,headers=meteo_header())

    if response.status_code != 200:
        print(f"Failed to retrieve capabilities: {response.status_code},response: {response.text}")
        return None    
    if response.status_code == 200:
        #debug : sauvegarder la réponse XML dans un fichier pour l'inspecter
        #with open("capabilities.xml", "w", encoding="utf-8") as f:
        #    f.write(response.text)
        #test avec read_xml pour extraire les CoverageSummary et leurs CoverageId
        #df=pd.read_xml(io.StringIO(response.text), xpath=".//wcs:CoverageSummary", namespaces={"wcs": "http://www.opengis.net/wcs/2.0", "ows": "http://www.opengis.net/ows/2.0"})
        #df2=pd.read_xml(io.StringIO(response.text))
        #print(df.head())
        #print(df.columns.tolist())
        #print(df2.head())
        #print(df2.columns.tolist())
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
            if ids:
                last_id = ids[-1]   # dernier dans l'ordre du XML
                coverage_ids[param] = last_id
            else:
                print(f"Aucun CoverageId trouvé pour le paramètre de titre'{param}'")
        return coverage_ids
    else:
        print(response.status_code)
        return None

def get_time_steps(coverage_id):
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
        return dates_iso
    else:
        print(f"Failed to retrieve time steps for {coverage_id}")
        return None

def get_forecast_parameter(coverage_ids,parameter,df,height):
    '''    Récupère les prévisions pour un paramètre donné (vent ou rayonnement solaire) à partir de l'API GetCoverage de Météo France pour chaque station météo associée à une centrale et les enregistre en base de données.
    '''
    time_steps = get_time_steps(coverage_ids[parameter])
    i = 0
    j=0
    stations_dict = {}
    for index, row in df.iterrows():
        # limiter à 2 stations pour les tests pour ne pas faire trop de requêtes à l'API Météo France
        if j<2:
            date_dict = {}
            for date in time_steps:
                parameter_dict = {}
                i+=1
                if i >=100:
                    print("Attente de 60 secondes pour respecter la limite de 100 requêtes par minute de l'API Météo France...")
                    time.sleep(60) #attente pour ne pas sursolliciter le serveur : limite de 100 requêtes par minute
                    i=0
                latitude = row["station_latitude"]
                longitude = row["station_longitude"]
                if parameter == "vent":
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
                        parameter_dict["vitesse_vent"] = value
                    elif parameter == "rayonnement":
                        parameter_dict["rayonnement_solaire"] = value
                    print(f"Successfully retrieved forecast for station {row['id_station']} at {date}")
                else:
                    print(f"Failed to retrieve forecast for station {row['id_station']} at {date}")
                date_dict[date] = parameter_dict
            stations_dict[row["id_station"]] = date_dict
            if os.getenv('MODE') == "DEV":
                #uniquement pour les tests : limiter à 2 stations pour ne pas faire trop de requêtes à l'API Météo France
                j+=1
    return stations_dict

def convert_to_df(forecast_vent, forecast_rayonnement):
    rows = []
    for id_station, times in forecast_vent.items():
        for forecast_time, vals in times.items():
            rows.append({
                "id_station": id_station,
                "forecast_time": forecast_time,
                "vitesse_vent": vals.get("vitesse_vent"),
                "rayonnement_solaire": None,  # rempli après
            })

    for id_station, times in forecast_rayonnement.items():
        for forecast_time, vals in times.items():
            # chercher si on a déjà une ligne pour (station_id, forecast_time)
            match = next(
                (r for r in rows
                if r["id_station"] == id_station and r["forecast_time"] == forecast_time),
                None,
            )
            if match is not None:
                match["rayonnement_solaire"] = vals.get("rayonnement_solaire")
            else:
                rows.append({
                    "id_station": id_station,
                    "forecast_time": forecast_time,
                    "vitesse_vent": None,
                    "rayonnement_solaire": vals.get("rayonnement_solaire"),
                })
    df = pd.DataFrame(rows)
    # df["forecast_time"] = pd.to_datetime(df["forecast_time"])
    return df

def get_forecast_stations(coverage_ids,height):
    '''
    Récupère les prévisions de vent et de rayonnement solaire pour les stations météo associées à une centrale et les enregistre en base de données.
    
    :param coverage_ids: coverage IDs pour les paramètres de vent et de rayonnement solaire
    :param height: hauteur pour laquelle récupérer les prévisions de vent (en mètres) - ignoré pour le rayonnement solaire
    '''
    db = Database(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),        
        port=os.getenv('DB_PORT')
    )
    station = Station()
    try:
        db.connect()
        df = station.getlistStationUtile(db.conn)
        #query = "select sc.id_station, s.station_latitude, s.station_longitude, s.mesure_vent, s.mesure_rayonnement from stations_centrales AS sc JOIN stations AS s ON sc.id_station = s.id_station"
        #results = db.fetch_all(query)
        #df = pd.DataFrame(results, columns=["id_station", "station_latitude", "station_longitude", "mesure_vent", "mesure_rayonnement"])
        df_vent = df[df["mesure_vent"] == True].copy()
        df_rayonnement = df[df["mesure_rayonnement"] == True].copy()
        forecast_vent = get_forecast_parameter(coverage_ids,"vent",df_vent,height)
        forecast_rayonnement = get_forecast_parameter(coverage_ids,"rayonnement",df_rayonnement,height)
        df_forecast = convert_to_df(forecast_vent, forecast_rayonnement)
        meteo = Meteo()
        meteo.save_forecast(df_forecast,db.conn)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return
    
    