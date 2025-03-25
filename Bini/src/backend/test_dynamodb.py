import boto3
import json
import asyncio
from datetime import datetime

# Set AWS Region
AWS_REGION = "us-east-2"

# Initialize DynamoDB Resource & Connect to Table
session = boto3.Session(region_name=AWS_REGION)
dynamodb_resource = session.resource("dynamodb")
table = dynamodb_resource.Table("chat_history")  # Connect to existing table

# Function to Write Chat History to DynamoDB
async def save_to_dynamodb(user_id, session_id, chat_history):
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "history": json.dumps(chat_history),
    }
    
    print("Saving to DynamoDB:", data)
    await asyncio.to_thread(table.put_item, Item=data)

# Function to Delete Chat History from DynamoDB
async def delete_chat_history(user_id, session_id):
    try:
        await asyncio.to_thread(table.delete_item, Key={"user_id": user_id, "session_id": session_id})
        print(f"Deleted chat history for user_id: {user_id}, session_id: {session_id}")
    except Exception as e:
        print(f"❌ Error deleting chat history: {str(e)}")

# Test Writing Chat History
async def test_write():
    chat_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there! How can I assist?"}
    ]
    await save_to_dynamodb("test_2", "session_12345", chat_history)

# Test Deleting Chat History
async def test_delete():
    await delete_chat_history("test_2", "session_12345")

# Run Tests (Comment out test_read since we don't want retrieval)
asyncio.run(test_write())  # Saves data
asyncio.run(test_delete())  # Deletes data

print("✅ Successfully saved and deleted chat history in DynamoDB!")