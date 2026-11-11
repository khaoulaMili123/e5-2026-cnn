# Counter compte les evenements (les requetes ou les inferences)
#Histogram enregistre des mesures comme les durées de calcul
from prometheus_client import Counter, Histogram

# Compte les requetes traitées par l'API 
REQUETES_HTTP = Counter(
    "cnn_api_requests_total",
    "Nombre de requêtes HTTP traitées par l'API",
    ["method", "route", "status"],
)

# Compte les appels réussis à la fct de prédiction 
INFERENCES_REUSSIES = Counter(
    "cnn_inferences_total",
    "Nombre de prédictions réalisées avec succès par le modèle",
)

# Enregistrer la durée des prédictions reussies en secondes
# La mesure comprendra le pretraitement de l'image et le calcul du modele
DUREE_INFERENCE = Histogram(
    "cnn_inference_duration_seconds",
    "Durée des prédictions réussies, prétraitement compris, en secondes",
)