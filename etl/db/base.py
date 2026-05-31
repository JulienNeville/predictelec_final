import json
import psycopg2
from psycopg2 import sql, OperationalError, Error
# nécessite de lancer dans le terminal : pip install psycopg2-binary


class Database:
    """
    Classe pour gérer la connexion et les requêtes PostgreSQL.
    Utilise psycopg2 et gère automatiquement la fermeture des ressources.
    """
 
    def __init__(self, host, dbname, user, password, port=5432):
        self.host = host
        self.dbname = dbname
        self.user = user
        self.password = password
        self.port = port
        self.conn = None
        self.cursor = None

    def connect(self):
        """Établit la connexion à la base de données."""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                port=self.port
            )
            self.cursor = self.conn.cursor()
            print(f"Connexion réussie à {self.dbname}")
        except OperationalError as e:
            print(f"Erreur de connexion : {e}")
            raise

    def execute_query(self, query, params=None):
        """
        Exécute une requête SQL (INSERT, UPDATE, DELETE).
        Utilise des paramètres pour éviter les injections SQL.
        """
        if not self.cursor:
            raise ConnectionError("La connexion n'est pas établie.")
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            print("Requête exécutée avec succès")
        except Error as e:
            self.conn.rollback()
            print(f"Erreur lors de l'exécution : {e}")
            raise

    def fetch_all(self, query, params=None):
        """Exécute une requête SELECT et retourne tous les résultats."""
        if not self.cursor:
            raise ConnectionError("La connexion n'est pas établie.")
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except Error as e:
            print(f"Erreur lors de la récupération : {e}")
            raise

    def close(self):
        """Ferme proprement le curseur et la connexion."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("Connexion fermée")
      
        
    def create_base(self):
        # obligation de désactiver les transactions pour créer la base
        conn = None
        cur = None
        try:
            # Connexion à la base système "postgres"
            conn = psycopg2.connect(
                host=self.host,
                dbname="postgres",
                user=self.user,
                password=self.password,
                port=self.port
            )

            # OBLIGATOIRE pour CREATE DATABASE
            conn.autocommit = True

            cur = conn.cursor()
            cur.execute(f"CREATE DATABASE {self.dbname}")

            print(f"Base {self.dbname} créée avec succès")

        except psycopg2.errors.DuplicateDatabase:
            print(f"La base {self.dbname} existe déjà")

        except Exception as e:
            print(f"Erreur lors de la création de la base {self.dbname} : {e}")

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def create_view(self):
        try:
            self.connect()
            self.cursor.execute("""
                /*Création de la table méteo ramené à la région par tranche de 15 minutes
                    pour correspondre aux données de production*/
                DROP MATERIALIZED VIEW IF EXISTS mv_meteo_region_15min_2 CASCADE;
                CREATE MATERIALIZED VIEW mv_meteo_region_15min_2 AS
                WITH station_region AS (
                    SELECT DISTINCT
                        sc.id_station,
                        d.num_region
                    FROM stations_centrales sc
                    JOIN centrales c ON sc.id_centrale = c.id_centrale
                    JOIN departements d ON c.num_dep = d.num_dep
                    WHERE c.codetechnologie IN ('TERRE', 'PHOTV')
                    AND (
                            (c.codetechnologie = 'TERRE' AND sc.ordre = 1)
                            OR (c.codetechnologie = 'PHOTV')
                        )
                ),
                meteo_15 AS (
                    SELECT
                        id_station,
                        date_trunc('hour', validity_time)
                        + floor(extract(minute FROM validity_time) / 15) * interval '15 minutes'
                        AS validity_time_interval_15,
                        vitesse_vent,
                        rayonnement_solaire
                    FROM meteo
                )
                SELECT
                    sr.num_region,
                    m15.validity_time_interval_15		AS date_heure,
                    ROUND(AVG(m15.vitesse_vent), 2)        AS moyenne_vitesse_vent,
                    ROUND(AVG(m15.rayonnement_solaire), 2) AS moyenne_rayonnement_solaire
                FROM meteo_15 m15
                JOIN station_region sr
                ON m15.id_station = sr.id_station
                GROUP BY
                    sr.num_region,
                    m15.validity_time_interval_15
                ORDER BY
                    sr.num_region,
                    m15.validity_time_interval_15;
            """)

            self.cursor.execute("""
                /*Création de la table forecast ramené à la région par tranche de 15 minutes
                    pour correspondre aux données de prévision*/
                DROP MATERIALIZED VIEW IF EXISTS mv_forecast_region_15min_2 CASCADE;
                CREATE MATERIALIZED VIEW mv_forecast_region_15min_2 AS
                WITH station_region AS (
                    SELECT DISTINCT
                        sc.id_station,
                        d.num_region
                    FROM stations_centrales sc
                    JOIN centrales c ON sc.id_centrale = c.id_centrale
                    JOIN departements d ON c.num_dep = d.num_dep
                    WHERE c.codetechnologie IN ('TERRE', 'PHOTV')
                    AND (
                            (c.codetechnologie = 'TERRE' AND sc.ordre = 1)
                            OR (c.codetechnologie = 'PHOTV')
                        )
                ),
                meteo_15 AS (
                    SELECT
                        id_station,
                        forecast_time  AS validity_time_interval_15,
                        vitesse_vent,
                        rayonnement_solaire
                    FROM forecast
                )
                SELECT
                    sr.num_region,
                    m15.validity_time_interval_15		AS "timestamp",
                    ROUND(AVG(m15.vitesse_vent), 2)        AS moyenne_vitesse_vent,
                    ROUND(AVG(m15.rayonnement_solaire), 2) AS moyenne_rayonnement_solaire
                FROM meteo_15 m15
                JOIN station_region sr
                ON m15.id_station = sr.id_station
                GROUP BY
                    sr.num_region,
                    m15.validity_time_interval_15
                ORDER BY
                    sr.num_region,
                    m15.validity_time_interval_15;
            """)

            self.cursor.execute("""
                /*table pour entrainer le modèle ML concernant l'éolien*/
                CREATE OR REPLACE VIEW prod_eolien_meteo_2 AS
                SELECT
                    p.num_region as code_region_insee,
                    r.region_name as region,
                    p.date_heure as "timestamp",
                    m.moyenne_vitesse_vent as vitesse_vent_15min,
                    p.prod_eolien as eol_mwh_15min
                FROM production p
                INNER JOIN mv_meteo_region_15min_2 m
                ON m.num_region = p.num_region
                AND m.date_heure = p.date_heure
                INNER JOIN regions r
                ON r.num_region = p.num_region;
            """)

            self.cursor.execute("""
                /*table pour entrainer le modèle ML concernant le solaire*/
                CREATE OR REPLACE VIEW prod_solaire_meteo_2 AS
                SELECT
                    p.num_region as code_region_insee,
                    r.region_name as region,
                    p.date_heure as "timestamp",
                    m.moyenne_rayonnement_solaire as ghi_wh_m2_15min,
                    p.prod_solaire as pv_mwh_15min
                FROM production p
                INNER JOIN mv_meteo_region_15min_2 m
                ON m.num_region = p.num_region
                AND m.date_heure = p.date_heure
                INNER JOIN regions r
                ON r.num_region = p.num_region;
            """)

            self.cursor.execute("""
                /*table pour prédiction concernant l'éolien*/
                CREATE OR REPLACE VIEW pred_eolien_forecast_2 AS
                SELECT
                    m.num_region as code_region_insee,
                    r.region_name as region,
                    m.timestamp as "timestamp",
                    GREATEST(m.moyenne_vitesse_vent, 0)::numeric(10,2) as vitesse_vent_15min
                FROM mv_forecast_region_15min_2 m
                INNER JOIN regions r
                ON r.num_region = m.num_region
                WHERE m.moyenne_vitesse_vent IS NOT NULL;
            """)

            self.cursor.execute("""
                /*table pour prédiction concernant le solaire*/
                CREATE OR REPLACE VIEW pred_solaire_forecast_2 AS
                SELECT
                    m.num_region as code_region_insee,
                    r.region_name as region,
                    m.timestamp as "timestamp",
                    GREATEST(m.moyenne_rayonnement_solaire, 0)::numeric(10,2) as ghi_wh_m2_15min
                FROM mv_forecast_region_15min_2 m
                INNER JOIN regions r
                ON r.num_region = m.num_region
                WHERE m.moyenne_rayonnement_solaire IS NOT NULL;
            """)

            self.conn.commit()
            print("Vues créées ou remplacées avec succès.")
        except Exception as e:
            print(f"Erreur lors de la création des vues : {e}")
        finally:
            self.close()

    def refresh_view(self):
        try:
            self.connect()
            # attention : la vue doit déjà exister, sinon erreur
            # attention : l'ordre est important 
            self.cursor.execute("""
                /*Commande pour mettre à jour la vue*/
                REFRESH MATERIALIZED VIEW mv_meteo_region_15min_2;
            """)
            self.cursor.execute("""
                /*Commande pour mettre à jour la vue*/
                REFRESH MATERIALIZED VIEW mv_forecast_region_15min_2;
            """)
            self.conn.commit()
            print("Vues mv_meteo_region_15min_2 et mv_forecast_region_15min_2 actualisées avec succès.")
        except Exception as e:
            print(f"Erreur lors de l'actualisation des vues : {e}")
        finally:
            self.close()

    def create_tables(self):
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                port=self.port
            )
            self.cursor = self.conn.cursor()

            self.cursor.execute("""
                DROP TABLE IF EXISTS regions CASCADE;
                CREATE TABLE regions
                    (
                        num_region int NOT NULL,
                        region_name TEXT NOT NULL,
                        CONSTRAINT regions_pkey PRIMARY KEY(num_region)
                    );
            """)

            self.cursor.execute("""
                DROP TABLE IF EXISTS departements CASCADE;
                CREATE TABLE departements
                (
                    num_dep int NOT NULL,
                    dep_name TEXT NOT NULL,
                    num_region int NOT NULL,
                    CONSTRAINT departements_pkey PRIMARY KEY (num_dep),
                    CONSTRAINT fk_departements_regions FOREIGN KEY (num_region)
                    REFERENCES regions (num_region)
                );
            """)

            self.cursor.execute("""
                drop table if exists stations cascade;
                create table stations
                (
                    id_station bigserial not null,
                    station_latitude numeric(6,4),
                    station_longitude numeric(6,4),
                    validity_time timestamp without time zone not null default now(),
                    mesure_vent boolean default false,
                    mesure_rayonnement boolean default false, 
                    debut timestamp without time zone default now(),
                    fin timestamp without time zone,
                    constraint stations_pkey primary key(id_station)
                );
            """)

            self.cursor.execute("""
                drop table if exists centrales cascade;
                create table centrales
                (
                    id_centrale bigserial,
                    codeeicresourceobject text UNIQUE,
                    codeiris text null,
                    codeinseecommune integer not null,
                    codeepci text null,
                    num_dep int not null,
                    codefiliere text not null,
                    filiere text not null,
                    codetechnologie text null, 
                    puismaxinstallee numeric(8,1),
                    installation_latitude numeric(6,4),
                    installation_longitude numeric(6,4),
                    debut timestamp without time zone default now(),
                    fin timestamp without time zone,
                    constraint centrales_pkey primary key(id_centrale),
                    CONSTRAINT centrales_codeeicresourceobject_key UNIQUE (codeeicresourceobject),                                
                    CONSTRAINT fk_centrales_departements foreign key (num_dep)
                    references departements(num_dep)
                );
            """)

            self.cursor.execute("""
                drop table if exists stations_centrales cascade;
                create table stations_centrales
                (
                    id_station_centrale bigserial,
                    id_station bigint not null,
                    id_centrale bigint not null,
                    distance_km numeric(6,2),-- clean -> round sur 2 digits valeur calculée
                    ordre integer, -- calcul : du plus proche au plus éloigné
                    debut timestamp without time zone default now(),
                    fin timestamp without time zone,
                    constraint stations_centrales_pkey primary key(id_station_centrale),
                    CONSTRAINT fk_stations_centrales_centrales foreign key (id_centrale)
                    references centrales(id_centrale),
                    CONSTRAINT fk_stations_centrales_stations foreign key (id_station)
                    references stations(id_station),
                    CONSTRAINT stations_centrales_unique UNIQUE (id_station, id_centrale)
                );
            """)

            self.cursor.execute("""
                DROP TABLE IF EXISTS meteo CASCADE;
                create table meteo
                (
                    id_meteo bigserial,
                    id_station bigint not null,
                    validity_time timestamp with time zone not null,
                    vitesse_vent numeric(6,1),
                    rayonnement_solaire numeric(8,1),
                    constraint meteo_pkey primary key(id_meteo),
                    CONSTRAINT meteo_ukey UNIQUE (id_station,validity_time),
                    CONSTRAINT fk_meteo_stations foreign key (id_station)
                    references stations(id_station)
                );
            """)

            self.cursor.execute("""
                DROP TABLE IF EXISTS production CASCADE;
                CREATE TABLE production
                (
                    id_production BIGSERIAL,
                    num_region integer NOT NULL,
                    date_heure TIMESTAMP WITH TIME ZONE NOT NULL,
                    prod_date date,
                    prod_heure time without time zone,
                    prod_eolien numeric(8,1), --(version1)
                    prod_solaire numeric(8,1),--(version1)
                    source text not null default 'REALTIME', -- REALTIME ou CONSOLIDE
                    CONSTRAINT production_pkey PRIMARY KEY(id_production),
                    CONSTRAINT production_unique UNIQUE (num_region, date_heure),                    
                    CONSTRAINT fk_production_regions FOREIGN KEY (num_region)
                    REFERENCES regions(num_region)
                );               
            """)
            # table log import données de production
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_log_production (
                    id bigserial,
                    code_insee_region VARCHAR(3),
                    date_jour DATE,
                    status VARCHAR(10), -- SUCCESS / ERROR
                    source VARCHAR(20), -- CONSOLIDE / REALTIME
                    message TEXT,
                    created_at TIMESTAMP DEFAULT now()
                );
            """)
             # table log import données de météo
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_log_meteo (
                    id bigserial,
                    station text,
                    date_jour DATE,
                    status VARCHAR(10), -- SUCCESS / ERROR
                    source VARCHAR(20), -- CLIM / OBS / PREV
                    message TEXT,
                    created_at TIMESTAMP DEFAULT now());
            """)
            self.cursor.execute("""
                DROP TABLE IF EXISTS forecast CASCADE;
                CREATE TABLE forecast
                (
                    id_forecast bigserial,
                    id_station bigint not null,
                    forecast_time timestamp with time zone not null,
                    coverage_id_vitesse_vent text default null,
                    vitesse_vent numeric(6,1),
                    coverage_id_rayonnement_solaire text default null,
                    rayonnement_solaire numeric(12,1),
                    constraint forecast_pkey primary key(id_forecast),
                    CONSTRAINT forecast_ukey UNIQUE (id_station,forecast_time),
                    CONSTRAINT fk_forecast_stations foreign key (id_station)
                    references stations(id_station)
                );
            """)
            self.cursor.execute("""
                DROP TABLE IF EXISTS forecast_archive CASCADE;
                CREATE TABLE forecast_archive
                (
                    id bigserial,
                    date_archivage timestamp without time zone default now(),            
                    id_forecast bigint not null,
                    id_station bigint not null,
                    forecast_time timestamp with time zone not null,
                    vitesse_vent numeric(6,1),
                    rayonnement_solaire numeric(12,1),
                    constraint forecast_archive_pkey primary key(id),
                    CONSTRAINT forecast_archive_ukey UNIQUE (date_archivage,id_station,forecast_time)
                );
            """)
            print("Tables créées avec succès.")
        except Exception as e:
            print(f"Erreur à la création des tables: {e}")
        finally:
            self.conn.commit()
            self.cursor.close()
            self.conn.close()

    def create_forecast_table(self):
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                port=self.port
            )
            self.cursor = self.conn.cursor()

            self.cursor.execute("""
                DROP TABLE IF EXISTS forecast CASCADE;
                CREATE TABLE forecast
                (
                    id_forecast bigserial,
                    id_station bigserial not null,
                    forecast_time timestamp with time zone not null,
                    coverage_id_vitesse_vent text default null,
                    vitesse_vent numeric(6,1),
                    coverage_id_rayonnement_solaire text default null,
                    rayonnement_solaire numeric(12,1),
                    constraint forecast_pkey primary key(id_forecast),
                    CONSTRAINT forecast_ukey UNIQUE (id_station,forecast_time),
                    CONSTRAINT fk_forecast_stations foreign key (id_station)
                    references stations(id_station)
                );
            """)
            print("Table forecast créée avec succès.")
        except Exception as e:
            print(f"Erreur à la création de la table forecast: {e}")
        finally:
            self.conn.commit()
            self.cursor.close()
            self.conn.close()
