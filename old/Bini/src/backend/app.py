# from flask import Flask, jsonify

# app = Flask(__name__)

# @app.route("/health", methods=["GET"])
# def health_check():
#     return jsonify({"status": "ok"}), 200

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5002)



from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import json

app = FastAPI()

# Health Check Endpoint
@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# Sample model for chat messages
class ChatMessage(BaseModel):
    user_id: str
    session_id: str
    message: str


# Chat API Example (Replace with your actual logic)
@app.post("/chat")
def process_chat(message: ChatMessage):
    # Simulate AI processing
    response = {
        "user_id": message.user_id,
        "session_id": message.session_id,
        "history": [
            {"role": "user", "content": message.message},
            {"role": "assistant", "content": "This is a generated AI response!"}
        ],
    }
    return response


# Run FastAPI
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)