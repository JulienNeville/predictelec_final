from psycopg2.extras import execute_batch
import pandas as pd
from db.sql_utils import python_to_sql

class Production:
    """
    Docstring for Production
    Production d'électricité par région et par filière.
    """

    def __init__(self):
        ## Constructor
        self.id=None
        self.region_id = None
        self.date_heure = None
        self.prod_heure = None
        self.prod_jour = None
        self.prod_eolien=None
        self.prod_solaire = None


    def getProductionData(self, start_date, end_date, region=None, conn=None):
        """
        Docstring for getProductionData
        
        :param start_date: date de début au format 'YYYY-MM-DD'
        :param end_date: date de fin au format 'YYYY-MM-DD'
        :param region: code de la région (optionnel)
        :param conn: connexion à la base de données ouverte
        """
        ## Fonction pour extraire les données de production depuis la BDD
        try:
            cur = conn.cursor()
            sql = """
                select *
                from production
                where (date_heure >= {start_date} and date_heure <= {end_date})
                and (region_id = {region} or {region} is null)
                order by region_id, date_heure;
            """

            data = pd.read_sql_query(
                sql.format(
                    start_date=python_to_sql(start_date),
                    end_date=python_to_sql(end_date),
                    region=python_to_sql(region)
                ), conn
            )
            
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des données de production : {e}")
            return []

    def delete_non_consolidee(self, region, day_start, day_end, conn):
        """
        Supprime les données de production NON consolidées (temps réel)
        pour une région et une période données.
        """
        print(
            f"Suppression des données temps réel "
            f"pour la région {region} entre {day_start} et {day_end}"
        )

        sql = """
            DELETE FROM production
            WHERE
                num_region = %s
                AND source = 'REALTIME'
                AND date_heure >= %s
                AND date_heure < %s
        """

        try:
            cur = conn.cursor()
            cur.execute(sql, (region, day_start, day_end))
            deleted = cur.rowcount
            conn.commit()

            print(f"{deleted} lignes temps réel supprimées")

        except Exception as e:
            conn.rollback()
            raise RuntimeError(
                f"Erreur lors de la suppression des données non consolidées : {e}"
            )


    def save_lot(self, df, source, conn):
        """
        Sauvegarde des données de production en base
        source : 'realtime' | 'consolide'
        """
        print(f"sauvegarde des données de production ({source})...")
        isuccess = True

        if source == "REALTIME":
            sql = """
                INSERT INTO production (
                    num_region,
                    date_heure,
                    prod_date,
                    prod_heure,
                    prod_eolien,
                    prod_solaire,
                    source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (num_region, date_heure) DO UPDATE
                SET
                    prod_eolien = EXCLUDED.prod_eolien,
                    prod_solaire = EXCLUDED.prod_solaire,
                    source = EXCLUDED.source
            """
        elif source == "CONSOLIDE":
            sql = """
                INSERT INTO production (
                    num_region,
                    date_heure,
                    prod_date,
                    prod_heure,
                    prod_eolien,
                    prod_solaire,
                    source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (num_region, date_heure) DO NOTHING
            """
        else:
            raise ValueError(f"Source inconnue : {source}")

        try:
            cur = conn.cursor()

            records = [
                (
                    row.code_insee_region,
                    row.date_heure,
                    row.date,
                    row.heure,
                    row.tch_eolien,
                    row.tch_solaire,
                    source
                )
                for row in df.itertuples(index=False)
            ]

            execute_batch(cur, sql, records, page_size=1000)
            conn.commit()
            print(f"{len(records)} lignes sauvegardées ({source})")

        except Exception as e:
            conn.rollback()
            print(f"Erreur lors de la sauvegarde : {e}")
            isuccess = False

        return isuccess