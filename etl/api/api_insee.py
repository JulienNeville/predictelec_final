import requests
import pandas as pd


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