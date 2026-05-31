#!/bin/bash
#fichier environnement pour les variables d'environnement (pas de .env pour ne pas risquer de le commiter par erreur, et pas d'export dans le .env pour pouvoir les utiliser dans docker compose)
#source /home/ubuntu/.predictelec_env
#source /root/.predictelec_env
ENV_FILE=/opt/predictelec/shared/.predictelec_env

# Vérifie si le fichier d'environnement existe avant de le sourcer : -f
# Vérifie si le fichier d'environnement existe et lisible avant de le sourcer : -r
if [ -r "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    echo "Fichier d'environnement introuvable: $ENV_FILE"
    exit 1
fi

# autorise erreur sans stopper le script : pas -e, sinon on ne récupère pas l'erreur à envoyer par mail
set +e

# Empêche plusieurs exécutions en même temps
LOCK_FILE="/tmp/maj_structures.lock"

# Aller dans le dossier parent du dossier du script
cd "$(dirname "$0")/.."

PROJECT_DIR="$(pwd)"
LOG_DIR="/opt/predictelec/shared/logs"
LOG_FILE="$LOG_DIR/maj_structures.log"

mkdir -p "$LOG_DIR"

if [ -f "$LOCK_FILE" ]; then
    echo "Script déjà en cours d'exécution." >> "$LOG_FILE"
    exit 1
fi

touch "$LOCK_FILE"
# tue le fichier lock en cas d'interruption (pas de blocage à cause du fichier lock présent alors que rien ne tourne)
trap "rm -f $LOCK_FILE" EXIT

echo "----------------------------------------" >> "$LOG_FILE"
echo "Début MAJ_STRUCTURES : $(date)" >> "$LOG_FILE"

# Exécution du job 
# ajout --no-deps pour ne pas relancer postgres
docker compose -f "$PROJECT_DIR/docker-compose.yml" run --rm --no-deps app MAJ_STRUCTURES >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

#stop le script si erreur
set -e

END_TIME=$(date)

if [ $EXIT_CODE -ne 0 ]; then
	#on log l'erreur
	echo "Erreur MAJ_STRUCTURES le $END_TIME : code=$EXIT_CODE" >> "$LOG_FILE"
	#envoie de l'erreur
	    if [ -z "$ALERT_EMAIL" ]; then
        echo "ALERT_EMAIL non définie !" >> "$LOG_FILE"
    else
        echo "Erreur MAJ_STRUCTURES le $END_TIME" | mail -s "ERREUR PREDICTELEC MAJ_STRUCTURES" "$ALERT_EMAIL"
    fi
else
	echo "Fin MAJ_STRUCTURES : $END_TIME" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"

#quitte avec le code erreur
exit $EXIT_CODE
