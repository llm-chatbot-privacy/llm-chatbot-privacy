import json
from gradio_app_v3 import lambda_handler

# Mock event payload
event = {
    "body": json.dumps({
        "session_id": "test_session_001",
        "user_id": "test_user_001",
        "user_message": "Hello, chatbot!",
        "chat_history": [{"role": "user", "content": "Hi!"}]
    })
}

# Mock context (can be empty for local testing)
context = {}

# Call the Lambda function locally
response = lambda_handler(event, context)

# Print the response
print("Lambda Response:")
print(json.dumps(response, indent=2))
