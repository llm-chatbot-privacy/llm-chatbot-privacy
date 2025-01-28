import json
import boto3
from datetime import datetime
import os
from openai import OpenAI, APIError, RateLimitError
import time
import logging


# AWS DynamoDB setup
dynamodb_resource = boto3.resource('dynamodb', region_name="us-east-2")
table = dynamodb_resource.Table('llm_chat_v1')

# OpenAI API key setup
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    response = table.get_item(Key={"session_id": session_id, "user_id": user_id})
    if "Item" in response:
        return json.loads(response["Item"]["history"])
    return []

# Function to generate a response using OpenAI API
# Configure logging
logging.basicConfig(level=logging.INFO)

def generate_response(user_message, chat_history):
    try:
        # Retry logic for transient errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Format chat history for OpenAI
                messages = [{"role": msg["role"], "content": msg["content"]} for msg in chat_history]
                messages.append({"role": "user", "content": user_message})

                # Call OpenAI's ChatCompletion API
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",  # Use "gpt-4" if needed
                    messages=messages
                )

                # Validate and extract the response
                if response.choices and len(response.choices) > 0:
                    llm_response = response.choices[0].message.content
                    if llm_response is not None:
                        return llm_response
                    else:
                        raise ValueError("Response format is invalid: 'content' missing in message")
                else:
                    raise ValueError("Response format is invalid: 'choices' missing or empty")

            except Exception as e:  # Catch all exceptions
                logging.warning(f"An error occurred: {e}. Retrying attempt {attempt + 1}/{max_retries}...")
                time.sleep(2 ** attempt)  # Exponential backoff

        # If all retries fail, raise an exception
        raise Exception("Max retries exceeded. Unable to generate a response.")

    except Exception as e:
        logging.error(f"Error in generate_response: {e}")
        raise


# Lambda handler for testing DynamoDB access
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