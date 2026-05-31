from psycopg2.extras import execute_batch, execute_values
### execute_batch et execute_values permettent d'insérer plusieurs lignes en une seule requête
### execute_values est plus performant que execute_batch pour les très gros volumes de données 10k
import pandas as pd
from db.sql_utils import python_to_sql 


class Installation:
    """Classe représentant une installation de production d'électricité."""
    def __init__(self):
        ## Constructor
        self.codeeicresourceobject = None
        self.codeiris = None
        self.codeinseecommune = None
        self.codeepci = None
        self.codedepartement = None
        self.filiere = None
        self.codetechnologie = None
        self.puismaxinstallee = None

    def getInstallationData(self, type_installation, region_code, departement_code,conn):
        """
        Docstring for getInstallationData
        
        :param type_installation: EOLIE, PHOTV, ALL
        :param region_code
        :param departement_code
        :param conn: connexion à la base de données ouverte
        """
        ## Fonction pour extraire les données d'installation depuis l'API
        try:
            cur = conn.cursor()
            sql = """
                select c.*,d.num_region from centrales c
                inner join departements d on d.num_dep=c.num_dep
                where (c.num_dep={departement_code} or {departement_code} is null)
                and (filiere = '{type_installation}' or codetechnologie='{type_installation}' or {type_installation} is null)
                and  (num_region = {region_code} or {region_code} is null) 
                /*and (installation_latitude is null or installation_longitude is null) -- test géolocalisation*/
                order by c.codeeicresourceobject;
            """

            ###Autre méthode
            #cur.execute(sql)
            ## Récupération des noms de colonnes
            #colonnes = [desc[0] for desc in cur.description]
            ## Récupération des données
            #rows = cur.fetchall()
            ## Création du DataFrame
            #data = pd.DataFrame(rows, columns=colonnes)

            data = pd.read_sql_query(
                sql.format(
                    departement_code=python_to_sql(departement_code) ,
                    type_installation=python_to_sql(type_installation), 
                    region_code=python_to_sql(region_code))
                , conn  )
            
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des installations : {e}")
            return []


    def save_lot(self, df, conn):
        ## Fonction pour sauvegarder les données des installations dans la bdd
        print("sauvegarde des données des installations...")
        isuccess = True

        sql = """
            INSERT INTO centrales (
                codeeicresourceobject,
                num_dep,
                codeiris,
                codeinseecommune,
                codeepci,
                codefiliere,
                filiere,
                codetechnologie,
                puismaxinstallee
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (codeeicresourceobject) DO UPDATE
            SET
                puismaxinstallee = EXCLUDED.puismaxinstallee,
                codetechnologie = EXCLUDED.codetechnologie,
                codefiliere = EXCLUDED.codefiliere,
                filiere = EXCLUDED.filiere;
        """

        try:
            cur = conn.cursor()
        
            records = [
                (
                    row.codeeicresourceobject,
                    row.codedepartement,
                    row.codeiris,
                    row.codeinseecommune,
                    row.codeepci,
                    row.codefiliere,
                    row.filiere,
                    row.codetechnologie,
                    row.puismaxinstallee
                )
                for row in df.itertuples(index=False)
            ]

            execute_batch(cur, sql, records, page_size=1000)
            conn.commit()
            print(f"{len(records)} installations sauvegardées en base")
            
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de la sauvegarde des données des installations: {e}")  
            isuccess = False  
        
        return isuccess
    
    # insertion par lots plus performante de 10 000 en 10 000
    """
    utilisation : 
        data = df_installations_station_meteo.to_records(index=False).tolist()
        insert_installation_station_links(conn, data)
    """
    def insert_installation_station_links(self,conn, data, batch_size=10_000):
        print("sauvegarde des liens entre installations et stations météo...")
        isuccess = True
        sql = """
            INSERT INTO stations_centrales (id_station, id_centrale, distance_km, ordre)
            VALUES %s
            ON CONFLICT (id_station, id_centrale) DO UPDATE
            SET distance_km = EXCLUDED.distance_km,
                ordre = EXCLUDED.ordre;
        """
        try:
            with conn.cursor() as cur:
                for i in range(0, len(data), batch_size):
                    batch = data[i : i + batch_size]
                    execute_values(cur, sql, batch)
            conn.commit()
            print(f"{len(data)} liens installations-stations météo sauvegardés en base")
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de la sauvegarde des liens entre installations et stations météo: {e}")  
            isuccess = False    
        finally:
            return isuccess

    # avec execute_batch
    def save_stations_linked(self, df, conn):
        ## Fonction pour sauvegarder les liens entre installations et stations météo dans la bdd
        print("sauvegarde des liens entre installations et stations météo...")
        isuccess = True

        sql = """
            insert into stations_centrales (id_station, id_centrale, distance_km, ordre)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id_station, id_centrale) DO UPDATE
            SET
                distance_km = EXCLUDED.distance_km,
                ordre = EXCLUDED.ordre;
        """

        try:
            cur = conn.cursor()
        
            records = [
                (
                    row.id_station,
                    row.id_centrale,
                    row.distance_km,    
                    row.ordre
                )
                for row in df.itertuples(index=False)
            ]

            execute_batch(cur, sql, records, page_size=1000)
            conn.commit()
            print(f"{len(records)} liens installations-stations météo sauvegardés en base")
            
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de la sauvegarde des liens entre installations et stations météo: {e}")  
            isuccess = False  
        
        return isuccess

    def save_data_geolocalisation(self, df, conn):
        ## Fonction pour sauvegarder les données des installations géolocalisées dans la bdd
        print("sauvegarde des données des installations géolocalisées...")
        isuccess = True

        sql = """
            UPDATE centrales
            SET
                installation_latitude = %s,
                installation_longitude = %s
            WHERE id_centrale = %s;
        """

        #ne conserve que les colonnes utiles du df
        df_update = df[
                        ["id_centrale", "installation_latitude", "installation_longitude"]
                    ].dropna(subset=["installation_latitude", "installation_longitude"])
        try:
            cur = conn.cursor()
        
            records = [
                (
                    float(row.installation_latitude),
                    float(row.installation_longitude),
                    row.id_centrale
                )
                for row in df_update.itertuples(index=False)
            ]

            execute_batch(cur, sql, records, page_size=1000)
            conn.commit()
            print(f"{len(records)} installations mises à jour")
            
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de la sauvegarde des données des installations géolocalisées: {e}")  
            isuccess = False  
        
        return isuccess