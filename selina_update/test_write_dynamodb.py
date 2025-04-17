import boto3
import json
from datetime import datetime
import asyncio
AWS_REGION = "us-east-2"
session = boto3.Session(region_name=AWS_REGION)
dynamodb_resource = session.resource("dynamodb")
table = dynamodb_resource.Table("chat_history")
async def save_to_dynamodb(user_id, session_id, chat_history):
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "history": json.dumps(chat_history),
    }
    print("Writing to DynamoDB:", data)
    await asyncio.to_thread(table.put_item, Item=data)
async def test_write():
    chat_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there! How can I help?"}
    ]
    await save_to_dynamodb("test_user", "session_python", chat_history)
asyncio.run(test_write())
