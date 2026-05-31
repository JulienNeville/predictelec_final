#outils sql

"""python_to_sql(value): Convertit une valeur Python en représentation SQL sécurisée."""
def python_to_sql(value):
    """Convertit une valeur Python en représentation SQL sécurisée."""
    if value is None:
        return "NULL"
    elif isinstance(value, str):
        # Échappement des apostrophes pour éviter l'injection SQL
        return "'" + value.replace("'", "''") + "'"
    else:
        return str(value)
    
def log_import(type,identifiant,jour,status,source,message,conn):
    if type == 'PROD':
        log_import_production(conn,identifiant,jour,status,source,message)
    if type == 'METEO':
        log_import_meteo(conn,identifiant,jour,status,source,message)   

def log_import_production(conn, region, day, status, source, message):
    sql = """
        INSERT INTO import_log_production (
            code_insee_region,
            date_jour,
            status,
            source,     
            message
        )
        VALUES (%s, %s, %s, %s, %s)
    """

    with conn.cursor() as cur:
        cur.execute(sql, (region, day, status, source,message))
        conn.commit()

def log_import_meteo(conn, id_station, day, status, source, message):
    sql = """
        INSERT INTO import_log_meteo (
            station,
            date_jour,
            status,
            source,
            message
        )
        VALUES (%s, %s, %s, %s, %s)
    """

    with conn.cursor() as cur:
        cur.execute(sql, (id_station, day, status, source,message))
        conn.commit()

def get_last_import_date(type,source,conn):
    if type == 'PROD':
        get_last_import_prod_date(source,conn)
    if type == 'METEO':
        get_last_import_meteo_date(source,conn)

def get_last_import_prod_date(source, conn):
    """
    Retourne la dernière date importée avec succès
    pour une source donnée (CONSOLIDE ou REALTIME)
    """
    sql = """
        SELECT MAX(date_jour)
        FROM import_log_production
        WHERE 1=1
            AND status = 'SUCCESS'
            AND source = %s
    """

    with conn.cursor() as cur:
        cur.execute(sql, (source,))
        result = cur.fetchone()[0]

    return result  # None si aucune donnée

def get_last_import_meteo_date(source, conn):
    """
    Retourne la dernière date importée avec succès
    pour une source donnée CLIM (climatologie), OBS (observations) ou PREV (prévisions)
    """
    sql = """
        SELECT MAX(date_jour)
        FROM import_log_meteo
        WHERE 1=1
            AND status = 'SUCCESS'
            AND source = %s
    """

    with conn.cursor() as cur:
        cur.execute(sql, (source,))
        result = cur.fetchone()[0]

    return result  # None si aucune donnée