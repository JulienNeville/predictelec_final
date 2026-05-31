#import sys
#from pathlib import Path
# Ajouter le répertoire parent au chemin Python
#sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import requests
import numpy as np
import os
import time
import dotenv #pip install python-dotenv
from models.territoire import Territoire
from models.station import Station
from db.base import Database
from api.api_meteo import get_valid_token
from api.api_meteo import get_valid_token_debugwindows

dotenv.load_dotenv()

#TOKEN = os.getenv('TOKEN_METEO_FRANCE')
#if not TOKEN:
#    raise ValueError("TOKEN_METEO_FRANCE non trouvé dans le fichier .env")


#HEADERS = {"Authorization": f"Bearer {get_valid_token()}"}
if os.getenv('MODE') == "PROD":
    print("Mode de fonctionnement : PROD - AVEC DOCKER")
    HEADERS = {"Authorization": f"Bearer {get_valid_token()}"}

if os.getenv('MODE') == "DEV":
    # pour appel curl sous windows
    print("Mode de fonctionnement : DEV - SANS DOCKER")
    HEADERS = {"Authorization": f"Bearer {get_valid_token_debugwindows()}"}

# --- check_station_eligibility : filtre les stations éligibles ---
def get_save_stations_eligibles():
    """
    Enregistre les stations météo éligibles pour les mesures de vent et/ou de rayonnement.
    Retourne un DataFrame des stations éligibles.
    """
    db = Database(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),        
        port=os.getenv('DB_PORT')
    )
  
    output_dict = {
        "total_count": 0,
        "total_inserted": 0,
        "total_errors": 0,
        "message": ""
        }

    try:
        db.connect()        
        df_stations_data = pd.DataFrame()
        
        liste_regions=Territoire.liste_regions(db.conn)
        for region in liste_regions:
            print(f"Récupération des données des stations météo pour la région {region}...")
            liste_dpt=Territoire.liste_departements(region,db.conn)
            for dpt in liste_dpt:
                url=f"https://public-api.meteofrance.fr/public/DPPaquetObs/v1/paquet/horaire?id-departement={dpt}&format=json"
                #print("url meteofrance :", url)
                #print("headers :", HEADERS)
                r = requests.get(url, headers=HEADERS)
                r.raise_for_status()
                data = r.json()
                if (not pd.json_normalize(data).empty):
                    df_stations_data = pd.concat([df_stations_data, pd.json_normalize(data)], ignore_index=True)
                #print("Colonnes disponibles :", df_stations_data.columns.tolist())
                #print("Nombre total lignes :", df_stations_data.shape[0])
                print(f"Données des stations du département {dpt} récupérées.")
                time.sleep(1) #attente de 1  seconde pour ne pas sursolliciter le serveur : limite de 50 requêtes par minute
                

        df_stations_data.rename(columns={"geo_id_insee":"id_station","lat": "station_latitude","lon": "station_longitude"}, inplace=True)
        Total_count = df_stations_data.shape[0]
        # on supprime les colonnes inutiles, on ne garde qu'un enregistrement par station et on supprime les stations qui n'ont pas de coordonnées geographiques ou ni mesure de vent ni mesure de rayonnement
        #df_stations_eligibles = df_stations_data[["id_station","station_latitude","station_longitude","ff","ray_glo01"]].copy()
        required_cols = ["id_station","station_latitude","station_longitude","ff","ray_glo01"]
        missing_cols = [col for col in required_cols if col not in df_stations_data.columns]
        if missing_cols:
            raise ValueError(f"Colonnes manquantes dans les données API : {missing_cols}")
        df_stations_eligibles = df_stations_data[required_cols].copy()
        df_stations_eligibles.drop_duplicates(subset=["id_station"],keep='first',inplace=True)
        df_stations_eligibles.dropna(subset=["ff","ray_glo01"],how='all',inplace=True)
        df_stations_eligibles["mesure_vent"] = np.where(df_stations_eligibles["ff"].notna(), True, False)
        df_stations_eligibles["mesure_rayonnement"] = np.where(df_stations_eligibles["ray_glo01"].notna(), True, False)
        df_stations_eligibles.drop(columns=["ff","ray_glo01"],inplace=True)
        df_stations_eligibles.dropna(subset=["station_latitude","station_longitude"],how='any',inplace=True)
        
        if df_stations_eligibles.empty:
            raise ValueError("Aucune station éligible. Vérifier le fichier des stations.")
        else:
            print(f"Il existe {len(df_stations_eligibles['id_station'].unique().tolist())} stations éligibles sur toute la France continentale.")

        ## remplacer les NaN par des null avant d'enregistrer le fichier en json
        #df_stations_eligibles_clean_dict = df_stations_eligibles.replace(np.nan, None).to_dict(orient="records")
        #station_count = df_stations_eligibles_clean_dict.__len__()
        station_count = df_stations_eligibles.shape[0]
        error_count = 0
        # on sauvegarde les données des stations éligibles en base
        station = Station()
        result = station.save_lot(df_stations_eligibles, db.conn)

        if not result:
            error_count = station_count 
            station_count = 0
          

        output_dict["total_count"] += Total_count
        output_dict["total_inserted"] += station_count
        output_dict["total_errors"] += error_count

    
    except requests.exceptions.RequestException as e:
        output_dict["message"] = f"Erreur requête API (vérifier le Token): {e}"
    
    finally:
        db.close()
        return output_dict

if __name__ == "__main__":
    result=get_save_stations_eligibles()
    if result["message"]:
        print(result["message"])
    else:
        print(f"Nombre de stations éligibles importées ou mises à jour : {result['total_inserted']} sur un total de {result['total_count']}.")

    #get_save_stations_eligibles()
