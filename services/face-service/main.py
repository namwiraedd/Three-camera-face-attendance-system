import os, io, base64, json, hashlib, time
from fastapi import FastAPI, UploadFile, File, HTTPException
import face_recognition
import numpy as np
import psycopg2
import redis
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
THRESH = float(os.getenv("FACE_MATCH_THRESHOLD", "0.55"))

# simple DB connection (blocking; replace pool in prod)
conn = psycopg2.connect(DB_URL)
rcli = redis.from_url(REDIS_URL)
app = FastAPI(title="Face Service - GateKeeper")

# minimal models
class EnrollIn(BaseModel):
    user_id: str
    name: str

@app.post("/enroll")
async def enroll(user: EnrollIn, file: UploadFile = File(...)):
    """
    Receive a high-quality enrollment image at kiosk.
    Stores embedding and sample image in DB.
    """
    img_bytes = await file.read()
    np_arr = np.frombuffer(img_bytes, np.uint8)
    import cv2
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="invalid image")
    # detect face and compute embedding
    face_locations = face_recognition.face_locations(img)
    if not face_locations:
        raise HTTPException(status_code=400, detail="no face detected")
    encodings = face_recognition.face_encodings(img, face_locations)
    if not encodings:
        raise HTTPException(status_code=400, detail="failed to encode")
    embedding = encodings[0].tolist()
    # save to DB
    with conn.cursor() as cur:
        cur.execute("INSERT INTO users (id, name, embedding, enrolled_at) VALUES (%s,%s,%s,now()) ON CONFLICT (id) DO UPDATE SET embedding=%s, enrolled_at=now()",
                    (user.user_id, user.name, json.dumps(embedding), json.dumps(embedding)))
        conn.commit()
    return {"ok": True, "user_id": user.user_id}

@app.post("/detect")
async def detect(camera_id: str, file: UploadFile = File(...)):
    """
    Receives a frame from a camera (entry/exit) and attempts recognition.
    Returns matched user_id or fallback code.
    """
    img_bytes = await file.read()
    np_arr = np.frombuffer(img_bytes, np.uint8)
    import cv2
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="invalid image")
    face_locations = face_recognition.face_locations(img)
    if not face_locations:
        return {"matched": False, "reason": "no_face"}
    encodings = face_recognition.face_encodings(img, face_locations)
    if not encodings:
        return {"matched": False, "reason": "no_encoding"}
    probe = encodings[0]
    # naive linear scan over DB users (fine for small deployments)
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, embedding FROM users WHERE embedding IS NOT NULL")
        rows = cur.fetchall()
    best = None
    best_score = 1.0
    for uid, name, emb_json in rows:
        emb = np.array(json.loads(emb_json))
        dist = np.linalg.norm(emb - probe)
        if dist < best_score:
            best_score = float(dist); best = (uid, name)
    if best and best_score <= THRESH:
        user_id, name = best
        # log event: entry/exit toggle depending on camera type
        with conn.cursor() as cur:
            cur.execute("INSERT INTO logs (user_id, name, camera_id, matched, score, ts) VALUES (%s,%s,%s,%s,%s,now())",
                        (user_id, name, camera_id, True, best_score))
            conn.commit()
        # publish to redis for realtime dashboard & gate controller
        payload = json.dumps({"event":"recognized","user_id":user_id,"name":name,"camera_id":camera_id})
        rcli.publish("events", payload)
        return {"matched": True, "user_id": user_id, "name": name, "score": best_score}
    else:
        # store failed image for audit / manual review
        with conn.cursor() as cur:
            cur.execute("INSERT INTO logs (user_id, name, camera_id, matched, score, ts, raw_image) VALUES (%s,%s,%s,%s,%s,now(),%s)",
                        (None, None, camera_id, False, None, psycopg2.Binary(img_bytes)))
            conn.commit()
        payload = json.dumps({"event":"unrecognized","camera_id":camera_id})
        rcli.publish("events", payload)
        return {"matched": False, "reason": "no_match"}

@app.get("/health")
def health():
    return {"ok": True}
