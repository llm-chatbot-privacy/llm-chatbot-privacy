## UE-Lab API Documentation

### Overview

UE-Lab provides a RESTful API for chat functionality with DynamoDB storage and OpenAI integration.

### Base URL

```
http://localhost:5173/
```

    In production, this URL would change to a live server.

### Authentication

Simple user ID authentication is used for all endpoints.

### Data Storage

Messages and conversations are stored in DynamoDB with the following structure:

#### Messages Table (chat_History)

- Primary Key: `user_id` (Hash) + `timestamp` (Range)
- GSI: SessionIdIndex on `session_id` + `timestamp`
- Attributes:
  - `user_id` (String): User identifier
  - `timestamp` (String): ISO timestamp
  - `session_id` (String): Conversation identifier
  - `history` (String): JSON string of message history

### API Endpoints

#### Send Message

```http
POST /api/chat
Content-Type: application/json

{
  "userId": "string",
  "message": "string",
  "conversationId": "string"
}
```

Response:

```json
{
  "userId": "string",
  "history": [
    {
      "role": "user" | "assistant",
      "content": "string"
    }
  ]
}
```

#### Get Chat History - Useful for displaying a list of past conversations.

```http
GET /api/chat/:userId
```

Response:

```json
{
  "messages": [
    {
      "user_id": "string",
      "session_id": "string",
      "timestamp": "string",
      "history": [
        {
          "role": "user" | "assistant",
          "content": "string"
        }
      ]
    }
  ]
}
```

#### Get Conversation Messages - Useful for loading chat history in a UI.

```http
GET /api/chat/:userId/:conversationId
```

Response:

```json
{
  "messages": [
    {
      "user_id": "string",
      "session_id": "string",
      "timestamp": "string",
      "history": [
        {
          "role": "user" | "assistant",
          "content": "string"
        }
      ]
    }
  ]
}
```

#### Delete Conversation

```http
DELETE /api/chat/:conversationId
```

Response:

```json
{
  "message": "Conversation deleted successfully"
}
```

#### Health Check

```http
GET /health
```

Response:

```json
{
  "status": "ok" | "degraded",
  "timestamp": "2025-02-23T05:53:19.000Z",
  "services": {
    "openai": true,
    "dynamodb": true
  }
}
```

### Error Responses

#### 400 Bad Request - Occurs when the request is missing required data.

```json
{
  "error": "Bad Request",
  "message": "User ID and message are required"
}
```

#### 500 Internal Server Error - Occurs when there is an unexpected issue.

```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred"
}
```

#### 503 Service Unavailable - Occurs when external dependencies (OpenAI, DynamoDB) are down.

```json
{
  "error": "Service Unavailable",
  "message": "Service is temporarily unavailable"
}
```
