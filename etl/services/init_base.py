#import sys
#from pathlib import Path

# Ajouter le répertoire parent au chemin Python
#sys.path.insert(0, str(Path(__file__).parent.parent))

from db import base
from models.territoire import Territoire
import os
import dotenv #pip install python-dotenv

dotenv.load_dotenv()

print("DB_HOST =", os.getenv("DB_HOST"))
print("DB_NAME =", os.getenv("DB_NAME"))
print("DB_USER =", os.getenv("DB_USER"))
print("MODE =", os.getenv("MODE"))

def init():
    """
    Docstring for init database
    """
    db = base.Database(
    host=os.getenv('DB_HOST'),
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),        
    port=os.getenv('DB_PORT')
    )
    if os.getenv('MODE') == "DEV":
        print("Mode de fonctionnement : DEV - SANS DOCKER")
        # Créer la base de données
        db.create_base()
    # Créer les tables nécessaires
    db.create_tables()
    # Connection
    db.connect()
    # Importe départements + regions
    Territoire.init_dep_region(db.conn)
    # Fermer la connexion à la base de données
    db.close()

def init_views():
    """
    Docstring for init view
    """
    db = base.Database(
    host=os.getenv('DB_HOST'),
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),        
    port=os.getenv('DB_PORT')
    )
    # Connection
    db.connect()
    # Créer les vues 
    db.create_view()
    # Fermer la connexion à la base de données
    db.close()

def refresh_views():
    """
    Docstring for refresh view
    """
    db = base.Database(
    host=os.getenv('DB_HOST'),
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),        
    port=os.getenv('DB_PORT')
    )
    # Connection
    db.connect()
    # Créer les vues 
    db.refresh_view()
    # Fermer la connexion à la base de données
    db.close()