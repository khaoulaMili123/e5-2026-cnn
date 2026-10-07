import unittest
# Importe patch pour simuler l'appel à l'API pendant le test.
from unittest.mock import patch
from client.api_client import recuperer_predictions

#Permet d'utiliser l'exception HTTPError pour simuler une erreur de l'api
import requests

# unittest.TestCase fournit les outils pour vérifier les résultats.
class TestRecupererPredictions(unittest.TestCase):

    #Le nom commence par test_ pour que unittest reconnaisse ce test.
    def test_retourne_predictions(self):

        #Voici les données que notre fausse API devra renvoyer.
        predictions_attendues = [{"id": 1, "label": "forêt"}]

        # Remplace temporairement requests.get paar une simulation
        with patch("client.api_client.requests.get") as faux_get:
            
            # Preparer la reponse que l'appel GET simulé va renvoyer
            fausse_reponse = faux_get.return_value

            # Simule une réponse réussie : aucune exception HTTP
            fausse_reponse.raise_for_status.return_value = None
           
            # Quand la fct appelera json() elle recevra notre liste.
            fausse_reponse.json.return_value = predictions_attendues

            # Adresse utilisée pour le test : aucun appel réseau réel.
            url = "http://api-test/predictions/"

            # Exécute la fct avec la réponse simulée.
            resultat = recuperer_predictions(url)

            # Verifier que la fct renvoie les données attendues.
            self.assertEqual(resultat, predictions_attendues) #compare le résultat obtenu avec le résultat attendu

            # Verifie que GET a été appelé ne seule fois,
            # avec la bonne URL et le délai d'attente prévu.
            faux_get.assert_called_once_with(url, timeout=(5, 30))   

    #Verifie que la fct transmet l'erreur HTTP au code qui l'appelle
    def test_propage_erreur_http(self):

        #Simule l'appel GET pour éviter une vraie requete reseau 
        with patch("client.api_client.requests.get") as faux_get:
            fausse_reponse = faux_get.return_value

            # Lors de la verification HTTP, declenche une exception simulé
            fausse_reponse.raise_for_status.side_effect = requests.HTTPError(
                "405 Method Not Allowed"
            )

            # Le test réussit si la fct déclenche bien uneHTTPError
            with self.assertRaises(requests.HTTPError): #Vérifie que cette exception remonte bien
                recuperer_predictions("http://api-test/predictions/")

            # Apres l'erreur HTTP, la fct ne doit pas lire le JSON
            fausse_reponse.json.assert_not_called()  