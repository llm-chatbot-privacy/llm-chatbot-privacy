import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import MessageList from "./MessageList";
import MessageInput from "./MessageInput";
import { Message } from "../../backend/types";

// Define expected props for ChatArea
interface ChatAreaProps {
  messages: Message[]; // List of messages
  inputMessage: string; // Current input text
  setInputMessage: (msg: string) => void; // Updates input text
  handleSendMessage: (e: React.FormEvent) => void; // Handles message sending
  isLoading: boolean; // Loading state
  error: string | null; // Error message (if any)
  isRetrying: boolean; // Retry attempt status
  retryConnection: () => void; // Function to retry connection
  darkMode: boolean; // Enables dark mode
}

// Functional component definition
const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  inputMessage,
  setInputMessage,
  handleSendMessage,
  isLoading,
  error,
  isRetrying,
  retryConnection,
  darkMode,
}) => {
  const messagesEndRef = React.useRef<HTMLDivElement>(null); // Ref for auto-scrolling

  // Auto-scroll to the latest message when messages update when chatting
  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <>
      {/* Chat message container */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Error message box */}
        {error && (
          <div
            className={`border px-4 py-3 rounded mb-4 flex items-center justify-between 
            ${
              darkMode
                ? "bg-red-900/20 border-red-800 text-red-300"
                : "bg-red-50 border-red-200 text-red-700"
            }`}
          >
            <div className="flex items-center">
              <AlertCircle className="h-5 w-5 mr-2" /> {error}
            </div>
            <button
              onClick={retryConnection}
              disabled={isRetrying}
              className={`ml-4 p-2 rounded-full transition-colors disabled:opacity-50 
                ${darkMode ? "hover:bg-red-900/30" : "hover:bg-red-100"}`}
            >
              <RefreshCw
                className={`h-5 w-5 ${isRetrying ? "animate-spin" : ""}`}
              />
            </button>
          </div>
        )}

        {/* Display chat messages */}
        <MessageList messages={messages} darkMode={darkMode} />

        {/* Loading animation (typing indicator) */}
        {isLoading && (
          <div className="flex justify-center">
            <div
              className={`rounded-lg px-4 py-2 ${
                darkMode ? "bg-gray-800" : "bg-white"
              }`}
            >
              <div className="flex space-x-2">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className={`w-2 h-2 ${
                      darkMode ? "bg-gray-400" : "bg-gray-600"
                    } rounded-full animate-bounce`}
                    style={{ animationDelay: `${i * 0.2}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Invisible div for auto-scroll */}
        <div ref={messagesEndRef} />
      </div>

      {/* User input area */}
      <MessageInput
        inputMessage={inputMessage}
        setInputMessage={setInputMessage}
        handleSendMessage={handleSendMessage}
        isLoading={isLoading}
        darkMode={darkMode}
      />
    </>
  );
};

export default ChatArea;
