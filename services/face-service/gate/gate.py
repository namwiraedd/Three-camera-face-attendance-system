import os, time, json
import redis, requests
from dotenv import load_dotenv
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")
API_URL = f"http://{os.getenv('API_HOST','api')}:8000"
GATE_PIN = int(os.getenv("GATE_PIN","17"))
MOCK = os.getenv("MOCK_GPIO","true").lower() == "true"

r = redis.from_url(REDIS_URL)

# GPIO helper (mock when not on Pi)
class Gate:
    def __init__(self, pin):
        self.pin = pin
        self.state = False
    def open(self):
        print("[GATE] OPEN")
        self.state = True
        time.sleep(2)  # keep open for 2s
        self.close()
    def close(self):
        print("[GATE] CLOSE")
        self.state = False

gate = Gate(GATE_PIN)

pubsub = r.pubsub()
pubsub.subscribe("events")
print("Gate controller subscribed to events channel")

for msg in pubsub.listen():
    if msg['type'] != 'message': continue
    payload = json.loads(msg['data'])
    print("Event:", payload)
    if payload.get("event") == "recognized":
        # simple policy: open gate
        print("Recognized user:", payload.get("name"))
        gate.open()
    elif payload.get("event") == "unrecognized":
        # do nothing - fallback via API (qr / fingerprint)
        print("Unrecognized at camera", payload.get("camera_id"))
    # else ignore
