## UE-Lab Chat Application Architecture

### Overview
UE-Lab is a real-time chat application built with React, TypeScript, and DynamoDB. It features a modern, responsive interface with dark mode support and conversation management capabilities.

### Tech Stack
- Frontend: React + TypeScript + Vite
- Styling: Tailwind CSS
- Backend: Node.js + Express
- Database: DynamoDB
- Icons: Lucide React
- AI Integration: OpenAI API

### Project Structure
```
src/
├── components/
│   ├── auth/
│   │   └── LoginForm.tsx         # User authentication form
│   ├── chat/
│   │   ├── ChatArea.tsx         # Main chat interface
│   │   ├── MessageList.tsx      # Chat messages display
│   │   └── MessageInput.tsx     # Message input form
│   └── layout/
│       ├── Layout.tsx           # Main layout wrapper
│       ├── Header.tsx           # Application header
│       └── Sidebar.tsx          # Chat sidebar
├── config/
│   └── aws.ts                   # AWS/DynamoDB configuration
├── services/
│   ├── api.ts                   # API client
│   └── dynamodb.ts              # DynamoDB operations
├── types/
│   └── index.ts                 # TypeScript interfaces
└── App.tsx                      # Main application component

scripts/
└── setup-dynamodb.ts            # DynamoDB setup script

server/
└── server.js                    # Express server for API endpoints
```

### Database Schema

#### Messages Table (uelab_messages)
Primary table for storing chat messages and their history.

```typescript
interface Message {
  user_id: string;      // Hash key
  timestamp: string;    // Range key
  session_id: string;   // GSI key
  history: string;      // JSON string of message history
}
```

Indexes:
- Primary: (user_id, timestamp)
- GSI: SessionIdIndex (session_id, timestamp)

### Key Features
1. Real-time Chat
   - Message persistence in DynamoDB
   - Conversation history
   - OpenAI integration

2. Conversation Management
   - Create new conversations
   - Archive conversations
   - Delete conversations
   - Edit conversation titles

3. User Experience
   - Dark/Light mode toggle
   - Responsive design
   - Error handling
   - Loading states

### API Layer
- RESTful endpoints
- Express.js server
- DynamoDB integration
- OpenAI integration

### State Management
- React useState for local state
- Props for component communication
- DynamoDB for persistence

### Error Handling
- Client-side validation
- Server error responses
- User-friendly error messages
- Automatic retry mechanism

### Performance Considerations
- DynamoDB read/write capacity units
- Efficient GSI usage
- Optimized React renders
- Lazy loading where appropriate

### Security
- Environment variable validation
- Input sanitization
- Error message sanitization
- Rate limiting (TODO)