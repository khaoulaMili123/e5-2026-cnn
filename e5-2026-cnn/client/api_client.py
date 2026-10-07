import requests

def recuperer_predictions(url):
    reponse = requests.get(url, timeout=(5, 30))
    reponse.raise_for_status()
    return reponse.json()

