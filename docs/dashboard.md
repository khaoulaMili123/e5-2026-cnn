# Supervision de l’application CNN

## Objectif et choix des outils

Le dashboard « Suivi de l’application CNN » permet de suivre la collecte des
métriques de l’API, l’activité HTTP et le fonctionnement du modèle de
classification d’images satellites. Il complète la
[documentation de la correction HTTP 405](correction_405.md).

Trois éléments assurent la supervision :

- **FastAPI et `prometheus-client`** produisent les compteurs et les mesures de
  durée directement dans le code qui traite les requêtes et les prédictions.
- **Prometheus** collecte ces mesures périodiquement et stocke leur évolution.
- **Grafana** interroge Prometheus, affiche les indicateurs et évalue la règle
  d’alerte.

Ces outils permettent de suivre les tendances et les incidents dans le temps.
Les logs du client apportent un complément : début de récupération des
prédictions, réussite, statut HTTP, durée et erreur éventuelle.

## Organisation des fichiers

Le dépôt contient un second dossier `e5-2026-cnn/`, qui est le dossier applicatif.

```text
e5-2026-cnn/                         # Racine du dépôt Git
├── .env                            # Configuration locale, hors commit
├── docs/
│   ├── correction_405.md
│   └── dashboard.md
└── e5-2026-cnn/                     # Dossier applicatif
    ├── docker-compose.yml
    ├── api/app/
    │   ├── main.py                  # Instrumentation et route /metrics
    │   └── monitoring.py            # Déclaration des métriques
    └── monitoring/
        ├── prometheus.yml          # Configuration de la collecte
        ├── dashboard_cnn.json      # Export du dashboard Grafana
        └── alertes_cnn.yml         # Export de la règle d’alerte Grafana
```

Les exports conservent les définitions des panneaux et de l’alerte. Le fichier
Compose actuel conserve les réglages créés dans Grafana grâce à un volume ; il
ne charge pas automatiquement ces deux exports. Leur restauration est décrite
plus bas.

## Démarrage et accès

### Lancer les services

Prérequis : Docker avec Compose, le fichier `.env` renseigné à la racine du
dépôt et les prérequis de l’application, notamment les poids du modèle.

Depuis la racine du dépôt Git, entrer dans le dossier applicatif :

```bash
cd e5-2026-cnn
```

Toutes les commandes Compose de cette documentation s’exécutent ensuite depuis
ce dossier, qui contient `docker-compose.yml` :

```bash
docker compose --env-file ../.env up --build -d
docker compose --env-file ../.env ps
```

| Service | Adresse dans le navigateur |
| --- | --- |
| Client Streamlit | http://localhost:8501 |
| Documentation de l’API | http://localhost:8081/docs |
| Métriques de l’API | http://localhost:8081/metrics |
| Cibles de collecte Prometheus | http://localhost:9090/targets |
| Grafana | http://localhost:3001 |

Les ports du client et de l’API dépendent des valeurs du `.env`. Les ports
`9090` et `3001` sont fixés dans Compose et publiés sur `127.0.0.1`.

### Vérifier la collecte

Dans Prometheus, la cible `cnn-api` doit être **UP**. La configuration attendue
dans [`prometheus.yml`](../e5-2026-cnn/monitoring/prometheus.yml) est :

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "cnn-api"
    metrics_path: /metrics
    static_configs:
      - targets: ["web:80"]
```

Les noms `web` et `prometheus` désignent des services sur le réseau Docker.
Prometheus contacte `http://web:80/metrics`, indépendamment du port publié sur
la machine.

### Connecter Grafana à Prometheus

Sur une installation Grafana neuve, se connecter avec `admin` / `admin`, puis
choisir un nouveau mot de passe. Sur une installation déjà configurée, utiliser
le compte existant.

Dans **Connections → Add new connection**, sélectionner **Prometheus**, puis
**Add new data source** et renseigner :

| Paramètre | Valeur |
| --- | --- |
| Name | `prometheus` |
| Prometheus server URL | `http://prometheus:9090` |
| Authentication | `No authentication` |
| Scrape interval | `15s` |

Cliquer sur **Save & test**. L’adresse utilise le nom du service Docker :
`localhost` dans le conteneur Grafana désignerait Grafana lui-même.
Voir la [configuration officielle de la source Prometheus](https://grafana.com/docs/grafana/latest/datasources/prometheus/configure/).

## Métriques ajoutées au code

Les métriques sont déclarées dans
[`api/app/monitoring.py`](../e5-2026-cnn/api/app/monitoring.py) et alimentées dans
[`api/app/main.py`](../e5-2026-cnn/api/app/main.py).

| Métrique | Type | Signification |
| --- | --- | --- |
| `cnn_api_requests_total` | Counter | Nombre de requêtes HTTP, avec les labels `method`, `route` et `status`. |
| `cnn_inferences_total` | Counter | Nombre d’appels réussis à la fonction de prédiction. |
| `cnn_inference_duration_seconds` | Histogram | Durée des appels réussis à la fonction de prédiction, en secondes. |

Un middleware compte les requêtes de l’API. Il exclut `/metrics` pour éviter que
les collectes de Prometheus gonflent l’activité HTTP affichée. Les routes non
identifiées sont regroupées sous `route_inconnue`.

La durée est mesurée avec `time.perf_counter()` autour de
`cnn.predict_image(file_path)`. Elle comprend le prétraitement de l’image et
l’exécution du modèle. Elle exclut le transfert HTTP du fichier, sa sauvegarde
initiale et l’écriture de la prédiction en base.

Les compteurs de prédictions et l’histogramme sont alimentés avant l’écriture en
base : une inférence peut donc être comptée comme réussie même si cet
enregistrement échoue ensuite. Une inférence qui lève une exception n’est pas
ajoutée à ces métriques de réussite.

Les métriques du processus Python et du ramasse-miettes sont également exposées
par la bibliothèque. Elles ne font pas partie des quatre panneaux sélectionnés.

## Les quatre panneaux du dashboard

### 1. Collecte des métriques de l’API

**Visualisation : Stat.**

```promql
up{job="cnn-api"}
```

Cette métrique est produite par Prometheus :

- `1` : la collecte de `/metrics` a réussi ;
- `0` : la collecte a échoué.

Elle permet de détecter une interruption de l’accès aux métriques. Elle ne
garantit pas que MySQL fonctionne ou que le modèle produit des résultats
corrects.

### 2. Temps moyen de prédiction

**Visualisation : Stat ; unité : secondes (`s`).**

```promql
sum(cnn_inference_duration_seconds_sum{job="cnn-api"})
/
sum(cnn_inference_duration_seconds_count{job="cnn-api"})
```

L’histogramme expose une somme des durées (`_sum`) et un nombre d’observations
(`_count`). Leur rapport donne la durée moyenne des prédictions réussies depuis
le démarrage du processus API. Par exemple, `0,170 s` correspond à environ
`170 ms`.

Cet indicateur suit la vitesse de traitement du modèle. Il ne mesure pas sa
précision. Avant toute prédiction, le rapport `0 / 0` est indéfini et peut
s’afficher comme `NaN` ou comme une absence de valeur exploitable.

La suggestion Grafana d’utiliser `rate()` n’invalide pas cette requête : ici,
l’objectif est une moyenne cumulée depuis le démarrage. Une moyenne limitée
aux cinq dernières minutes nécessiterait un autre calcul.

### 3. Nombre de prédictions réussies

**Visualisation : Stat.**

```promql
sum(cnn_inferences_total{job="cnn-api"})
```

Ce compteur suit l’utilisation du modèle et permet de vérifier qu’une nouvelle
inférence réussie est enregistrée. Sa valeur augmente d’une unité par appel
réussi à la fonction de prédiction, puis repart de zéro au redémarrage de l’API.
Ce n’est pas un comptage des lignes actuellement présentes dans MySQL.

### 4. Activité HTTP par statut

**Visualisation : Time series ; unité du calcul : requêtes par seconde.**

```promql
sum by (status) (
  rate(cnn_api_requests_total{job="cnn-api"}[5m])
)
```

`rate()` calcule le débit moyen sur les cinq minutes précédant chaque point du
graphique. Le regroupement par `status` permet de distinguer les réponses
réussies et les erreurs, notamment `200`, `405` et `503`.

Le résultat peut être décimal : il représente un débit, pas un nombre entier de
requêtes. Un statut jamais rencontré peut être absent. Il faut au moins deux
échantillons pour calculer le débit d’une série ; une requête supplémentaire
entre deux collectes permet d’en observer l’évolution.

## Période affichée et mise à jour

L’export actuel contient :

```json
"from": "now-30m",
"to": "now",
"autoRefresh": "30s"
```

Le dashboard affiche donc les **30 dernières minutes** et actualise ses
requêtes toutes les **30 secondes**. Prometheus collecte indépendamment les
métriques toutes les **15 secondes**.

Les requêtes des panneaux Stat sont exportées en mode plage temporelle. Leur
affichage retient la dernière valeur non vide de la période choisie. Sur une
période passée, cette valeur décrit donc cette période, pas l’état actuel.
Choisir une période plus courte ne transforme pas les compteurs et la moyenne
cumulée en statistiques limitées à cette période.

Une période absolue, par exemple le 9 octobre 2026, est utile pour étudier un
incident passé lorsque les mesures existent encore. Une période relative est
adaptée au suivi quotidien et évite de rester bloqué sur les dates d’un ancien
test.

Les couleurs des Stat correspondent actuellement aux seuils graphiques par
défaut. Elles ne constituent pas une validation de santé : lire la valeur et
l’état de la règle d’alerte, notamment lorsque `up = 0` ou qu’un panneau indique
`No data`.

## Alerte de collecte indisponible

La règle est exportée dans
[`monitoring/alertes_cnn.yml`](../e5-2026-cnn/monitoring/alertes_cnn.yml).

| Paramètre | Valeur enregistrée |
| --- | --- |
| Nom | `CNN - Collecte API indisponible` |
| Dossier | `CNN` |
| Groupe | `cnn-monitoring` |
| Requête A | `up{job="cnn-api"}` en mode instantané |
| Condition C | A inférieure à `1` |
| Intervalle d’évaluation | `30s` |
| Période d’attente (`for`) | `1m` |
| Absence de données | `NoData` |
| Erreur d’évaluation | `Error` |
| Pause | `false` : règle active |

L’alerte passe de **Normal** à **Pending** lorsque la condition devient vraie,
puis à **Firing / Alerting** si elle reste vraie pendant une minute. La durée
totale de détection dépend aussi des intervalles de collecte et d’évaluation.

Lorsque l’API est arrêtée mais que Prometheus fonctionne, `up` passe normalement
à `0`. Si Grafana ne reçoit aucune donnée ou ne peut pas exécuter la requête,
les états `NoData` et `Error` décrivent des situations différentes de ce seuil.

L’alerte est observable dans Grafana. Aucun serveur SMTP ni canal de
notification externe n’a été configuré et validé dans ce projet. L’export de la
règle ne sauvegarde pas les contact points et les politiques de notification.
Une notification reçue doit être testée séparément si un tel canal est ajouté.

## Vérification du dashboard et de l’alerte

### Vérifier les mesures du modèle

1. Choisir une période récente, par exemple **Last 30 minutes**.
2. Noter la valeur du compteur de prédictions.
3. Réaliser une prédiction dans le client Streamlit.
4. Attendre une actualisation : le compteur doit augmenter d’une unité et le
   temps moyen doit être défini. La collecte doit rester à `1`.

### Vérifier les statuts HTTP

Depuis un terminal, avec le port API par défaut :

```bash
curl -sS -o /dev/null -w "GET : %{http_code}\n" http://localhost:8081/predictions/
curl -sS -o /dev/null -w "POST : %{http_code}\n" -X POST http://localhost:8081/predictions/
```

Les résultats attendus sont `GET : 200` si la base est accessible et
`POST : 405`. Le POST provoque volontairement une erreur pour vérifier la
supervision ; le client corrigé continue à utiliser GET pour télécharger le
JSON.

Attendre environ 30 secondes, répéter les appels, puis consulter le graphique.
Les nouvelles observations entre les collectes doivent permettre de voir les
séries correspondant aux statuts rencontrés.

### Tester une interruption de l’API

Depuis le dossier applicatif :

```bash
docker compose --env-file ../.env stop web
```

Observer `up = 0`, puis **Pending** et **Firing** dans
**Alerting / Alerts & IRM → Alert rules**. Conserver une capture du déclenchement.

Redémarrer ensuite l’API :

```bash
docker compose --env-file ../.env start web
```

Après son démarrage, les collectes et les évaluations suivantes doivent ramener
`up` à `1` et l’alerte à **Normal**. Conserver aussi cette preuve de
rétablissement. Le démarrage de l’API recharge le modèle et remet ses compteurs
en mémoire à zéro.

## Sauvegarde et restauration du dashboard

### Mettre à jour l’export JSON

1. Enregistrer le dashboard dans Grafana avec la période relative souhaitée.
2. Ouvrir **Export → Export as code**.
3. Choisir JSON et activer **Share dashboard with another instance** si proposé.
4. Copier le résultat dans `monitoring/dashboard_cnn.json` et enregistrer.
5. Vérifier `timeSettings` : `now-30m`, `now` et `30s` pour la configuration
   décrite ici.

Le fichier actuel utilise le format `dashboard.grafana.app/v2`, exporté avec
Grafana 13.2.3. Utiliser cette version pour reproduire l’installation et vérifier
la compatibilité avant un import dans une autre version.

### Restaurer depuis le JSON

1. Configurer et tester la source Prometheus sur l’installation de destination.
2. Ouvrir **Dashboards → New → Import**.
3. Charger le fichier JSON, ou coller son contenu et cliquer sur **Load**.
4. Associer les requêtes à la source `prometheus` lorsqu’elle est demandée.
5. Pour une copie de test, utiliser le nom `Test restauration CNN` et un UID
   différent, par exemple `cnn-restauration-test`.
6. Cliquer sur **Import**, puis vérifier les quatre panneaux.

L’export conserve le nom de ressource `ad4snmn`. Lors d’un test sur la même
installation, changer l’UID dans l’écran d’import et annuler toute proposition
d’écraser l’original. Les réglages et les requêtes doivent être retrouvés dans
la copie ; les mesures affichées proviennent toujours de Prometheus.

Voir les procédures officielles d’[export](https://grafana.com/docs/grafana/latest/visualizations/dashboards/share-dashboards-panels/#export-a-dashboard-as-code)
et d’[import d’un dashboard](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/import-dashboards/).

## Restauration de l’alerte sur une nouvelle installation

Cette procédure concerne une installation où la règle exportée est absente.
L’export actuel référence la source Prometheus par l’UID `fg0osy1dyvklcc`.
Relever l’UID de la nouvelle source dans l’URL de sa fiche Grafana et adapter
`datasourceUid` dans le YAML si nécessaire. Conserver les références `__expr__`,
qui désignent les expressions internes de Grafana.

À côté de `docker-compose.yml`, créer un fichier
`docker-compose.restore-alertes.yml` :

```yaml
services:
  grafana:
    volumes:
      - ./monitoring/alertes_cnn.yml:/etc/grafana/provisioning/alerting/alertes_cnn.yml:ro
```

Recréer Grafana avec cette configuration complémentaire :

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.restore-alertes.yml up -d --no-deps --force-recreate grafana
```

Vérifier les logs et la présence de la règle :

```bash
docker compose --env-file ../.env logs --tail=50 grafana
```

Une règle chargée par fichier est gérée dans ce fichier, puis rechargée au
redémarrage ; elle n’est pas éditable dans l’interface comme une règle créée
manuellement. Une ressource déjà présente peut entrer en conflit avec l’import.
Voir le [provisionnement officiel des alertes par fichier](https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/).

## Conservation des mesures et limites

| Élément | Stockage | Comportement |
| --- | --- | --- |
| Compteurs et durées de l’API | Mémoire du processus API | Remis à zéro au redémarrage de l’API. |
| Mesures collectées par Prometheus | Volume Docker `prometheus_data` | Conservées après recréation du conteneur utilisant le même volume, jusqu’à expiration ou suppression. |
| Réglages Grafana | Volume Docker `grafana_data` | Sources, dashboards et alertes créés dans cette installation. |
| Exports JSON et YAML | Dossier `monitoring/` du projet | Définitions réutilisables, sans historique des mesures. |

Aucune durée de rétention particulière n’est configurée dans Compose.
Prometheus applique donc sa valeur par défaut de **15 jours**. La persistance du
volume n’empêche pas l’expiration des anciennes mesures. Prolonger la rétention
ne recrée pas les données déjà supprimées.
Voir la [documentation du stockage Prometheus](https://prometheus.io/docs/prometheus/latest/storage/#operational-aspects).

La conservation d’un historique plus long nécessite une configuration de
rétention adaptée et une sauvegarde distincte du stockage Prometheus. Le JSON
du dashboard et le YAML de l’alerte ne sauvegardent pas ce stockage.

Les mesures du modèle suivent son activité et sa durée de traitement. Mesurer
sa précision nécessiterait des étiquettes de référence et une comparaison aux
prédictions. Enfin, l’instrumentation actuelle utilise un seul processus API,
conformément à la commande Uvicorn de Compose ; une exécution avec plusieurs
workers demanderait une gestion adaptée des métriques.

## Dépannage

| Symptôme | Vérification et action |
| --- | --- |
| `No data` sur tous les panneaux | Vérifier une période relative récente, la source Grafana avec **Save & test**, puis les services Prometheus et API. |
| Cible Prometheus `DOWN` avec HTTP 404 | Vérifier `metrics_path: /metrics` ; `/metrics_path` n’est pas la route de l’API. |
| `up = 0` | Examiner les logs de `web`, l’accès à `/metrics` et le réseau Docker. |
| `No data` sur une période ancienne | Interroger Prometheus sur cette période et vérifier la rétention ; changer les dates ne restaure pas les mesures expirées. |
| Moyenne indéfinie après démarrage | Réaliser une prédiction réussie, puis attendre la collecte et l’actualisation. |
| Graphique HTTP vide ou à zéro | Générer des requêtes entre plusieurs collectes ; un statut jamais rencontré n’a pas nécessairement de série. |
| GET `/predictions/` renvoie 503 | Vérifier MySQL et les logs de l’API ; cet échec est distinct du ticket 405. |
| Alerte `Error` après restauration | Vérifier l’accès à Prometheus et la correspondance du `datasourceUid` dans le YAML. |

Commandes utiles depuis le dossier applicatif :

```bash
docker compose --env-file ../.env ps
docker compose --env-file ../.env logs --tail=50 web prometheus grafana
```

Après modification de `prometheus.yml`, recréer uniquement son service :

```bash
docker compose --env-file ../.env up -d --no-deps --force-recreate prometheus
```

## État des validations et preuves

Les validations manuelles réalisées pendant le projet ont confirmé le
fonctionnement des quatre panneaux, le passage de l’alerte à **Firing** lors de
l’arrêt de l’API et l’import du JSON dans une copie du dashboard.

La consultation directe de Prometheus pour la journée du 9 octobre 2026 a
retourné `status: success` et `result: []` pour les mesures `up` de `cnn-api`.
Cette absence a été constatée ; l’expiration de la rétention est une explication
probable, sans preuve d’une cause unique.

Le retour de l’alerte à **Normal** après redémarrage doit être consigné avec sa
capture. La restauration de l’alerte par le fichier Compose complémentaire est
une procédure documentée ; elle n’a pas été exécutée dans le cadre de la
rédaction de cette documentation. L’import d’un dashboard dans l’installation
actuelle ne constitue pas à lui seul un test complet sur une installation neuve.

Pour le rapport, conserver les captures des quatre panneaux, de la cible
Prometheus **UP**, de l’alerte **Firing**, de son rétablissement et du dashboard
restauré. Relancer les vérifications après le déploiement final avant de
conclure sur la version livrée.
