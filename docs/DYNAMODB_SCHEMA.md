UE-Lab Chat Application Architecture

Overview

UE-Lab is a real-time chat application designed with a modern, responsive React + TypeScript frontend and seamless OpenAI integration. It supports conversation management, dark mode, and DynamoDB-powered message storage.

Tech Stack

Layer Technology
Frontend React + TypeScript + Vite
Styling Tailwind CSS
Icons Lucide React
AI Integration OpenAI API
Database DynamoDB

Project Structure

src/
├── components/
│ ├── auth/
│ │ └── LoginForm.tsx # User authentication form
│ ├── chat/
│ │ ├── ChatArea.tsx # Main chat interface
│ │ ├── MessageList.tsx # Chat messages display
│ │ └── MessageInput.tsx # Message input form
│ └── layout/
│ ├── Layout.tsx # Main layout wrapper
│ ├── Header.tsx # Application header
│ └── Sidebar.tsx # Chat sidebar
├── config/
│ └── aws.ts # AWS configuration for DynamoDB
├── services/
│ ├── openai.ts # OpenAI API client
│ ├── api.ts # API client for backend interactions
│ └── dynamodb.ts # DynamoDB operations
├── types/
│ └── index.ts # TypeScript interfaces
└── App.tsx # Main application component

scripts/
└── setup-dynamodb.ts # DynamoDB setup script

Database Schema

Messages Table (uelab_messages)

Primary storage for chat messages and conversation history.

interface Message {
user_id: string; // Partition Key (Hash Key)
timestamp: string; // Sort Key (Range Key)
session_id: string; // Global Secondary Index (GSI Key)
history: string; // JSON string containing chat history
}

Indexes
• Primary Index: (user_id, timestamp)
• Global Secondary Index (GSI): SessionIdIndex (session_id, timestamp)

Key Features

1️⃣ Real-time Chat

✔ Stores messages in DynamoDB
✔ Retrieves AI-generated responses via OpenAI
✔ Displays conversation history

2️⃣ Conversation Management

✔ Start new conversations
✔ Archive & delete chats
✔ Edit conversation titles

3️⃣ User Experience

✔ Dark/Light mode toggle
✔ Fully responsive UI
✔ Error handling & loading states

API Layer
• RESTful Express.js endpoints
• Direct OpenAI API integration for AI responses
• DynamoDB CRUD operations (store & delete messages)

State Management
• useState for local UI updates
• Props-based communication between components
• DynamoDB for persistence

Error Handling
• Client-side validation to prevent invalid input
• Server-side error responses for stability
• User-friendly error messages displayed in UI
• Automatic retry mechanism for failed requests

Performance Considerations

⚡ Optimized DynamoDB Read/Write Capacity Units
⚡ Efficient Global Secondary Index (GSI) usage
⚡ Lazy loading messages for large chat histories
⚡ Optimized React rendering to prevent re-renders

Security Measures

✅ Environment variable validation to protect API keys
✅ Input sanitization to prevent XSS attacks
✅ Sanitized error messages to avoid information leaks
✅ Rate limiting (Future Implementation)

Future Enhancements 🚀

🔹 WebSocket Integration for real-time updates
🔹 User Authentication (OAuth/Google Login)
🔹 Advanced Conversation Insights with AI
🔹 Multi-user Chat Support

Run:

npm start
