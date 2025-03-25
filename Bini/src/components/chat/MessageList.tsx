//  Right-aligns user messages, left-aligns bot messages using justify-end and justify-start.
//  Applies different colors based on role & dark mode (user vs. bot).
//  Displays timestamps for each message in a clean, readable format.
//  Ensures text wraps properly, even for long messages.
//  Loops through messages and history to display each message.

import React from "react";
import { Message, MessageHistory } from "../../backend/types";

// Define expected props for MessageList
interface MessageListProps {
  messages: Message[]; // List of messages with history
  darkMode: boolean; // Enables dark mode styling
}

// Functional component definition
const MessageList: React.FC<MessageListProps> = ({ messages, darkMode }) => {
  return (
    <>
      {messages.map((message) =>
        // Iterate through each history item in a message
        message.history.map((historyItem: MessageHistory, index: number) => (
          <div
            key={`${message.id}-${index}`} // Unique key using message ID and index
            className={`flex ${
              historyItem.role === "user" ? "justify-end" : "justify-start"
            } mb-4`}
          >
            {/* Message bubble with conditional styling based on sender role and dark mode */}
            <div
              className={`max-w-lg rounded-lg px-4 py-2 ${
                historyItem.role === "user"
                  ? darkMode
                    ? "bg-gray-700 text-gray-200" // User message (dark mode)
                    : "bg-gray-200 text-gray-900" // User message (light mode)
                  : darkMode
                  ? "bg-gray-800 text-gray-200" // Bot/assistant message (dark mode)
                  : "bg-white text-gray-900" // Bot/assistant message (light mode)
              }`}
            >
              {/* Message content */}
              <p className="break-words">{historyItem.content}</p>

              {/* Timestamp of the message */}
              <div className="flex justify-between items-center mt-1">
                <span
                  className={`text-xs ${
                    darkMode ? "text-gray-400" : "text-gray-500"
                  }`}
                >
                  {new Date(message.timestamp).toLocaleTimeString()}{" "}
                  {/* Formats the timestamp */}
                </span>
              </div>
            </div>
          </div>
        ))
      )}
    </>
  );
};

export default MessageList;
