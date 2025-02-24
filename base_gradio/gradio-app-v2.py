import json
import boto3
from datetime import datetime
import openai

# AWS DynamoDB setup
dynamodb_resource = boto3.resource('dynamodb', region_name="us-east-2")
table = dynamodb_resource.Table('llm_chat_v1')

# OpenAI API key setup
openai.api_key = os.getenv("OPENAI_API_KEY")

# Function to save conversation history to DynamoDB
def save_to_dynamodb(session_id, user_id, chat_history):
    data = {
        "session_id": session_id,
        "user_id": user_id,  # Include the pre-assigned user identifier
        "timestamp": datetime.utcnow().isoformat(),
        "history": json.dumps(chat_history),
    }
    table.put_item(Item=data)

# Function to retrieve conversation history from DynamoDB
def get_from_dynamodb(session_id, user_id):
    # Use both session_id and user_id for the query if needed
    response = table.get_item(Key={"session_id": session_id, "user_id": user_id})
    if "Item" in response:
        return json.loads(response["Item"]["history"])
    return []

# Function to generate a response using OpenAI API
def generate_response(user_message, chat_history):
    # Format chat history for OpenAI
    messages = [{"role": msg["role"], "content": msg["content"]} for msg in chat_history]
    messages.append({"role": "user", "content": user_message})

    # Call OpenAI's ChatCompletion API
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # Use "gpt-4" if needed
        messages=messages
    )

    # Extract assistant's response
    llm_response = response['choices'][0]['message']['content']
    return llm_response

# AWS Lambda handler
def lambda_handler(event, context):
    try:
        # Parse the incoming request
        body = json.loads(event['body'])
        session_id = body.get("session_id")
        user_id = body.get("user_id")  # Extract the pre-assigned unique identifier
        user_message = body.get("user_message")
        chat_history = body.get("chat_history", [])
        
        if not session_id or not user_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "session_id and user_id are required"})
            }
        
        # Get existing chat history from DynamoDB
        if not chat_history:
            chat_history = get_from_dynamodb(session_id, user_id)
        
        # Generate response using OpenAI API
        llm_response = generate_response(user_message, chat_history)
        
        # Update chat history
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": llm_response})
        
        # Save updated chat history to DynamoDB
        save_to_dynamodb(session_id, user_id, chat_history)

        # Return the response
        return {
            "statusCode": 200,
            "body": json.dumps({
                "session_id": session_id,
                "user_id": user_id,
                "chat_history": chat_history
            })
        }
    except Exception as e:
        # Handle exceptions and return error response
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
