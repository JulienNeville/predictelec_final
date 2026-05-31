import argparse
from email import parser
from services.init_base import init, init_views, refresh_views
from services.maj_installations import get_save_allinstallations as maj_installations
from services.maj_installations import save_installations_geoloc as maj_geoloc
from services.maj_stations import get_save_stations_eligibles as maj_stations
from services.combine_installations_stations import combine_installations_stations_eligibles as combine
from services.maj_meteo import get_save_meteo_hier as maj_meteo_quotidien
from services.maj_meteo import import_meteo_previous_month as maj_meteo_mois
from services.maj_production import get_save_production as maj_production_mois_precedent
#from services.get_forecast_new import update_forecast_db
from services.get_forecast_old import maj_prevision
import os
import dotenv
dotenv.load_dotenv(dotenv_path=".env.local")

def main(action=None, parametres=None):
    print(f"Action donnée : {action}")
    print(f"Paramètres donnée : {parametres}")
    #MODE CLI
    if action is None:
        parser = argparse.ArgumentParser(description="Gestion des opérations Predictelec")
        parser.add_argument("action", choices=["INIT", "INIT_VIEWS", "REFRESH_VIEWS", "MAJ_STRUCTURES", "MAJ_STATIONS","COMBINE_STRUCTURES", "MAJ_PROD", "MAJ_METEO","MAJ_METEO_PREC","MAJ_METEO_PREC_MOIS", "MAJ_PREVISION"])
        parser.add_argument("parametres", nargs="*", help="Paramètres supplémentaires pour certaines actions (optionnel)")
        
        args = parser.parse_args()
        action=args.action
        parametres=args.parametres


    # MODE APPEL INTERNE / DEBUG : utilise action passée en paramètre
    
    print(f"Action exécutée : {action}")
    print(f"Paramètres exécutés : {parametres}")

    if action == "INIT":
        print("Initialisation base de données...")
        init()
        init_views()

    elif action == "INIT_VIEWS":
        print("Initialisation des vues...")
        init_views()

    elif action == "REFRESH_VIEWS":
        print("Actualisation des vues...")
        refresh_views()

    elif action == "MAJ_STRUCTURES":
        print("Mise à jour mensuelle des installations et des stations...")
        maj_installations()
        maj_geoloc()
        maj_stations()
        combine()

    elif action == "COMBINE_STRUCTURES":
        print("Mise à jour uniquement des combinaisons installations/stations...")
        combine()

    elif action == "MAJ_STATIONS":
        print("Mise à jour uniquement des stations météo...")
        maj_stations()

    elif action == "MAJ_PROD":
        print("Mise à jour mois précédent des données de production...")
        maj_production_mois_precedent()
        refresh_views()

    elif action == "MAJ_METEO":
        print("Mise à jour journalière des données météorologiques...")
        maj_meteo_quotidien()
        refresh_views()        

    elif action == "MAJ_METEO_PREC":
        print("Mise à jour mensuelle des données météorologiques...")
        maj_meteo_mois()
        refresh_views()    

    elif action == "MAJ_METEO_PREC_MOIS":
        print("Mise à jour mensuelle des données météorologiques...")
        if parametres is None:
            print("Aucun paramètre de date fourni, utilisation de la date actuelle.")
            date_ref = None
        else:
            date_ref = parametres[0]
        maj_meteo_mois(date_ref=date_ref)
        refresh_views()             

    elif action == "MAJ_PREVISION":
        print("Récupération des prévisions météorologiques...")
        #update_forecast_db()
        maj_prevision()

if __name__ == "__main__":
    if os.getenv('MODE') == "DEV":
        #debug
        #main("INIT")
        #main("MAJ_STRUCTURES")
        #main("MAJ_PROD")
        #main("MAJ_METEO")
        #main("MAJ_METEO_PREC") 
        #main("MAJ_PREVISION")
        main("MAJ_METEO_PREC_MOIS", parametres=["2026-01-01"])

    if os.getenv('MODE') == "PROD":
         #prod
         main()