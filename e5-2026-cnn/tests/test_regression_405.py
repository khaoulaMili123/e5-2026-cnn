# Fournit les outils pour écrire les tests et vérifier les résultats 
import unittest

#Permet de rendre le dossier client accessible pendant le test
import sys

# Permet de construire le chemin vers le fichier app.py
from pathlib import Path

#Permet de simuler les appels HTTP
from unittest.mock import patch #permet de remplacer temporairement un objet par un faux objet (un mock)

# Fournit l'exception HTTPError pour simuler l'erreur 405
import requests

# Exécuter l'appli Streamlit et permet d'examiner son affichage
from streamlit.testing.v1 import AppTest 

# Remonte jusqu'au dossier du projet, puis rejoint le dossier client.
DOSSIER_CLIENT = Path(__file__).resolve().parents[1] / "client"

# Designe le fichier de l'appli à exécuter pendant le test
CHEMIN_APP = DOSSIER_CLIENT / "app.py"

# Regrouper les tests qui protègent contre le retour du bug 405
class TestRegression405(unittest.TestCase):

    #Vérifier que la récuperation des predictions affiche le bouton JSON
    def test_affiche_bouton_telechargement(self):

        # Préparer les prédictions que notre fausse API renverra.
        predictions_simulees = [
            {
                "id": 1,
                "image": "foret.jpg",
                "label": "forêt",
                "commentaire": "OK",
                "modele": "CNN",
            }
        ]

        # Préparer les imports du client et simule les deux méthodes HTTP.
        with (
            # Permet à app.py d'importer config.p et api_client.py.
            patch.object(sys, "path", [str(DOSSIER_CLIENT)] + sys.path),

            # Remplace les vrais appels GET et POST pendant le test
            patch("requests.get") as faux_get,
            patch("requests.post") as faux_post,
        ):
            # GET simule une réponse réussie contenant les prédictions.
            faux_get.return_value.status_code = 200
            faux_get.return_value.raise_for_status.return_value = None
            faux_get.return_value.json.return_value = predictions_simulees

            # POST simule la méthode refusée par L'API
            faux_post.return_value.status_code = 405
            faux_post.return_value.raise_for_status.side_effect = (
                requests.HTTPError("405 Method Not Allowed")
            )

            # Exécute app.py avec les réponses HTTP simulées
            app = AppTest.from_file(CHEMIN_APP).run(timeout=10)

        # Vérifier que l'appli s'est exécute sans exception
        self.assertEqual(len(app.exception), 0)

        #Vérifier que la récupération utilise GET une seule fois.
        faux_get.assert_called_once()

        #Vérifie qu'aucun POST n'a été envoyé à l'ouverture
        faux_post.assert_not_called()

        # Vérifier qu'aucune erreur n'apparait dans la barre laterale
        self.assertEqual(len(app.sidebar.error), 0)

        #Recherche les boutons de telechargement dans la barre laterale
        boutons = app.sidebar.get("download_button")

        #Vérifier qu'un bouton existe et qu'il porte le libellé attendu
        self.assertEqual(len(boutons), 1)
        self.assertEqual(boutons[0].proto.label, "Télécharger le JSON")
