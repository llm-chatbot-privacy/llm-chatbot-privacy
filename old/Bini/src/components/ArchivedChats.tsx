import React from "react";
import { MessageCircle, ChevronLeft, Trash2 } from "lucide-react";
import { format } from "date-fns";

// Define expected props for the component
interface ArchivedChatsProps {
  conversations: Array<{
    id: string;
    title: string;
    lastMessage: string;
    timestamp: string;
    status: string;
  }>; // List of archived conversations
  onSelectConversation: (id: string) => void; // Opens a conversation
  onBack: () => void; // Navigates back
  onDelete: (id: string) => void; // Deletes a conversation
  darkMode: boolean; // Enables dark mode styling
}

const ArchivedChats: React.FC<ArchivedChatsProps> = ({
  conversations,
  onSelectConversation,
  onBack,
  onDelete,
  darkMode,
}) => {
  // Filter and sort archived conversations (newest first)
  const archivedConversations = conversations
    .filter((conv) => conv.status === "archived")
    .sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );

  return (
    // Main container with gradient background and smooth transitions
    <div
      className={`h-screen overflow-auto transition-colors duration-200 ${
        darkMode
          ? "bg-gradient-to-br from-gray-900 to-purple-900"
          : "bg-gradient-to-br from-blue-50 to-purple-50"
      }`}
    >
      {/* Header Section */}
      <header
        className={`sticky top-0 z-50 flex items-center p-4 shadow-lg transition-colors duration-200 ${
          darkMode ? "bg-gray-800" : "bg-white"
        }`}
      >
        {/* Back Button */}
        <button
          onClick={onBack}
          className={`p-2 rounded-lg transition-colors duration-200 ${
            darkMode
              ? "hover:bg-gray-700 text-gray-300"
              : "hover:bg-gray-100 text-gray-600"
          }`}
        >
          <ChevronLeft className="h-5 w-5" />
        </button>

        {/* Icon and Title */}
        <MessageCircle
          className={`h-8 w-8 ${
            darkMode ? "text-purple-400" : "text-blue-500"
          }`}
        />
        <h1
          className={`ml-3 text-2xl font-bold ${
            darkMode ? "text-purple-400" : "text-blue-600"
          }`}
        >
          Archived Chats
        </h1>
      </header>

      {/* Archived Conversations List */}
      <div className="p-4 space-y-4">
        {archivedConversations.length === 0 ? (
          // Display a message if no archived conversations exist
          <div
            className={`text-center py-8 ${
              darkMode ? "text-gray-400" : "text-gray-500"
            }`}
          >
            No archived conversations found
          </div>
        ) : (
          archivedConversations.map((conversation) => (
            <div
              key={conversation.id}
              className={`rounded-lg shadow-md p-4 transition-colors duration-200 ${
                darkMode
                  ? "bg-gray-800 hover:bg-gray-700"
                  : "bg-white hover:bg-gray-50"
              }`}
            >
              {/* Chat Card Layout */}
              <div className="flex justify-between items-start">
                {/* Clickable Chat Info (Title, Last Message, Timestamp) */}
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() => onSelectConversation(conversation.id)}
                >
                  {/* Chat Title */}
                  <h3
                    className={`font-medium ${
                      darkMode ? "text-white" : "text-gray-900"
                    }`}
                  >
                    {conversation.title}
                  </h3>
                  {/* Last Message Preview */}
                  <p
                    className={`text-sm mt-1 line-clamp-2 ${
                      darkMode ? "text-gray-300" : "text-gray-600"
                    }`}
                  >
                    {conversation.lastMessage}
                  </p>
                  {/* Timestamp (Formatted) */}
                  <div
                    className={`mt-2 text-xs ${
                      darkMode ? "text-gray-400" : "text-gray-500"
                    }`}
                  >
                    {format(new Date(conversation.timestamp), "PPpp")}
                  </div>
                </div>

                {/* Delete Button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation(); // Prevents clicking the chat when deleting
                    onDelete(conversation.id);
                  }}
                  className={`p-2 rounded-full transition-colors duration-200 ${
                    darkMode
                      ? "hover:bg-red-900/50 text-red-400"
                      : "hover:bg-red-100 text-red-600"
                  }`}
                  title="Delete conversation"
                >
                  <Trash2 className="h-5 w-5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ArchivedChats;
