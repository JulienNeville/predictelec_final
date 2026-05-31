
# Ajouter le répertoire parent au chemin Python
#import sys
#from pathlib import Path
#sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import os
import time
import requests
import pandas as pd
from models.meteo import Meteo
from models.station import Station
from db.base import Database
import dotenv
from api.api_meteo import get_valid_token, get_valid_token_debugwindows
from datetime import datetime, timedelta, timezone
from db.sql_utils import log_import

dotenv.load_dotenv()

def paramHeaders(action):
    content_type=""
    if action == "Commande":
        content_type = """content-type": "json"""

    if os.getenv('MODE') == "PROD":
        HEADERS = {"Authorization": f"Bearer {get_valid_token()}, {content_type}"}

    if os.getenv('MODE') == "DEV":
        # pour appel curl sous windows
        HEADERS = {"Authorization": f"Bearer {get_valid_token_debugwindows()} , {content_type}"}

    return HEADERS

# Normalisation des dates pour l'API
def normalize_date_for_api(date_in):
    if isinstance(date_in, str):
        try:
            dt = datetime.fromisoformat(date_in.replace("Z", ""))
        except ValueError:
            dt = datetime.strptime(date_in, "%Y-%m-%d")
    elif isinstance(date_in, datetime):
        dt = date_in
    else:
        raise ValueError("Format de date non supporté")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# Générateur de plages périodiques d'une journée pour pagination
def iter_days(start_dt, end_dt, step_days=1):
    current = start_dt
    while current < end_dt:
        day_start = current.replace(hour=0, minute=0, second=0)
        day_end = day_start + timedelta(days=step_days) 
        yield day_start, min(day_end, end_dt)
        current += timedelta(days=step_days)

# Calcul de la plage du mois précédent
def get_previous_month_range(date_ref=None):
    if date_ref is None:
        date_ref = datetime.now(timezone.utc)
    else:
        date_ref = datetime.fromisoformat(date_ref.replace("Z", "")).replace(tzinfo=timezone.utc) + pd.DateOffset(months=1)
    today = date_ref 
    # premier jour du mois courant
    first_day_current_month = today.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    # premier jour du mois précédent
    first_day_prev_month = first_day_current_month - pd.DateOffset(months=1)

    # premier jour du mois suivant = premier jour du mois courant + 1 mois
    last_day_prev_month = first_day_prev_month + pd.DateOffset(months=1)

    return first_day_prev_month, last_day_prev_month

# Sauvegarde des données dans la base
def save_data(df_stations):
    meteo = Meteo()
    db = Database(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),        
        port=os.getenv('DB_PORT')
    )
    try:
        db.connect()
        isaved = meteo.save_lot(df_stations, db.conn)
        if isaved:  
            print(f"Sauvegarde réussie de {df_stations.shape[0]} enregistrements de météo.")
        else:
            print("Erreur lors de la sauvegarde des données de météo.")
    except Exception as e:
        print(f"Erreur lors de la connexion à la base de données : {e}")
    finally:
        db.close()   

    return df_stations

def get_commande_meteo(station,debut,fin,conn):
    """
    Docstring pour get_commande_meteo
    """
    # Exemple de paramètres
    #id_station = "28380003"  # Exemple : SOURS_SAPC
    #debut = "2025-10-01T00:00:00Z"
    #fin = "2025-10-02T11:00:00Z"

    TOKEN = get_valid_token()
    if not TOKEN:
        raise ValueError("Pas de TOKEN METEO_FRANCE valide généré.")
    

    # normalisation dates entrée
    start_dt = datetime.fromisoformat(
        normalize_date_for_api(debut).replace("Z", "")
    )
    end_dt = datetime.fromisoformat(
        normalize_date_for_api(fin).replace("Z", "")
    )

    df_stations_data = pd.DataFrame()
    
    try:
        # pagination par blocs de 30 jours pour éviter les erreurs de période trop longue
        for day_start, day_end in iter_days(start_dt, end_dt, step_days=30):
            print(f"Traitement de la période du {day_start} au {day_end}...")
            debut_api = normalize_date_for_api(day_start)
            fin_api = normalize_date_for_api(day_end)
            print(f"Station {station} | {debut_api} → {fin_api}")
            
            # 1- récupère la commande horaire
            #BASE_URL_CMD =f"https://public-api.meteofrance.fr/public/DPClim/v1/commande-station/infrahoraire-6m?id-station={station}&date-deb-periode={debut_api}&date-fin-periode={fin_api}"
            BASE_URL_CMD =f"https://public-api.meteofrance.fr/public/DPClim/v1/commande-station/horaire?id-station={station}&date-deb-periode={debut_api}&date-fin-periode={fin_api}"
            HEADERS = paramHeaders("Demande")
            response = requests.get(BASE_URL_CMD, headers=HEADERS)
            response.raise_for_status()
            data_cmd = response.json()
            print("la commande est :",data_cmd['elaboreProduitAvecDemandeResponse']['return'])
            commande=data_cmd['elaboreProduitAvecDemandeResponse']['return']
            
            #Il est utile d'attendre plusieurs secondes avant de solliciter le web 
            time.sleep(3) #attente de 3 secondes

            # 2- récupère les données météo associées à la commande
            url=f"https://public-api.meteofrance.fr/public/DPClim/v1/commande/fichier?id-cmde={commande}"
            HEADERS = paramHeaders("Commande")
            # boucle tant que le status code est 204 (préparation en cours)
            status_code=204
            while status_code==204:
                response = requests.get(url, headers=HEADERS)
                status_code=response.status_code
                if status_code==204:
                    print("Préparation toujours en cours. Nouvelle tentative ...")
                    time.sleep(3) #attente de 3 secondes avant nouvelle tentative

            # statut ko
            if status_code!=200 and status_code!=201:
                print(f"Erreur lors de la récupération des données météo : status code {status_code}")
                log_import("METEO", station, day_start, "WARNING", "CLIM",f"status_code={status_code}",conn)
            
            #retour format csv    
            data_text=response.content.decode('utf-8')
            df_data = pd.read_csv(io.StringIO(data_text), sep=";")
            
            df_stations_data = pd.concat([df_stations_data, df_data], ignore_index=True)
            #print(df_data.head()  )
            #for col in df_data.columns:
            #    print(col)

            # 3 - sélection + renommage
            df_select = df_stations_data[["POSTE", "DATE", "FF", "GLO"]].copy()
            df_select["DATE"] = pd.to_datetime(
                df_select["DATE"], format="%Y%m%d%H%M"
            )

            df_select.rename(
                columns={
                    "POSTE": "id_station",
                    "DATE": "validity_time",
                    "FF": "vitesse_vent",
                    "GLO": "rayonnement_solaire"
                },
                inplace=True
            )

            # 4 - NaN → NULL (pour intégration Postgres)
            df_select = df_select.where(pd.notnull(df_select), None)
            
            # 5 - décimal "," en "."
            cols_numeric = ["vitesse_vent","rayonnement_solaire"]
            for col in cols_numeric:
                if col in df_select.columns:
                    df_select[col] = (
                        df_select[col]
                        .astype(str)
                        .str.replace(",", ".", regex=False)
                    )
                    df_select[col] = pd.to_numeric(
                        df_select[col],
                        errors="coerce"
                    )

            save_data(df_select)

            # 5 log succès
            log_import("METEO", station, day_start, "SUCCESS", "CLIM", None,conn)
    except Exception as e:
        print(f"Erreur lors de la requête : {e}")
        log_import("METEO", station, day_start, "ERROR", "CLIM", str(e),conn)
    finally:
        print("Processus de récupération et de sauvegarde des données météo terminé.")


def import_meteo_previous_month(date_ref=None):
    debut, fin = get_previous_month_range(date_ref=date_ref)
    if date_ref==None:
        #jusqu'à la veille
        today = datetime.now(timezone.utc)            
        fin = today.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

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
        stations = station.getlistStationUtile(db.conn)
        liste_stations = stations['id_station']
        for station in liste_stations:
            station_str = str(station)
            if len(station_str)<8:
                station_str = station_str.zfill(8)
            print(
                f"Import météo – station {station} | "
                f"{debut.strftime('%Y-%m-%d')} → {fin.strftime('%Y-%m-%d')}"
            )
            get_commande_meteo(
                                station=station_str,
                                debut=debut,
                                fin=fin,
                                conn=db.conn
            )
            print(f"Import météo pour la station {station} terminé.")
    except Exception as e:
        print(f"Erreur lors de la connexion à la base de données : {e}")
    finally:        
        db.close()

def get_save_meteo_hier():

    """
    Récupère toutes les données meteo entre deux dates en paginant par blocs de 100.
    - debut_date et fin_date au format 'YYYY-MM-DD'
    - region (optionnel) : ex 'Auvergne-Rhône-Alpes'
    
    Retourne une liste de dicts (enregistrements).
    """
    df_stations_data = pd.DataFrame()
    df_stations_data_select = pd.DataFrame()
    db = Database(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),        
        port=os.getenv('DB_PORT')
    )
    station = Station()

    TOKEN = get_valid_token()
    if not TOKEN:
        raise ValueError("Pas de TOKEN METEO_FRANCE valide généré.")
    HEADERS = {"Authorization": f"Bearer {TOKEN}"}

    try:
        db.connect()
        stations = station.getlistStation(db.conn)
        liste_stations = stations['id_station']
        print(len(liste_stations), "stations météo à traiter.")
        twentyth = len(liste_stations) // 20
        liste_stations1 = liste_stations[:twentyth]
        liste_stations2 = liste_stations[twentyth:2*twentyth]
        liste_stations3 = liste_stations[2*twentyth:3*twentyth]
        liste_stations4 = liste_stations[3*twentyth:4*twentyth]
        liste_stations5 = liste_stations[4*twentyth:5*twentyth]
        liste_stations6 = liste_stations[5*twentyth:6*twentyth]
        liste_stations7 = liste_stations[6*twentyth:7*twentyth]
        liste_stations8 = liste_stations[7*twentyth:8*twentyth]
        liste_stations9 = liste_stations[8*twentyth:9*twentyth]
        liste_stations10 = liste_stations[9*twentyth:10*twentyth]
        liste_stations11 = liste_stations[10*twentyth:11*twentyth]
        liste_stations12 = liste_stations[11*twentyth:12*twentyth]
        liste_stations13 = liste_stations[12*twentyth:13*twentyth]
        liste_stations14 = liste_stations[13*twentyth:14*twentyth]
        liste_stations15 = liste_stations[14*twentyth:15*twentyth]
        liste_stations16 = liste_stations[15*twentyth:16*twentyth]
        liste_stations17 = liste_stations[16*twentyth:17*twentyth]
        liste_stations18 = liste_stations[17*twentyth:18*twentyth]
        liste_stations19 = liste_stations[18*twentyth:19*twentyth]
        liste_stations20 = liste_stations[19*twentyth:]
        liste_listes_stations = [liste_stations1, liste_stations2, liste_stations3, liste_stations4, liste_stations5, liste_stations6, liste_stations7, liste_stations8, liste_stations9, liste_stations10, liste_stations11, liste_stations12, liste_stations13, liste_stations14, liste_stations15, liste_stations16, liste_stations17, liste_stations18, liste_stations19, liste_stations20]
        for liste_stations in liste_listes_stations:
            for station in liste_stations:
                station_str = str(station)
                if len(station_str)<8:
                    station_str = station_str.zfill(8)
                #BASE_URL = f"https://public-api.meteofrance.fr/public/DPPaquetObs/v1/paquet/infrahoraire-6m?id_station={station_str}&format=json"
                BASE_URL = f"https://public-api.meteofrance.fr/public/DPPaquetObs/v1/paquet/infrahoraire-6m?date=2024-05-06T18:00:00Z&id_station={station_str}&format=json"
                response = requests.get(BASE_URL, headers=HEADERS)
                response.raise_for_status()
                data = response.json()
                df_data = pd.json_normalize(data)
                df_stations_data = pd.concat([df_stations_data, df_data], ignore_index=True)
                print(f"Station n° {station} traitée.")
            time.sleep(30)
        df_stations_data_select = df_stations_data[["geo_id_insee","validity_time","ff","ray_glo01"]].copy()
        df_stations_data_select.rename(columns={"geo_id_insee" : "id_station","validity_time" : "validity_time","ff":"vitesse_vent","ray_glo01":"rayonnement_solaire"},inplace=True)
       
    except Exception as e:
        print(f"Erreur lors de la connexion à la base de données : {e}")

    finally:
        save_data(df_stations_data_select)

if __name__ == "__main__":
    pass
    ##test sur la journée d'hier
    #all_data=get_save_meteo_hier()

    #all_data=get_commande_meteo()
    #print(f"Nombre total d'enregistrements récupérés : {len(all_data)}")
    #print(all_data[:5])  # aperçu des 5 premiers