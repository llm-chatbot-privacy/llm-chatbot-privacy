// User authentication (LoginForm)
// Chat interactions (ChatArea)
// Fetching and managing conversations (Layout, ArchivedChats)
// Dark mode settings
// Server health checks

import React, { useState, useEffect } from "react";
import { apiService } from "./services/api";
import { Message, Conversation } from "./backend/types";
import Layout from "./components/layout/Layout";
import ChatArea from "./components/chat/ChatArea";
import LoginForm from "./components/auth/LoginForm";
import ArchivedChats from "./components/ArchivedChats";

const App: React.FC = () => {
  //     User authentication state
  const [userId, setUserId] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  //     Chat-related state
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<
    string | null
  >(null);
  const [currentConversationId, setCurrentConversationId] = useState<
    string | null
  >(null);

  //     UI State
  const [showSidebar, setShowSidebar] = useState(true);
  const [showArchivedChats, setShowArchivedChats] = useState(false);
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window !== "undefined") {
      return (
        localStorage.getItem("darkMode") === "true" ||
        window.matchMedia("(prefers-color-scheme: dark)").matches
      );
    }
    return false;
  });

  //     Loading & Error Handling
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  //     Apply dark mode on app load
  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
    localStorage.setItem("darkMode", darkMode.toString());
  }, [darkMode]);

  //     Fetch chat history when the user logs in
  useEffect(() => {
    if (isAuthenticated) {
      fetchChatHistory();
      checkServerHealth();
    }
  }, [isAuthenticated]);

  // 🔄 Toggle Dark Mode
  const toggleDarkMode = () => setDarkMode((prev) => !prev);

  //     Check if the backend is running
  const checkServerHealth = async () => {
    try {
      const data = await apiService.checkHealth();
      if (data.status !== "ok") throw new Error("Server health check failed");
      setError(null);
    } catch {
      setError("Cannot connect to chat server. Please try again later.");
    }
  };

  // 🔄 Retry server connection and reload messages
  const retryConnection = async () => {
    setIsRetrying(true);
    await checkServerHealth();
    if (!error) await fetchChatHistory();
    setIsRetrying(false);
  };

  //     Fetch user's chat history
  const fetchChatHistory = async () => {
    try {
      setError(null);
      const data = await apiService.getChatHistory(userId);

      if (data.messages) {
        // Group messages by conversation ID
        const messagesByConversation = data.messages.reduce(
          (acc: { [key: string]: Message[] }, msg: Message) => {
            if (msg.session_id) {
              acc[msg.session_id] = acc[msg.session_id] || [];
              acc[msg.session_id].push(msg);
            }
            return acc;
          },
          {}
        );

        // Generate conversation list
        const conversationList = Object.entries(messagesByConversation).map(
          ([id, messages]) => ({
            id,
            title: messages[0]?.history[0]?.content || "New Chat",
            lastMessage:
              messages[messages.length - 1]?.history[0]?.content || "",
            timestamp:
              messages[messages.length - 1]?.timestamp ||
              new Date().toISOString(),
            status: "active" as const,
          })
        );

        setConversations(conversationList);

        // Load messages of the selected conversation
        if (selectedConversationId) {
          setMessages(messagesByConversation[selectedConversationId] || []);
        }
      }
    } catch {
      setError("Unable to load chat history. Please try again later.");
    }
  };

  //     Start a new chat session
  const handleNewChat = async () => {
    try {
      const conversationId = await apiService.createConversation(userId);
      setCurrentConversationId(conversationId);
      setSelectedConversationId(conversationId);
      setMessages([]);
      setInputMessage("");

      setConversations((prev) => [
        {
          id: conversationId,
          title: "New Chat",
          lastMessage: "",
          timestamp: new Date().toISOString(),
          status: "active",
        },
        ...prev,
      ]);

      return conversationId;
    } catch {
      setError("Failed to create new chat.");
      return null;
    }
  };

  //     Send a message and update chat history
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    setIsLoading(true);
    const currentMessage = inputMessage;
    setInputMessage("");

    try {
      let conversationId = currentConversationId;
      if (!conversationId) {
        conversationId = await handleNewChat();
        if (!conversationId) throw new Error("Failed to create conversation");
      }

      const data = await apiService.sendMessage(
        userId,
        currentMessage,
        conversationId
      );

      // Add the message to the chat history
      const newMessage: Message = {
        id: crypto.randomUUID(),
        user_id: userId,
        session_id: conversationId,
        timestamp: new Date().toISOString(),
        history: data.history,
      };

      setMessages((prev) => [...prev, newMessage]);

      // Update conversation preview
      setConversations((prev) =>
        prev.map((conv) =>
          conv.id === conversationId
            ? {
                ...conv,
                lastMessage: data.history[data.history.length - 1].content,
              }
            : conv
        )
      );
    } catch {
      setError("Failed to send message. Please try again.");
      setInputMessage(currentMessage);
    } finally {
      setIsLoading(false);
    }
  };

  //  Render Login Form if user is not authenticated
  if (!isAuthenticated) {
    return (
      <LoginForm
        userId={userId}
        setUserId={setUserId}
        onSubmit={() => setIsAuthenticated(true)}
        darkMode={darkMode}
      />
    );
  }

  // Render Archived Chats Page
  if (showArchivedChats) {
    return (
      <ArchivedChats
        conversations={conversations}
        onSelectConversation={(id) => {
          setSelectedConversationId(id);
          setCurrentConversationId(id);
          setShowArchivedChats(false);
        }}
        onBack={() => setShowArchivedChats(false)}
        onDelete={async (id) => {
          try {
            await apiService.deleteConversation(id);
            setConversations((prev) => prev.filter((conv) => conv.id !== id));
          } catch {
            setError("Failed to delete conversation.");
          }
        }}
        darkMode={darkMode}
      />
    );
  }

  // Render Main Chat Interface
  return (
    <Layout
      userId={userId}
      showSidebar={showSidebar}
      setShowSidebar={setShowSidebar}
      darkMode={darkMode}
      toggleDarkMode={toggleDarkMode}
      conversations={conversations}
      selectedConversationId={selectedConversationId}
      onNewChat={handleNewChat}
      onSelectConversation={async (id) => {
        setSelectedConversationId(id);
        setCurrentConversationId(id);
        try {
          const data = await apiService.getChatHistory(userId);
          const conversationMessages =
            data.messages?.filter((m) => m.session_id === id) || [];
          setMessages(conversationMessages);
        } catch (err) {
          setError("Failed to load conversation messages.");
        }
      }}
      onArchiveConversation={(id) => {
        if (id === currentConversationId) {
          setMessages([]);
          setCurrentConversationId(null);
          setSelectedConversationId(null);
        }
        setConversations((prev) =>
          prev.map((conv) =>
            conv.id === id ? { ...conv, status: "archived" } : conv
          )
        );
      }}
      onDeleteConversation={async (id) => {
        if (
          !window.confirm("Are you sure you want to delete this conversation?")
        ) {
          return;
        }
        try {
          await apiService.deleteConversation(id);
          if (id === currentConversationId) {
            setMessages([]);
            setCurrentConversationId(null);
            setSelectedConversationId(null);
          }
          setConversations((prev) => prev.filter((conv) => conv.id !== id));
        } catch (err) {
          setError("Failed to delete conversation.");
        }
      }}
      onTitleEdit={(id, title) => {
        setConversations((prev) =>
          prev.map((conv) => (conv.id === id ? { ...conv, title } : conv))
        );
      }}
      onShowArchivedChats={() => setShowArchivedChats(true)}
    >
      <ChatArea
        messages={messages}
        inputMessage={inputMessage}
        setInputMessage={setInputMessage}
        handleSendMessage={handleSendMessage}
        isLoading={isLoading}
        error={error}
        isRetrying={isRetrying}
        retryConnection={retryConnection}
        darkMode={darkMode}
      />
    </Layout>
  );
};

export default App;
