// Defines an API service using axios to interact with a backend server

//    Import dependencies
import axios from "axios"; // Handles HTTP requests
import { Message, APIResponse, HealthCheckResponse } from "../backend/types";

//    Configure the API base URL
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5001";

//    Create an Axios instance for API requests
const api = axios.create({
  baseURL: API_URL, // Backend server URL
  timeout: 10000, // Request timeout: 10s
  headers: { "Content-Type": "application/json" }, // Default headers
});

export const apiService = {
  //    Check if the backend server and services (OpenAI, DynamoDB) are running
  async checkHealth(): Promise<HealthCheckResponse> {
    try {
      const response = await api.get<HealthCheckResponse>("/health");
      return response.data; // Returns server status
    } catch (error) {
      console.error("Health check failed:", error);
      throw new Error("Cannot reach server");
    }
  },

  //    Retrieve chat history for a specific user
  async getChatHistory(userId: string): Promise<{ messages: Message[] }> {
    try {
      const response = await api.get<APIResponse<{ messages: Message[] }>>(
        `/api/chat/${userId}`
      );
      if (!response.data.data?.messages) throw new Error("No messages found");
      return response.data.data;
    } catch (error) {
      console.error("Failed to fetch chat history:", error);
      throw new Error("Error retrieving messages");
    }
  },

  //    Send a message and get the AI response
  async sendMessage(
    userId: string,
    message: string,
    conversationId: string
  ): Promise<{
    userId: string;
    history: { role: "user" | "assistant"; content: string }[];
  }> {
    try {
      const response = await api.post<
        APIResponse<{
          userId: string;
          history: { role: "user" | "assistant"; content: string }[];
        }>
      >("/api/chat", { userId, message, conversationId });

      if (!response.data.data?.history) throw new Error("No history returned");
      return response.data.data;
    } catch (error) {
      console.error("Message send failed:", error);
      throw new Error("Error sending message");
    }
  },

  //    Generate a new conversation ID
  async createConversation(userId: string): Promise<string> {
    try {
      return crypto.randomUUID(); // Creates a unique conversation ID
    } catch (error) {
      console.error("Conversation creation failed:", error);
      throw new Error("Error creating conversation");
    }
  },

  //    Delete a conversation from the chat history
  async deleteConversation(conversationId: string): Promise<void> {
    try {
      await api.delete(`/api/chat/${conversationId}`);
    } catch (error) {
      console.error("Conversation deletion failed:", error);
      throw new Error("Error deleting conversation");
    }
  },
};
