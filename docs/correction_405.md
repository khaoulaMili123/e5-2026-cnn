# Correction du ticket 1 — Erreur HTTP 405 lors du téléchargement JSON

## Problème observé

L’application permet de classifier des images satellites et de consulter les prédictions enregistrées. La barre latérale doit proposer un bouton « Télécharger le JSON » pour récupérer ces prédictions dans un fichier `predictions.json`.

Avant la correction, une erreur apparaît à la place de ce bouton. Les logs de l’API montrent la requête suivante :

```text
POST /predictions/ HTTP/1.1" 405 Method Not Allowed
```

Le code HTTP `405` signifie que la méthode utilisée n’est pas autorisée pour cette route.

## Recherche de la cause avec le débogueur

Le client envoyait la requête suivante dans `client/app.py` :

```python
pourfichier = requests.post(API_PREDICTIONS_URL, timeout=(5, 30))
```

Or, dans `api/app/main.py`, la consultation des prédictions est définie avec `@app.get("/predictions/")`. L’adresse appelée était correcte, mais la méthode envoyée était `POST` au lieu de `GET`.

Pour suivre le traitement, le client a été lancé avec le débogueur Python de VS Code. Un premier point d’arrêt a été placé sur `pourfichier.raise_for_status()`, après la réception de la réponse. L’inspection de `pourfichier.request.method` et de `pourfichier.status_code` permet de constater la méthode `POST` et le statut `405`.

L’exécution de `raise_for_status()` déclenche alors une exception `requests.HTTPError`. Un second point d’arrêt, placé sur `st.sidebar.error(...)`, permet de lire son message avec `str(e)`.

Le programme passe dans le bloc `except` avant d’atteindre `st.sidebar.download_button(...)`. Cela explique pourquoi l’erreur s’affiche et pourquoi le bouton n’est pas créé.

## Correction réalisée

La récupération utilise désormais la méthode `GET`. Elle a été isolée dans la fonction `recuperer_predictions(url)`, située dans `client/api_client.py`, afin de pouvoir la tester séparément de l’interface :

```python
def recuperer_predictions(url):
    reponse = requests.get(url, timeout=(5, 30))
    reponse.raise_for_status()
    return reponse.json()
```

La fonction envoie la requête, vérifie le statut HTTP, puis renvoie les données JSON. Le délai d’attente est conservé. En cas d’erreur HTTP, elle laisse remonter l’exception vers le client.

Dans `client/app.py`, le bloc de téléchargement appelle maintenant cette fonction :

```python
predictionsjson = recuperer_predictions(API_PREDICTIONS_URL)
```

Les données sont ensuite converties en JSON et transmises au bouton de téléchargement. Le bloc `except` conserve l’affichage des erreurs lorsqu’une récupération échoue.

Le Dockerfile du client inclut aussi le nouveau module :

```dockerfile
COPY app.py config.py api_client.py ./
```

## Tests unitaires

Deux tests ont été ajoutés dans `tests/test_api_client.py`. Ils utilisent `unittest` et `unittest.mock.patch` pour remplacer l’appel HTTP par une réponse simulée.

| Test | Vérifications |
| --- | --- |
| `test_retourne_predictions` | La fonction renvoie les données attendues et appelle GET une seule fois, avec l’URL fournie et `timeout=(5, 30)`. |
| `test_propage_erreur_http` | La fonction transmet une exception `HTTPError` déclenchée par `raise_for_status()` et ne tente pas de lire le JSON après cet échec. |

Le second test simule une erreur HTTP. Il ne vérifie pas les méthodes autorisées par la vraie API.

## Test de régression

Le test `test_affiche_bouton_telechargement`, dans `tests/test_regression_405.py`, exécute le véritable client avec `streamlit.testing.v1.AppTest`. Les appels réseau sont simulés : GET fournit des prédictions et POST provoque une erreur HTTP 405 lors de la vérification du statut.

Le test vérifie que :

- l’application s’exécute sans exception non interceptée ;
- GET est appelé une seule fois et aucun POST n’est envoyé à l’ouverture ;
- aucune erreur n’apparaît dans la barre latérale ;
- un bouton de téléchargement portant le libellé « Télécharger le JSON » est présent.

La capacité du test à détecter le retour du bug a été vérifiée en remplaçant temporairement GET par POST dans `api_client.py`. Le test de régression échoue avec cette modification. Après restauration de GET, les trois tests passent.

## Exécution et résultat des tests

Les commandes suivantes s’exécutent depuis le dossier `e5-2026-cnn/` situé à l’intérieur du dépôt, celui qui contient `docker-compose.yml`, `client/`, `api/` et `tests/`.

Avec l’environnement virtuel Python activé et les dépendances du client installées :

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Résultat confirmé lors de la validation :

```text
Ran 3 tests
OK
```

Pour exécuter uniquement le test de régression :

```bash
python -m unittest discover -s tests -p "test_regression_405.py" -v
```

Ces tests ne nécessitent ni Docker, ni l’API, ni MySQL, puisque les appels HTTP sont simulés. Ils vérifient la récupération et la présence du bouton. Le téléchargement effectif du fichier et l’accès à la base réelle nécessitent une vérification dans le navigateur.

## Vérification de la version Docker

Après les modifications du client et de son Dockerfile, reconstruire et démarrer le client depuis le dossier Compose :

```bash
docker compose --env-file ../.env up --build -d client
```

Ouvrir `http://localhost:8501`, actualiser la page et vérifier la présence du bouton. Télécharger `predictions.json` et vérifier que son contenu est un JSON valide. Une liste vide `[]` est un résultat valide lorsque la récupération ne renvoie aucune prédiction.

Les nouvelles requêtes de récupération doivent apparaître dans les logs sous la forme `GET /predictions/` avec un statut `200` lorsque la base est accessible :

```bash
docker compose --env-file ../.env logs --since=2m web
```

## Incident d’environnement rencontré pendant la validation

Un problème distinct a également provoqué des réponses `503 Service Unavailable`. L’API signalait `Unknown MySQL server host 'db'`, et le conteneur MySQL CNN n’était connecté à aucun réseau. Le rattachement au réseau échouait à cause du port hôte `3306`, déjà occupé par le conteneur `trading_db`.

Le conteneur `trading_db`, devenu inutile, a été arrêté et supprimé. Le conteneur MySQL CNN a ensuite été recréé. Cette intervention concerne l’environnement Docker ; la correction du ticket 405 reste le remplacement de POST par GET et sa protection par les tests.

## Éléments à conserver pour le rapport

- Capture de l’erreur initiale et de la requête POST avec le statut 405.
- Captures du débogueur montrant la réponse HTTP et l’exception interceptée.
- Résultat des trois tests réussis.
- Échec du test de régression après réintroduction temporaire de POST.
- Capture du bouton et vérification du JSON téléchargé lors du contrôle manuel.

Les informations sur le commit, la fusion et le dashboard seront documentées lors des étapes correspondantes du projet.
