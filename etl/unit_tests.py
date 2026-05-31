import argparse
from services.init_base import init, init_views, refresh_views
from services.maj_installations import get_save_allinstallations as maj_installations
from services.maj_installations import save_installations_geoloc as maj_geoloc
from services.maj_stations import get_save_stations_eligibles as maj_stations
from services.combine_installations_stations import combine_installations_stations_eligibles as combine
from services.maj_meteo import get_save_meteo_hier as maj_meteo_quotidien
from services.maj_meteo import import_meteo_previous_month as maj_meteo_mois_precedent
from services.maj_production import get_save_production as maj_production_mois_precedent
from services.get_forecast_old import get_forecast_stations, get_coverage_ids

from dotenv import load_dotenv
load_dotenv(dotenv_path=".env.local")

import requests
def get_forecast_package():
    token = 'eyJ4NXQiOiJOelU0WTJJME9XRXhZVGt6WkdJM1kySTFaakZqWVRJeE4yUTNNalEyTkRRM09HRmtZalkzTURkbE9UZ3paakUxTURRNFltSTVPR1kyTURjMVkyWTBNdyIsImtpZCI6Ik56VTRZMkkwT1dFeFlUa3paR0kzWTJJMVpqRmpZVEl4TjJRM01qUTJORFEzT0dGa1lqWTNNRGRsT1RnelpqRTFNRFE0WW1JNU9HWTJNRGMxWTJZME13X1JTMjU2IiwidHlwIjoiYXQrand0IiwiYWxnIjoiUlMyNTYifQ.eyJzdWIiOiJhNWUzMjJiNS05YTk4LTQyY2YtYThkNi03ZmM2NGM3ZTdiYTEiLCJhdXQiOiJBUFBMSUNBVElPTiIsImF1ZCI6ImdrRkVpUEJ4b0JJMG10dHA1MGdQdU5pbm9WY2EiLCJuYmYiOjE3NzIxMDg3MTgsImF6cCI6ImdrRkVpUEJ4b0JJMG10dHA1MGdQdU5pbm9WY2EiLCJzY29wZSI6ImRlZmF1bHQiLCJpc3MiOiJodHRwczpcL1wvcG9ydGFpbC1hcGkubWV0ZW9mcmFuY2UuZnJcL29hdXRoMlwvdG9rZW4iLCJleHAiOjE3NzIxMTIzMTgsImlhdCI6MTc3MjEwODcxOCwianRpIjoiMmNhZDAzM2EtMDQ0OC00NTJmLWJiZDktOTlhYTQ0MGZjYWVjIiwiY2xpZW50X2lkIjoiZ2tGRWlQQnhvQkkwbXR0cDUwZ1B1Tmlub1ZjYSJ9.sU9KrsVDI6O3EQsNNqjHztLbEP0130S70SXPWE8ipeVvqHEolFtBPHTSmNI0kfb5kQbmPQs7t7iJRqvIa4S-NDShPNTJxxtTJEqcBchMkGsaXFt1roh9Wed4fwG50cojEqnxnIwn6zlG_8JgXF-YbmvuQUygjVz4ncmSXkfS8N8cYRI_TnzNA2dGONCG2xGOWSMQMBRfrhpvB1AM2AWXE18IFNATb7MlgflTOAYycApGcIiRfj2JXCcA9pyRP4Bf36yx2PSzs07YI5Diur6Lfl38h8e9AIjtdpJEdPt1mr0Avgrd9DvQBxZNvoCBtjh8n-UmWyFUmbrJ8DH3EjC2Ug'
    url = 'https://public-api.meteofrance.fr/previnum/DPPaquetARPEGE/v1/models/ARPEGE/grids/0.25/packages/HP1/productARP?referencetime=2026-02-26T06%3A00%3A00Z&time=073H102H&format=grib2'
    HEADERS = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=HEADERS)
    print(response.status_code)
    print(response.text)

from db.base import Database
import os
db = Database(
    host=os.getenv('DB_HOST'),
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),        
    port=os.getenv('DB_PORT')
)
db.create_forecast_table()