from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import logging
import shutil
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, Response 
# Fournit les mesures et le format attendu par Prometheus.
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from mysql.connector import Error as DatabaseError
from PIL import Image, UnidentifiedImageError
from app.modele import cnn
from app.config import UPLOAD_FOLDER
from app.bdd.service import Service_Prediction
from app.bdd.prediction import Prediction
import time #Pour mesurer la durée de la predictions

#Importe le compteur des requetes defini dans monitoring.py
from app.monitoring import (
    REQUETES_HTTP,
    INFERENCES_REUSSIES,
    DUREE_INFERENCE,
)
@asynccontextmanager
async def lifespan(app):
    Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    cnn.get_model()
    yield


app = FastAPI(lifespan=lifespan)

# Observe les requetes HTTP pour alimenter le compteur Prometheus
@app.middleware("http")
async def compter_requetes(request: Request, call_next):

    #Exclut la collecte des metriques pour mesurer l'activite de l'appli
    if request.url.path.rstrip("/") == "/metrics":
        return await call_next(request)
    
    # Si le traitement déclenche une exception non interceptée,
    # la requête sera comptée comme une erreur serveur.
    statut = 500
    try:
        # Laisse l'API traiter la requête et récupère sa réponse.
        reponse = await call_next(request)

        # Retient le statut réellement renvoyé : 200, 405, 503, etc.
        statut = reponse.status_code
        return reponse

    finally:
        # Utilise le modèle de route défini par FastAPI.
        # Les adresses inconnues sont regroupées sous un même libellé.
        route = request.scope.get("route")
        chemin = getattr(route, "path", "route_inconnue")

        # Ajoute une requête au compteur correspondant.
        REQUETES_HTTP.labels(
            method=request.method,
            route=chemin,
            status=str(statut),
        ).inc()


# Fournit les mesures que Prometheus viendra récupérer.
@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(
        content=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )

@app.exception_handler(DatabaseError)
async def database_error(request: Request, exc: DatabaseError):
    logging.getLogger(__name__).error("Erreur MySQL : %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Base de données indisponible"})


@app.get("/")
def index():
    return "API Prediction!"

@app.post("/predictions/satellite/")
def upload_image(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        file.file.close()
        raise HTTPException(status_code=400, detail="Format non supporté")
    file_path = Path(UPLOAD_FOLDER) / f"{uuid4().hex}{suffix}"
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        try:
            with Image.open(file_path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise HTTPException(status_code=400, detail="Image invalide") from exc

        #Demarre la mesure juste avant la prediction
        debut_inference = time.perf_counter()

        #Prepare l'image et execute le modele pour obtenir sa classe
        label = cnn.predict_image(file_path)

        #Enregistre le temps ecoulé aprés une prediction reussie 
        duree_inference = time.perf_counter() - debut_inference
        DUREE_INFERENCE.observe(duree_inference) #enregistre une durée

        #Ajoute une prediction reussie au compteur
        INFERENCES_REUSSIES.inc() #inc() augmente un compteur.
        
        prediction = Prediction(image=str(file_path), label=label, commentaire="OK", modele="CNN")
        Service_Prediction.sauvegarder_prediction(prediction)
        return {"prediction": prediction}
    except Exception:
        file_path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()


@app.get("/predictions/", response_model=list[Prediction])
def list_predictions():
    return Service_Prediction.lister_predictions()
