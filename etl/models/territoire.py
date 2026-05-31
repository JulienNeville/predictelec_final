import requests
import pandas as pd
import json
from pathlib import Path


class Territoire:
    """Classe représentant un territoire administratif (région ou département)."""

    def init_dep_region(conn):
        ##todo: retrouver l'API d'origine pour initialiser proprement
        # chemin absolu vers le fichier JSON
        BASE_DIR = Path(__file__).resolve().parents[1]
        JSON_PATH = BASE_DIR / "api" / "departements_region_map_continental.json"
        if not JSON_PATH.exists():
            raise FileNotFoundError(f"Fichier introuvable : {JSON_PATH}")
        try:
            cur = conn.cursor()
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            # création d'un dictionnaire des régions
            regions = {}
            for d in data:
                regions[d["num_region"]] = d["region_name"]

            #  INSERT REGIONS 
            for num_region, region_name in regions.items():
                cur.execute("""
                    INSERT INTO regions (num_region, region_name)
                    VALUES (%s, %s)
                    ON CONFLICT (num_region) DO
                    UPDATE SET region_name = EXCLUDED.region_name;
                """, (num_region, region_name))
            print("Table regions remplie.")


            #  INSERT DEPARTEMENTS ou UPDATE si déjà existant
            for d in data:
                cur.execute("""
                    INSERT INTO departements (num_dep, dep_name, num_region)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (num_dep) DO 
                    UPDATE SET dep_name = EXCLUDED.dep_name,
                            num_region = EXCLUDED.num_region;
                """, (d["num_dep"], d["dep_name"], d["num_region"]))
            print("Table departements remplie.")
            conn.commit()
        except Exception as e:
            print(f"Erreur lors de l'importation des régions et départements' : {e}")

    def liste_regions(conn):
        """Retourne la liste des régions disponibles dans la base de données."""
        try:
            cur = conn.cursor()
            sql = """
                SELECT num_region FROM regions order by num_region;
            """
            cur.execute(sql)
            records = cur.fetchall()
            liste_regions = [record[0] for record in records]
            return liste_regions
        except Exception as e:
            print(f"Erreur lors de la récupération de la liste des régions : {e}")
            return []

    def liste_departements(region_code, conn):
        """Retourne la liste des départements pour cette région."""
        try:
            cur = conn.cursor()
            sql = f"""
                SELECT num_dep FROM departements
                WHERE num_region = '{region_code}' 
                order by num_dep;
            """
            cur.execute(sql)
            records = cur.fetchall()
            liste_departements = [record[0] for record in records]
            return liste_departements
        except Exception as e:
            print(f"Erreur lors de la récupération des départements pour la région {region_code} : {e}")
            return []            
        
    """ Télécharge, enregistre, retourne dans un dataframe les coordonnées géographiques des communes françaises continentales via l'API geo.api.gouv.fr"""    
    def get_all_codeinsee_coordinates(liste_code_region, conn):
        """
        Télécharge, enregistre, retourne dans un dataframe les coordonnées géographiques des communes françaises continentales via l'API geo.api.gouv.fr
        """ 
        api_url = f"https://geo.api.gouv.fr/communes?fields=code,codeRegion,centre"  
   
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            df_data = pd.DataFrame(data)
            
            # convertir les codes de région en str pour la comparaison
            liste_code_region = [str(c) for c in liste_code_region]

            df_data_continental = df_data[df_data["codeRegion"].isin(liste_code_region)]
            #df = df_data_continental.to_dict(orient="records")
            
            
            return df_data_continental
        except requests.exceptions.RequestException as e:
            print(f"get_coordinates_from_codeinsee : Erreur lors de la requête API : {e}")
            return None