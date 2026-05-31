import requests
import os
import time
import subprocess
import json

TOKEN_URL = "https://portail-api.meteofrance.fr/token"
_token_cache = {}

def get_users():
    users = []
    i = 1
    while True:
        token = os.getenv(f"METEOFRANCE_BASIC_AUTH_{i}")
        if not token:
            break
        users.append({"name": f"user_{i}", "token_user":f"METEOFRANCE_BASIC_AUTH_{i}", "token": token})
        i += 1

    if not users:
        raise ValueError("Pas de tokens")

    return users


# Récupère un token valide, en utilisant le cache si possible
def get_valid_token(token_user=None):
    global _token_cache

    # récupère les tokens disponibles dans les variables d'environnement
    users = get_users()

    if not users:
        raise ValueError("Aucun utilisateur/token disponible.")

    if token_user is None:
        # Par défaut, on prend le premier user disponible        
        token_user = users[0]["token_user"]

    # Recherche du token en cache pour ce user
    token_data = _token_cache.get(token_user)

    # Token encore valide ?
    if token_data and time.time() < token_data["expires_at"]:
        return token_data["access_token"]

    # Sinon on demande un nouveau token
    user_secret = os.getenv(token_user)
    if not user_secret:
        raise ValueError(f"Aucune variable d'environnement trouvée pour {token_user}")

    headers = {
        "Authorization": f"Basic {user_secret}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    r = requests.post(
        TOKEN_URL,
        headers=headers,
        data="grant_type=client_credentials",
        timeout=10
    )
    r.raise_for_status()

    data = r.json()

    # Mise à jour ou ajout dans le cache
    _token_cache[token_user] = {
        "access_token": data["access_token"],
        "expires_at": time.time() + data["expires_in"] - 60
    }

    return _token_cache[token_user]["access_token"]

def get_valid_token_debugwindows(token_user=None):
    global _token_cache

    # Recherche du token en cache pour ce user
    users = get_users()

    if not users:
        raise ValueError("Aucun utilisateur/token disponible.")

    if token_user is None:
        # Par défaut, on prend le premier user disponible
        token_user = users[0]["token_user"]

    # Recherche du token en cache pour ce user
    token_data = _token_cache.get(token_user)

    # Token encore valide ?
    if token_data and time.time() < token_data["expires_at"]:
        return token_data["access_token"]

    # Sinon on demande un nouveau token
    user_secret = os.getenv(token_user)
    if not user_secret:
        raise ValueError(f"Aucune variable d'environnement trouvée pour {token_user}")

    cmd = [
        "curl.exe",
        "-s",
        "-X", "POST",
        TOKEN_URL,
        "-H", f"Authorization: Basic {user_secret}",
        "-H", "Content-Type: application/x-www-form-urlencoded",
        "-d", "grant_type=client_credentials"
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Erreur curl : {result.stderr}")

    data = json.loads(result.stdout)

    # Mise à jour ou ajout dans le cache
    _token_cache[token_user] = {
        "access_token": data["access_token"],
        "expires_at": time.time() + data["expires_in"] - 60
    }

    return _token_cache[token_user]["access_token"]