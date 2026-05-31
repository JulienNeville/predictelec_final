import sys
from pathlib import Path

# Ajouter le répertoire parent au chemin Python
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import os
from db.base import Database
from models.installation import Installation
from models.station import Station
import dotenv #pip install python-dotenv
import time

dotenv.load_dotenv()

# --- haversine vectorisé pour gagner en vitesse ---
def haversine_vector(lat1, lon1, lats2, lons2):
    # tous en radians
    lat1_r = np.radians(lat1)
    lon1_r = np.radians(lon1)
    lats2_r = np.radians(lats2)
    lons2_r = np.radians(lons2)
    dlat = lats2_r - lat1_r
    dlon = lons2_r - lon1_r
    a = np.sin(dlat/2.0)**2 + np.cos(lat1_r) * np.cos(lats2_r) * np.sin(dlon/2.0)**2
    R = 6371.0
    return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

# --- associer_station : version robuste et informative ---
def associer_stations(installations, stations_eligibles, conn):
    """
    Associe à chaque installation les stations météos les plus proches qui possèdent la mesure pertinente (vent ou rayonnement)
    Retourne un DataFrame résultat et enregistre le résultat dans un fichier csv.
    """
    
    if "station_latitude" in stations_eligibles.columns:
        stations_eligibles["station_latitude"] = pd.to_numeric(stations_eligibles["station_latitude"], errors="coerce")
    if "station_longitude" in stations_eligibles.columns:
        stations_eligibles["station_longitude"] = pd.to_numeric(stations_eligibles["station_longitude"], errors="coerce")

    # gestion affichage résultat
    last_print =time.time()

    # Construire le DataFrame des 3 stations les plus proches pour cette installation   
    df=pd.DataFrame(columns=["id_station","id_centrale","distance_km","ordre"])

    for i, row in installations.iterrows():
        code_insee = row.get("codeinseecommune")
        if pd.isna(code_insee):
            print(f"[associer_station] ligne {i} : codeINSEECommune manquant → saut.")
            continue

        if (row.get("installation_latitude") is None) or (row.get("installation_longitude") is None):
            print(f"Coordonnées introuvables pour la station {i} (code {code_insee})")
            continue
        else:
            lat_inst = row.get("installation_latitude")
            lon_inst = row.get("installation_longitude")

        if row["filiere"] == 'Eolien':
            if stations_eligibles[stations_eligibles["mesure_vent"] == True].shape[0] > 0:
                stations_valid = stations_eligibles[stations_eligibles["mesure_vent"] == True]
                # Vectorisé : calcule distances pour toutes les stations
                distances = haversine_vector(lat_inst, lon_inst,
                                            stations_valid["station_latitude"].values,
                                            stations_valid["station_longitude"].values)
            else:
                raise ValueError("Pas de champ 'mesure_vent' disponible.")

        if row["filiere"] != 'Eolien':
            if stations_eligibles[stations_eligibles["mesure_rayonnement"] == True].shape[0] > 0:
                stations_valid = stations_eligibles[stations_eligibles["mesure_rayonnement"] == True]
                # Vectorisé : calcule distances pour toutes les stations
                distances = haversine_vector(lat_inst, lon_inst,
                                            stations_valid["station_latitude"].values,
                                            stations_valid["station_longitude"].values)
            else:
                raise ValueError("Pas de champ 'mesure_rayonnement' disponible.")

        if distances.size == 0:
            print(f"[associer_station] Aucune station disponible pour l'installation {i} (code {code_insee})")
            continue

        stations_valid = stations_valid.reset_index(drop=True)
        stations_valid["distance_km"] = distances


        df_station=pd.DataFrame(columns=["id_station","id_centrale","distance_km","ordre"])

        # Ajouter les 3 stations les plus proches
        for k in range(3):
            idx_min = int(np.argmin(distances))
            nearest = stations_valid.iloc[idx_min]

            df_station.loc[k] = [                
                nearest["id_station"],
                row["id_centrale"],
                float(nearest["distance_km"]),
                k + 1
            ]
            # Supprimer la station déjà utilisée pour la prochaine itération
            stations_valid = stations_valid.drop(index=idx_min).reset_index(drop=True)
            # idem pour les distances
            distances = np.delete(distances, idx_min)

            if stations_valid.empty:
                break

        # Ajouter les données de liaison installation-station au DataFrame final
        df = pd.concat([df, df_station], ignore_index=True)

        # Affichage progression toutes les 30 secondes
        current_time = time.time()
        if current_time - last_print >= 10:
            print(f"Installation ligne {i + 1} / {installations.shape[0]} traitée.")
            last_print = current_time

        #debug : limiter le nombre d'installations pour test rapide
        #if i >= 2000:
        #    break

    return df

def combine_installations_stations_eligibles():
    """Associe les installations géolocalisées avec les stations météo éligibles et sauvegarde en base."""
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
        
        #charger les stations éligibles depuis la base de données plutôt que depuis le fichier json
        station = Station()
        df_stations_eligibles = station.getlistStation(db.conn)
        
        df_installations_station_meteo = associer_stations(df_installations, df_stations_eligibles,db.conn)
        
        #convertir les Nan en None pour insertion en base
        df_installations_station_meteo = df_installations_station_meteo.replace({np.nan: None})

        # Enregistrer les liens installation-station en base
        #result = Installation.Installation().save_stations_linked(df_installations_station_meteo, db.conn)
        
        if df_installations_station_meteo.empty:
            print("Aucune association installation-station météo n'a été réalisée.")
            return output_dict
        
        # attention ordre des colonnes est importante car utilisée pour l'insertion en base
        data = df_installations_station_meteo[["id_station","id_centrale","distance_km","ordre"]].to_records(index=False).tolist()
        result = installation.insert_installation_station_links(db.conn, data)
        if result:
            output_dict["total_inserted"] = df_installations_station_meteo.shape[0]
        else:
            output_dict["total_errors"] = df_installations_station_meteo.shape[0]
        print("Association terminéee : {} associations installation-station météo réalisées.".format(df_installations_station_meteo.shape[0]))
    except Exception as e:
        print(f"Erreur lors de l'association des installations avec les stations météo : {e}")
    finally:
        return output_dict

if __name__=='__main__':
    result =combine_installations_stations_eligibles()
    print(f"{result['total_inserted']} stations météo ont été liées à {result['total_count']} installations")
