import React from "react";

// Define expected props for MessageInput
interface MessageInputProps {
  inputMessage: string; // User's current message input
  setInputMessage: (message: string) => void; // Updates the message input field
  handleSendMessage: (e: React.FormEvent) => void; // Handles message submission
  isLoading: boolean; // Indicates if a message is being sent
  darkMode: boolean; // Enables dark mode styling
}

// Functional component definition
const MessageInput: React.FC<MessageInputProps> = ({
  inputMessage,
  setInputMessage,
  handleSendMessage,
  isLoading,
  darkMode,
}) => {
  return (
    // Input container with dark mode styling
    <div
      className={`${
        darkMode ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"
      } p-4 border-t`}
    >
      {/* Form for handling message submission */}
      <form onSubmit={handleSendMessage} className="flex gap-4">
        {/* Input field for typing messages */}
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          className={`flex-1 rounded-lg border px-4 py-3 focus:outline-none focus:ring-2 ${
            darkMode
              ? "bg-gray-700 border-gray-600 text-gray-200 focus:ring-gray-500"
              : "bg-white border-gray-300 text-gray-900 focus:ring-gray-400"
          }`}
          placeholder="Type your message..."
          disabled={isLoading} // Disable input when loading
        />

        {/* Submit button for sending messages */}
        <button
          type="submit"
          className={`px-6 py-3 rounded-lg transition-colors disabled:opacity-50 ${
            darkMode
              ? "bg-gray-700 text-gray-200 hover:bg-gray-600"
              : "bg-gray-200 text-gray-900 hover:bg-gray-300"
          }`}
          disabled={isLoading || !inputMessage.trim()} // Disable when loading or input is empty
        >
          Send
        </button>
      </form>
    </div>
  );
};

export default MessageInput;
