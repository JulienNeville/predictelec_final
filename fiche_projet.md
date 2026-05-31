<h1><p align="center">DataScientest</p></h1>

<h2><p align="center">Proposition de Projet par Julien Neville : PredictElec</p></h2>

**Cursus concerné :** Data Engineer

**Difficulté :** ?

**Description détaillée :**

La production d'électricité par les énergies renouvelables (éolien, photovoltaïque), par nature intermittentes, pose des difficultés importantes aux gestionnaires de réseaux électriques. En effet, la stabilité du réseau nécessitant à tout instant l'équilibre entre la puissance produite et la puissance consommée, les pics et les creux intempestifs dus aux renouvelables doivent être compensés en temps réel. Cela peut se faire de deux façons:
- en modulant la puissance produite par les centrales pilotables (centrales nucléaires ou hydroélectriques principalement en France);
- en modulant la puissance consommée par des consommateurs pilotables (démarrables ou arrêtables sur demande).

En France, la modulation est aujourd'hui réalisée principalement par les centrales nucléaires qui ont l'obligation légale de réduire leur puissance en cas de pic de production des renouvelables, ce qui a des conséquences néfastes sur la rentabilité et sur la durée de vie des réacteurs nucléaires.

Ainsi, partout dans le monde, on cherche à développer des parcs de consommateurs pilotables. Par exemple, le 11 juillet 2025, la proposition de loi N° 1750 (https://www.assemblee-nationale.fr/dyn/17/textes/l17b1750_proposition-loi) a été déposée à l'Assemblée Nationale pour autoriser à titre expérimental l'utilisation des surplus électriques pour le minage de cryptoactifs.

Assurer la disponibilité des consommateurs pilotables lors des pics de production est crucial, non seulement pour leur propre rentabilité, mais aussi pour la gestion du réseau dans son ensemble. Il faut donc planifier précisément les opérations de maintenance préventive en anticipant les pics durant lesquels ces installations seront sollicitées.

**Le projet consiste à développer une application permettant de prédire les variations de production électrique des renouvelables sur la base des prévisions météorologiques. On utilisera les données historiques et temps réel de MétéoFrance et de RTE (gestionnaire du réseau national).**

|Etape|Description|Objectif|Modules de formation|Conditions de validation du projet|
|:-:|:-:|:-:|:-:|:-:|
|1|Récolte des données, Extraction et Transformation|Non exhaustif : - Données RTE sur la production et la consommation d'électricité (https://www.services-rte.com/fr/telechargez-les-donnees-publiees-par-rte.html), API "Production" et "Consommation" (https://data.rte-france.com/) - Données locales MétéoFrance (https://donneespubliques.meteofrance.fr/)|||
|2|Stockage de la donnée|Il s’agit de choisir la solution de stockage la plus adaptée. Il est tout à fait possible d’utiliser plusieurs systèmes de bases de donnés ensemble.|||
|3|Consommation de la donnée|Programmer l'algorithme du modèle.||
|4|Mise en production|Faire une API pour tester le modèle de ML et pourquoi pas requêter les données historiques. Dockeriser tout le projet pour qu’il soit reproduisible sur n’importe quel machine.||
|5|Automatisation des flux et Monitoring|Il faudra automatiser à l’aide d’outils divers la récupération des données.||
|6|Soutenance|Démonstration de l'appli et explication du raisonnement effectué lors du projet.|X|Soutenance, Rapport|

