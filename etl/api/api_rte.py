import requests
import pandas as pd
from models.installation import Installation


#todo : passer l'objet installation en paramètre, ne pas l'instancier dans la fonction
# prévoir type_installation et liste d'objets installation dans l'objet installation_manager ?
def get_installations(type_installation,code_region,code_departement,conn):    
    """
    Extrait d'une API et 
     sauvegarde en base.
    """
    # codetechnologie : PHOTV
    # codefiliere : EOLIE
    BASE_URL = "https://odre.opendatasoft.com"
   
    output_dict = {
        "total_count": 0,
        "total_inserted": 0,
        "total_errors": 0
        }

    station_count = 0
    error_count = 0

    # Initialisation des objets
    installation=Installation()
    
    # limitation batch API : 100 enregistrements par appel
    batch_size = 100
    #initialisation de l'offset
    offset_val = 0
    
    #template url
    template_url = (
        "{BASE_URL}/api/explore/v2.1/catalog/datasets/"
        "registre-national-installation-production-stockage-electricite-agrege/records"
        "?select=codeeicresourceobject,codeiris,codeinseecommune,codeepci,"
        "codedepartement,coderegion,codefiliere,filiere,codetechnologie,puismaxinstallee"
        "&where={where_clause}"
        "&limit={batch_size}"
        "&offset={offset_val}"
    )
    try:
        where_clause = (
                        f"(codefiliere = '{type_installation}' or codetechnologie = '{type_installation}') "
                        f"and regime = 'En service' "
                        f"and coderegion = '{code_region}' "
                        f"and codedepartement = '{code_departement}'"
                        )
        # on limite à 100 enregistrements par appel
        # initialisation 1er appel
        offset_val = 0
        # boucle de récupération des données par batch
        while True:
            url = template_url.format(
                BASE_URL=BASE_URL,
                where_clause=where_clause,
                batch_size=batch_size,
                offset_val=offset_val
            )
            r = requests.get(url)
            r.raise_for_status()
            response_data = r.json()
            df_batch = pd.json_normalize(response_data["results"])

            batch_count = df_batch.shape[0]
            
            #si pas de données, on sort de la boucle
            if batch_count == 0:
                print("Pas d'installation {} pour la région {} et le département {}.".format(type_installation,code_region,code_departement))
                break
            
            print("Traitement de {} installations {} pour la région {} et le département {} (offset={})...".format(batch_count,type_installation,code_region,code_departement,offset_val))
            #remplace les valeurs NaN par None pour éviter les erreurs d'insertion en base
            df_batch=df_batch.where(pd.notnull(df_batch), None) 
            # on sauvegarde les données du batch courant dans la bdd
            result = installation.save_lot(df_batch,conn)

            if result:
                station_count += batch_count
            else:
                error_count += batch_count                       
                                    
            #si moins de batch_size, on sort de la boucle
            if batch_count < batch_size:
                break
            # sinon incrémentation de l'offset
            offset_val = offset_val + batch_size

        output_dict["total_count"] += station_count + error_count
        output_dict["total_inserted"] += station_count
        output_dict["total_errors"] += error_count
        print(f"{station_count} installations {type_installation} sur {station_count+error_count} au total ont été récupérées.")
    
    except requests.exceptions.RequestException as e:
        print(f"Une erreur est survenue lors de la requête : {e}")
    finally:
      return output_dict