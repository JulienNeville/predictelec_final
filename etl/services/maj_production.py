# debug : ajoute répertoire parent au PYTHONPATH
#import sys
#from pathlib import Path
#sys.path.append(str(Path(__file__).resolve().parents[1]))


import json
import requests
from datetime import date,timedelta
import os
import pandas as pd

# fichiers __init__.py nécessaire dans chaque répertoire
from models.production import Production
from models.territoire import Territoire
from db.base import Database
from db.sql_utils import get_last_import_date, log_import
from datetime import datetime
import dotenv #pip install python-dotenv

dotenv.load_dotenv()

#https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-regional-tr/records?
# where=date_heure%20%3E=%20%222025-03-01%22%20AND%20date_heure%20%3C=%20%222025-03-03%22&limit=100

def daterange(start_date, end_date):
    """Générateur de dates (inclusives)"""
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)

def get_save_production():
    """
    Docstring for get_save_production
    Traitement de la période + region
    - récupération de la date max des données consolidées pour limiter les appels API
    - récupération de la dernière date importée (consolidée et temps réel) pour reprise incrémentale
     (en reprenant le lendemain de la dernière date importée pour éviter les doublons et les appels inutiles à l'API)
    """
    ###reprise incrémentale
    max_date_consolidee = get_max_date_consolidee()
    print("Date max des données consolidées :", max_date_consolidee)


    db = Database(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),        
        port=os.getenv('DB_PORT')
    )
    try:
        db.connect()
        last_consolide = get_last_import_date("PROD","CONSOLIDE", db.conn)
        last_realtime = get_last_import_date("PROD","REALTIME", db.conn) 
        #récupère la date de début des données de production, par défaut 2026-01-01 
        date_debut_str = os.getenv('DATE_DEBUT_PROD', '2026-01-01')
        date_debut_prod = datetime.strptime(date_debut_str, "%Y-%m-%d").date()

        print("Dernière date CONSOLIDE :", last_consolide)
        print("Dernière date REALTIME :", last_realtime)
               
        # Période dynamique jusqu'à hier
        end_target = date.today() - timedelta(days=1)
        

        ## Si déjà des imports consolidés → reprise le lendemain
        if last_consolide:
            conso_start = last_consolide + timedelta(days=1)
        else:
            # premier import historique
            conso_start = date_debut_prod  # ou date de début officielle

        # période consolidée
        if max_date_consolidee:
            conso_end = min(end_target, max_date_consolidee)
        else:
            conso_end = date_debut_prod # ou date de début officielle
        
        # période temps réel
        ## Si déjà des imports realtime → reprise le lendemain
        if last_realtime:
            start_target = last_realtime + timedelta(days=1)
        else:
            start_target = date_debut_prod  # ou date de début officielle
        
        realtime_start = max(start_target, conso_end)


        liste_region = Territoire.liste_regions(db.conn)
        if conso_start < conso_end:
            print(f"Import CONSOLIDE du {conso_start} au {conso_end}")
            get_save_production_regions_consolidee(
                conso_start, conso_end, liste_region, db.conn
            )
        else:
            print("Aucune donnée CONSOLIDE à importer")
        
        if realtime_start <= end_target:
            print(f"Import REALTIME du {realtime_start} au {end_target}")
            get_save_production_regions_tempsreel(
                realtime_start, end_target, liste_region, db.conn
            )
        else:
            print("Aucune donnée REALTIME à importer")      

        #get_save_production_regions(start_date,end_date,liste_region,db.conn)
    except Exception as e:
        print(f"Erreur lors de la connexion à la base de données : {e}")
    finally:
        db.close()

def fetch_production_consolidee(region, start_datetime, end_datetime):
    """
    Docstring for fetch_production
    Appel API production par region et par date
    (attention <10000 enregistrements par limit 100)
    :param region: Description
    :param start_datetime: Description
    :param end_datetime: Description
    """
    API_URL = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-regional-cons-def/records"
    params = {
        "where": (
            f"code_insee_region = '{region}' "
            f"AND date_heure >= '{start_datetime}' "
            f"AND date_heure <= '{end_datetime}'"
        ),
        "limit": 100,
        "order_by": "date_heure"
    }

    all_rows = []
    offset = 0

    while True:
        params["offset"] = offset
        r = requests.get(API_URL, params=params)
        r.raise_for_status()
        data = r.json()["results"]

        if not data:
            break

        all_rows.extend(data)
        offset += 100

    return pd.DataFrame(all_rows)

def fetch_production_tempsreel(region, start_datetime, end_datetime):
    """
    Docstring for fetch_production
    Appel API production par region et par date
    (attention <10000 enregistrements par limit 100)
    :param region: Description
    :param start_datetime: Description
    :param end_datetime: Description
    """
    API_URL = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-regional-tr/records"
    params = {
        "where": (
            f"code_insee_region = '{region}' "
            f"AND date_heure >= '{start_datetime}' "
            f"AND date_heure <= '{end_datetime}'"
        ),
        "limit": 100,
        "order_by": "date_heure"
    }

    all_rows = []
    offset = 0

    while True:
        params["offset"] = offset
        r = requests.get(API_URL, params=params)
        r.raise_for_status()
        data = r.json()["results"]

        if not data:
            break

        all_rows.extend(data)
        offset += 100

    return pd.DataFrame(all_rows)

# recherche de la date max des données consolidées pour limiter les appels API
def get_max_date_consolidee():
    url = (
        "https://odre.opendatasoft.com/api/explore/v2.1/"
        "catalog/datasets/eco2mix-regional-cons-def/records"
        "?limit=1&order_by=-date_heure"
    )
    r = requests.get(url)
    r.raise_for_status()
    results = r.json()["results"]
    return pd.to_datetime(results[0]["date_heure"], utc=True).date()

def get_save_production_regions_consolidee(start_date, end_date, regions, conn):
    """
    Import de la production par jour et par région
    """
    prod = Production()

    for day in daterange(start_date, end_date):
        day_start = f"{day}T00:00:00+00:00"
        day_end = f"{day}T23:59:59+00:00"

        for region in regions:
            try:
                print(f"Import production | Région {region} | {day}")

                # 1 appel API
                df = fetch_production_consolidee(
                    region=region,
                    start_datetime=day_start,
                    end_datetime=day_end
                )

                if df.empty:
                    log_import("PROD", region, day, "WARNING", "CONSOLIDE","Aucune donnée",conn)
                    continue

                # vérification des données : si les deux productions éolien et solaire sont nulles → log warning et pas d'insertion
                # Vérifie colonnes présentes
                if {"prod_eolien", "prod_solaire"}.issubset(df.columns):
                    eolien_sum = df["prod_eolien"].fillna(0).sum()
                    solaire_sum = df["prod_solaire"].fillna(0).sum()
                    if eolien_sum == 0 and solaire_sum == 0:
                        log_import("PROD", region, day, "WARNING", "CONSOLIDE","Valeurs nulles",conn)
                        continue

                # 2 suppression des données non consolidées sur la période (si existantes)
                prod.delete_non_consolidee(region, day_start, day_end, conn)
                # 3 insertion immédiate
                prod.save_lot(df,"CONSOLIDE", conn)

                # 3 log succès
                log_import("PROD", region, day, "SUCCESS", "CONSOLIDE",None,conn)

            except Exception as e:
                conn.rollback()
                log_import("PROD", region, day, "ERROR", "CONSOLIDE", str(e), conn)
                print(f"Erreur région {region} | {day} : {e}")


def get_save_production_regions_tempsreel(start_date, end_date, regions, conn):
    """
    Import de la production par jour et par région
    """
    prod = Production()

    for day in daterange(start_date, end_date):
        day_start = f"{day}T00:00:00+00:00"
        day_end = f"{day}T23:59:59+00:00"

        for region in regions:
            try:
                print(f"Import production | Région {region} | {day}")

                # 1 appel API
                df = fetch_production_tempsreel(
                    region=region,
                    start_datetime=day_start,
                    end_datetime=day_end
                )

                if df.empty:
                    log_import("PROD", region, day, "WARNING", "REALTIME","Aucune donnée",conn)
                    continue

                # vérification des données : si les deux productions éolien et solaire sont nulles → log warning et pas d'insertion
                # Vérifie colonnes présentes
                if {"tch_eolien", "tch_solaire"}.issubset(df.columns):
                    eolien_sum = df["tch_eolien"].fillna(0).sum()
                    solaire_sum = df["tch_solaire"].fillna(0).sum()
                    if eolien_sum == 0 and solaire_sum == 0:
                        log_import("PROD", region, day, "WARNING", "REALTIME","Valeurs nulles",conn)
                        continue

                # 2 insertion immédiate
                prod.save_lot(df,"REALTIME", conn)

                # 3 log succès
                log_import("PROD", region, day, "SUCCESS", "REALTIME",None,conn)

            except Exception as e:
                conn.rollback()
                log_import("PROD", region, day, "ERROR", "REALTIME", str(e), conn)
                print(f"Erreur région {region} | {day} : {e}")

def get_save_production_regions(start_date, end_date, regions, conn):
    """
    Import de la production par jour et par région en fonction de la disponibilité des données (consolidées ou temps réel)
    """
    prod = Production()

    #ne pas d'appel au delà de la date max des données consolidées
    max_date_consolidee = get_max_date_consolidee()
    if end_date < max_date_consolidee:
        #periode entièrement dans les données consolidées
        get_save_production_regions_consolidee(start_date, end_date, regions, conn)
    elif start_date > max_date_consolidee:
        #periode entièrement dans les données en temps réel
        get_save_production_regions_tempsreel(start_date, end_date, regions, conn)
    else:
        #periode mixte : on traite en deux fois
        print(f"Attention période mixte : données consolidées jusqu'au {max_date_consolidee} | données temps réel à partir du {max_date_consolidee + timedelta(days=1)}")
        #traitement des données consolidées
        get_save_production_regions_consolidee(start_date, max_date_consolidee, regions, conn)
        #traitement des données temps réel
        get_save_production_regions_tempsreel(max_date_consolidee + timedelta(days=1), end_date, regions, conn)

    

###get_save_production()

# def get_save_production_regions_old(debut_date, fin_date, region=None):

#     """
#     Récupère toutes les données eco2mix-regional-tr entre deux dates en paginant par blocs de 100.
#     - debut_date et fin_date au format 'YYYY-MM-DD'
#     - region (optionnel) : ex 'Auvergne-Rhône-Alpes'
    
#     Retourne une liste de dicts (enregistrements).
#     """

#     BASE_URL = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-regional-tr/records"
#     LIMIT = 100
#     offset = 0
#     results = []

#     # prépare la clause WHERE
#     where_clause = f"date_heure >= '{debut_date}' AND date_heure <= '{fin_date}'"
#     if region:
#         where_clause += f" AND region = '{region}'"

#     while True:
#         params = {
#             "select": "code_insee_region,date_heure,date,heure,tch_eolien,tch_solaire",
#             "where": where_clause,
#             "limit": LIMIT,
#             "offset": offset,
#             "order_by": "date_heure"   # pour un ordre cohérent des données
#         }

#         response = requests.get(BASE_URL, params=params)
#         response.raise_for_status()
#         data = response.json()

#         records = data.get("results", [])
#         results.extend(records)

#         # si moins de 100 enregistrements, on a atteint la fin
#         if len(records) < LIMIT:
#             break
        
#         offset += LIMIT  # passe au bloc suivant
#         print("offset",offset)

#     # Sauvegarde des données dans la base
#     prod = Production()
#     df_records = pd.json_normalize(results) 

#     db = Database(
#         host=os.getenv('DB_HOST'),
#         dbname=os.getenv('DB_NAME'),
#         user=os.getenv('DB_USER'),
#         password=os.getenv('DB_PASSWORD'),        
#         port=os.getenv('DB_PORT')
#     )
#     try:
#         db.connect()
#         isaved = prod.save_lot(df_records, db.conn)
#         if isaved:  
#             print(f"Sauvegarde réussie de {len(results)} enregistrements de production.")
#         else:
#             print("Erreur lors de la sauvegarde des données de production.")
#     except Exception as e:
#         print(f"Erreur lors de la connexion à la base de données : {e}")
#     finally:
#         db.close()   
#     return results



# def get_save_production_regions_hier():
#     """
#     Docstring for get_save_production_regions_hier
#     Appel spécifiquement save production pour la journée d'hier
#     """
#     hier = date.now() - timedelta(days=1)
#     hier_str = hier.strftime("%Y-%m-%d")
#     return get_save_production_regions(hier_str, hier_str)

# if __name__ == "__main__":
#     ##test sur la journée d'hier
#     #all_data=get_save_production_regions_hier()
    
#     #test sur une période
#     start = "2025-07-01"
#     end   = "2025-07-07"
#     region_id = None  # ou "22"

#     all_data = get_save_production_regions(start, end, region=region_id)

#     print(f"Nombre total d'enregistrements récupérés : {len(all_data)}")
#     print(all_data[:5])  # aperçu des 5 premiers