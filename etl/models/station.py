from psycopg2.extras import execute_batch
import pandas as pd

class Station:
    """Classe représentant une station météo."""
    def __init__(self):
        self.id_station = None
        self.latitude = None
        self.longitude = None
        self.mesure_vent = None
        self.mesure_rayonnement = None

    def getlistStation(self, conn):
        """
        Docstring for getlistStation
        
        :param conn: connexion à la base de données ouverte
        """
        ## Fonction pour extraire les données des stations depuis la BDD
        try:
            cur = conn.cursor()
            sql = """
                select * from stations
                order by id_station;
            """

            cur.execute(sql)
            ## Récupération des noms de colonnes
            colonnes = [desc[0] for desc in cur.description]
            ## Récupération des données
            rows = cur.fetchall()
            ## Création du DataFrame
            data = pd.DataFrame(rows, columns=colonnes)
            
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des stations : {e}")
            return []

    def getlistStationUtile(self, conn):
        """
        Docstring for getlistStationUtile
        
        :param conn: connexion à la base de données ouverte
        """
        ## Fonction pour extraire les données des stations depuis la BDD
        try:
            cur = conn.cursor()
            sql = """
                select distinct s.* from stations_centrales sc
                inner join stations s on sc.id_station = s.id_station
                order by s.id_station;
            """

            cur.execute(sql)
            ## Récupération des noms de colonnes
            colonnes = [desc[0] for desc in cur.description]
            ## Récupération des données
            rows = cur.fetchall()
            ## Création du DataFrame
            data = pd.DataFrame(rows, columns=colonnes)
            
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des stations : {e}")
            return []
                
    def save_lot(self, df, conn):
        ## Fonction pour sauvegarder les données des stations dans la bdd
        print("sauvegarde des données des stations...")
        isuccess = True

        sql = """
            INSERT INTO stations (
                id_station,
                station_latitude,
                station_longitude,  
                mesure_vent,
                mesure_rayonnement
            )               
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id_station) DO UPDATE
            SET
                mesure_vent = EXCLUDED.mesure_vent,
                mesure_rayonnement = EXCLUDED.mesure_rayonnement;
        """

        try:
            cur = conn.cursor()
        
            records = [
                (
                    row.id_station,
                    row.station_latitude,  
                    row.station_longitude,
                    row.mesure_vent,
                    row.mesure_rayonnement
                )
                for row in df.itertuples(index=False)
            ]

            execute_batch(cur, sql, records, page_size=1000)
            conn.commit()
            print(f"{len(records)} stations sauvegardées en base")
            
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de la sauvegarde des données des stations: {e}")  
            isuccess = False  
        
        return isuccess
    
