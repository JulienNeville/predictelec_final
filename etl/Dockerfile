# Image Python officielle, légère
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dossier de travail dans le conteneur
WORKDIR /app

# Installation des dépendances systèmes
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copier les dépendances Python
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code applicatif
COPY api ./api
COPY db ./db
COPY models ./models
COPY services ./services
COPY main.py .

# Commande de lancement avec argument en entrée : "INIT", "MAJ_STRUCTURES", "MAJ_PROD", "MAJ_METEO","MAJ_METEO_PREC", "MAJ_PREVISION"
ENTRYPOINT ["python", "main.py"]
CMD []
