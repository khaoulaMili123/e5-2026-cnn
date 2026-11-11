import requests

#Permet d'enregistrer les événements et les erreurs de récupération
import logging

#Permet de mesurer la durée de la récupération des prédictions
import time

# Crée le journal utilisé par ce module
logger = logging.getLogger(__name__)

def recuperer_predictions(url):
    #Mémorise le pts de départ pour mesurer la durée de l'opération
    debut = time.perf_counter() #fournit un compteur en secondes.

    #Enregistre le début de la récupération et l'adresse appelée
    logger.info("Début de récupération des prédictions : url=%s", url)

    # Tente de récupérer les prédictions
    try:
        reponse = requests.get(url, timeout=(5,30))
        reponse.raise_for_status()
        predictions = reponse.json(
        )

    # Enregistre les erreurs rencontrées pendant la récupération
    except requests.exceptions.RequestException as erreur:
        duree = time.perf_counter() - debut

        logger.error(
            "Échec de récupération : url=%s durée=%.3f s erreur=%s",
            url,
            duree,
            erreur,
        )

        # Transmet l'exception à app.py après l'avoir enregistrée
        raise

    # Calcule la durée depuis le début de la récupération.
    duree = time.perf_counter() - debut

    # Enregistre la réussite, le statut HTTp et la durée en secondes
    logger.info(
        "Récupération réussie : statut=%s durée=%.3f s",
        reponse.status_code,
        duree,
    )

    #Renvoie les prédictions au code qui appelle la fct
    return predictions 
