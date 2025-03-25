// Message types
export interface MessageHistory {
  role: 'user' | 'assistant';
  content: string;
}

export interface Message {
  id: string;
  user_id: string;
  session_id: string;
  timestamp: string;
  history: MessageHistory[];
  status?: 'active' | 'archived' | 'deleted';
}

// Conversation types
export interface Conversation {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: string;
  status: 'active' | 'archived' | 'deleted';
  isEditingTitle?: boolean;
  showMenu?: boolean;
}

// Component props types
export interface TooltipProps {
  text: string;
  children: React.ReactNode;
}

// API response types
export interface APIResponse<T> {
  data?: T;
  error?: string;
  message?: string;
}

export interface HealthCheckResponse {
  status: 'ok' | 'degraded';
  timestamp: string;
  services: {
    openai: boolean;
    dynamodb: boolean;
  };
}