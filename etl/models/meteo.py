from psycopg2.extras import execute_batch
import pandas as pd
from db.sql_utils import python_to_sql


class Meteo:
    """
    Docstring for Meteo
    """
    def __init__(self):
        self.id = None
        self.id_station = None
        self.validity_time = None
        self.vitesse_vent= None
        self.rayonnement_solaire=None

    def save_lot(self,df,conn):
        ## Fonction pour sauvegarder les données météo dans la bdd
        print("sauvegarde des données météo...")
        isuccess = True

        sql = """
            INSERT INTO meteo (
                id_station,
                validity_time,
                vitesse_vent,
                rayonnement_solaire
            )               
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id_station, validity_time) DO UPDATE
                SET
                    vitesse_vent = EXCLUDED.vitesse_vent,
                    rayonnement_solaire = EXCLUDED.rayonnement_solaire
        """

        try:
            cur = conn.cursor()
            records = [
                (
                    row.id_station,
                    row.validity_time,
                    row.vitesse_vent,
                    row.rayonnement_solaire
                )
                for row in df.itertuples(index=False)
            ]

            execute_batch(cur, sql, records, page_size=1000)
            conn.commit()
            print(f"{len(records)} lignes de meteo sauvegardées en base")
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de la sauvegarde des données météo : {e}")
            isuccess = False

        return isuccess
    
    def archive_forecast_partiels(self, df, conn):
        try:
            cur = conn.cursor()
            for index, row in df.iterrows():
                forecast_time = row['forecast_time']
                id_station = row['id_station']
                cur.execute("""
                    INSERT INTO forecast_archive(id_forecast, id_station, forecast_time, vitesse_vent, rayonnement_solaire, date_archivage)
                    SELECT id_forecast, id_station, forecast_time, vitesse_vent, rayonnement_solaire, CURRENT_TIMESTAMP 
                    FROM forecast
                    WHERE forecast_time = %s AND id_station = %s;
                """, (forecast_time, id_station))
                cur.execute("""
                    DELETE FROM forecast
                    WHERE forecast_time = %s AND id_station = %s;
                """, (forecast_time, id_station  ))  
            conn.commit()
            print("Prévisions météo archivées avec succès.")
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de l'archivage des prévisions météo : {e}")
    
    def archive_forecast(self,conn):
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO forecast_archive(id_forecast, id_station, forecast_time, vitesse_vent, rayonnement_solaire, date_archivage)
                SELECT id_forecast, id_station, forecast_time, vitesse_vent, rayonnement_solaire, CURRENT_TIMESTAMP FROM forecast;
            """)
            cur.execute("TRUNCATE TABLE forecast;")
            conn.commit()
            print("Prévisions météo archivées avec succès.")
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de l'archivage des prévisions météo : {e}")

    """ Archive les prévisions météo historiques dont la date de validité est antérieure à la date du jour avant de les supprimer de la table forecast.
    """
    def archive_forecast_historique(self,conn):
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO forecast_archive(id_forecast, id_station, forecast_time, vitesse_vent, rayonnement_solaire, date_archivage)
                SELECT id_forecast, id_station, forecast_time, vitesse_vent, rayonnement_solaire, CURRENT_TIMESTAMP FROM forecast
                WHERE forecast_time < date(CURRENT_DATE);
            """)
            cur.execute("DELETE FROM forecast where forecast_time < date(CURRENT_DATE);")
            conn.commit()
            print("Prévisions météo historiques archivées avec succès.")
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de l'archivage des prévisions météo historiques : {e}")            

    def save_forecast(self, df, conn):
        print("sauvegarde des prévisions météo...")
        isuccess = True

        sql = """
            INSERT INTO forecast (
                id_station,
                forecast_time,
                coverage_id_vitesse_vent,
                vitesse_vent,
                coverage_id_rayonnement_solaire,
                rayonnement_solaire
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_station, forecast_time)
            DO UPDATE SET
                coverage_id_vitesse_vent = EXCLUDED.coverage_id_vitesse_vent,
                vitesse_vent = EXCLUDED.vitesse_vent,
                coverage_id_rayonnement_solaire = EXCLUDED.coverage_id_rayonnement_solaire,
                rayonnement_solaire = EXCLUDED.rayonnement_solaire
            WHERE
                forecast.coverage_id_vitesse_vent IS DISTINCT FROM EXCLUDED.coverage_id_vitesse_vent
                OR forecast.coverage_id_rayonnement_solaire IS DISTINCT FROM EXCLUDED.coverage_id_rayonnement_solaire;
        """

        try:
            with conn.cursor() as cur:
                #archiver les prévisions existantes avant de les écraser
                self.archive_forecast(conn)
                #cur.execute("TRUNCATE TABLE forecast;")
                records = [
                    (
                        row.id_station,
                        row.forecast_time,
                        row.coverage_id_vitesse_vent,
                        row.vitesse_vent,
                        row.coverage_id_rayonnement_solaire,
                        row.rayonnement_solaire,
                    )
                    for row in df.itertuples(index=False)
                ]

                execute_batch(cur, sql, records, page_size=1000)

            conn.commit()
            print(f"{len(records)} lignes de prévisions meteo sauvegardées/ajustées en base")
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de la sauvegarde des prévisions météo : {e}")
            isuccess = False

        return isuccess
    
    def save_forecast_partiels(self, data, conn):
        print("sauvegarde des prévisions météo...")
        isuccess = True

        sql = """
            INSERT INTO forecast (
                id_station,
                forecast_time,
                vitesse_vent,
                rayonnement_solaire
            )
            VALUES (%s, %s, %s, %s) 
        """

        try:
            df=pd.DataFrame(data)

            with conn.cursor() as cur:
                #archiver les prévisions existantes avant de les écraser
                self.archive_forecast_partiels(df,conn)

                records = [
                    (
                        row.id_station,
                        row.forecast_time,
                        row.vitesse_vent,
                        row.rayonnement_solaire,
                    )
                    for row in df.itertuples(index=False)
                ]

                execute_batch(cur, sql, records, page_size=1000)

            conn.commit()
            print(f"{len(records)} lignes de prévisions meteo sauvegardées/ajoutées en base")
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de la sauvegarde des prévisions météo : {e}")
            isuccess = False

        return isuccess
    
    def delete_forecast(self,conn,forecast_time):
        print(f"Suppression des prévisions météo pour {forecast_time}...")
        isuccess = True

        sql = """
            DELETE FROM forecast
            WHERE forecast_time::date = %s
        """

        try:
            cur = conn.cursor()
            cur.execute(sql, (forecast_time,))
            conn.commit()
            print(f"Prévisions météo pour {forecast_time} supprimées de la base")
        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de la suppression des prévisions météo : {e}")
            isuccess = False

        return isuccess