#import sys
#from pathlib import Path

# Ajouter le répertoire parent au chemin Python
#sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import pandas as pd
from models.installation import Installation
from models.territoire import Territoire
import os
import dotenv #pip install python-dotenv 
from db.base import Database
from api.api_rte import get_installations

dotenv.load_dotenv()

def get_save_allinstallations(liste_code_region=None, liste_code_departement=None):
    """
    Extrait d'une API et 
     sauvegarde en base.
    """
    # codetechnologie : PHOTV
    # codefiliere : EOLIE
    types_installations = ["PHOTV", "EOLIE"]
   
    total_count = 0

    output_dict = {
    "total_count": 0,
    "total_inserted": 0,
    "total_errors": 0
    }
    db = Database(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),        
        port=os.getenv('DB_PORT')
    )
    try:
        db.connect()

        if liste_code_region is None:
            liste_code_region = Territoire.liste_regions(db.conn)
    
        # parcours des types d'installations
        for type_installation in types_installations:  
                
            station_count = 0
            error_count = 0
    
            # parcours des régions
            for code_region in liste_code_region :               
                if liste_code_departement is None:
                    liste_departement = Territoire.liste_departements(code_region,db.conn)   
                else:
                    liste_departement = liste_code_departement
                # parcours des départements
                for code_departement in liste_departement:
                    result=get_installations(type_installation,code_region,code_departement,db.conn)
                    station_count += result["total_inserted"]
                    error_count += result["total_errors"]
                    total_count += result["total_count"]

            # mise à jour des compteurs globaux
            output_dict["total_count"] += station_count + error_count
            output_dict["total_inserted"] += station_count  
            output_dict["total_errors"] += error_count
            print(f"{station_count} installations {type_installation} sur {station_count+error_count} au total ont été récupérées.")
    
    except requests.exceptions.RequestException as e:
        print(f"Une erreur est survenue lors de la requête : {e}")
    finally:   
        db.close()
        return output_dict
        
def extract_latitude(centre):
    """Extrait la latitude du centre d'une commune"""
    if isinstance(centre, dict):
        return centre["coordinates"][1]
    return None

def extract_longitude(centre):
    """Extrait la longitude du centre d'une commune"""
    if isinstance(centre, dict):
        return centre["coordinates"][0]
    return None

def get_codeinsee_plus_proche(codeinsee, liste_codeinsee):
        """Trouve le code INSEE le plus proche numériquement dans une liste de codes INSEE"""
        codeinsee_int = int(codeinsee)
        liste_codeinsee_int = [int(code) for code in liste_codeinsee]
        codeinsee_proche = min(liste_codeinsee_int, key=lambda x: abs(x - codeinsee_int)) # syntaxe qui permet de renvoyer l'élément de liste_codeinsee_int tel que la valeur de abs(x - codeinsee_int) est minimale
        return str(codeinsee_proche).zfill(5)

def get_coordinates_proche(code_insee, df_coord):
        """Trouve les coordonnées du code INSEE le plus proche"""
        codes_disponibles = df_coord["code"].tolist()
        code_proche = get_codeinsee_plus_proche(code_insee, codes_disponibles)
        
        if code_proche not in codes_disponibles:
            return None
            
        longitude = df_coord.loc[df_coord["code"] == code_proche, "centre"].apply(extract_longitude).values[0]
        latitude = df_coord.loc[df_coord["code"] == code_proche, "centre"].apply(extract_latitude).values[0]
        return longitude, latitude

def save_installations_geoloc():
    """
    Charge les données des installations éoliennes et photovoltaïques, récupère les coordonnées géographiques du centre de chaque code INSEE correspondant via une API publique, et enregistre le résultat en base.
    """
    output_dict = {
    "total_count": 0,
    "total_inserted": 0,
    "total_errors": 0
    }

    db = Database(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),        
        port=os.getenv('DB_PORT')
    )
    try:
        db.connect()
   
        installation = Installation()
        df_installations = installation.getInstallationData(type_installation=None, region_code=None, departement_code=None, conn=db.conn)  
        output_dict["total_count"] = df_installations.shape[0]

        # on récupère les coordonnées géographiques de tous les codes INSEE de France continentale
        liste_code_region = Territoire.liste_regions(db.conn)
        df_coordinates_codeinsee = Territoire.get_all_codeinsee_coordinates(liste_code_region,db.conn)

        #formatage des codes INSEE à 5 caractères avec des zéros initiaux si besoin
        df_installations["codeinseecommune"] = df_installations["codeinseecommune"].astype(str).str.zfill(5)  
        df_coordinates_codeinsee["code"] = df_coordinates_codeinsee["code"].astype(str).str.zfill(5)  

        # on mappe les coordonnées géographiques dans le dataframe des installations
        latitude_mapping = (df_coordinates_codeinsee
                    .set_index("code")["centre"]
                    .apply(extract_latitude))
        df_installations["installation_latitude"] = df_installations["codeinseecommune"].map(latitude_mapping)
        longitude_mapping = (df_coordinates_codeinsee
                    .set_index("code")["centre"]
                    .apply(extract_longitude))
        df_installations["installation_longitude"] = df_installations["codeinseecommune"].map(longitude_mapping)

        # on traite les codes INSEE sans coordonnées géographiques en prenant les coordonnées du code INSEE le plus proche numériquement
        mask = df_installations["installation_longitude"].isna() & df_installations["installation_latitude"].isna() & df_installations["codeinseecommune"].notna()
        codes_a_traiter = df_installations.loc[mask, "codeinseecommune"].unique().tolist()
        mapping_longitude = {}
        mapping_latitude = {}
        for code in codes_a_traiter:
            coords = get_coordinates_proche(code, df_coordinates_codeinsee)
            mapping_longitude[code] = coords[0] if (coords is not None and len(coords) >= 1) else None
            mapping_latitude[code] = coords[1] if (coords is not None and len(coords) >= 1) else None

        # remplir les longitudes manquantes à partir du mapping
        df_installations.loc[mask, "installation_longitude"] = df_installations.loc[mask, "codeinseecommune"].map(mapping_longitude)
        df_installations.loc[mask, "installation_latitude"] = df_installations.loc[mask, "codeinseecommune"].map(mapping_latitude)

        if df_installations["installation_latitude"].isna().sum() > 0 or df_installations["installation_longitude"].isna().sum() > 0:
            print("Certaines installations n'ont pas pu être géolocalisées :")
            print(df_installations[df_installations["installation_latitude"].isna() | df_installations["installation_longitude"].isna()][["id_centrale","codeinseecommune","installation_latitude","installation_longitude"]])
        else:
            print("Toutes les installations ont pu être géolocalisées.")
        
        
        # on enregistre le dataframe résultant dans la base de données
        result = installation.save_data_geolocalisation(df_installations, db.conn)
        if result:
            output_dict["total_inserted"] = df_installations.shape[0]
        else:
            output_dict["total_errors"] = df_installations.shape[0]
    except Exception as e:
        print(f"Une erreur est survenue lors de l'appel à la fonction : {e}")
    finally:   
        db.close()
        return output_dict        

if __name__ == "__main__":
    result=get_save_allinstallations()
    print(f"Nombre d'installations importées ou mises à jour : {result['total_inserted']} sur un total de {result['total_count']}.")
    result=save_installations_geoloc()
    print(f"Nombre d'installations géolocalisées : {result['total_inserted']} sur un total de {result['total_count']}.")    
    