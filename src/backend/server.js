// Import required modules
import express from "express"; // Web framework for handling API requests
import cors from "cors"; // Enables cross-origin requests
import dotenv from "dotenv"; // Loads environment variables from .env
import OpenAI from "openai"; // Communicates with ChatGPT API
import AWS from "aws-sdk"; // Direct interaction with DynamoDB

// Load environment variables
dotenv.config();

// Initialize Express server
const app = express();
const PORT = process.env.PORT || 5001;

// Configure CORS (Allows frontend to communicate with backend)
app.use(cors({ origin: ["http://localhost:5173"], credentials: true }));
app.use(express.json()); // Parse incoming JSON requests

// Middleware to log all incoming requests
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.path}`);
  next();
});

// Validate essential environment variables
const requiredEnvVars = ["OPENAI_API_KEY", "AWS_REGION"];
for (const envVar of requiredEnvVars) {
  if (!process.env[envVar]) {
    console.error(`❌ Missing required environment variable: ${envVar}`);
    process.exit(1);
  }
}

// Initialize OpenAI client for ChatGPT API calls
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY.trim(),
  timeout: 30000, // Request timeout set to 30 seconds
  maxRetries: 3, // Retries failed API calls up to 3 times
});

// Configure AWS SDK for DynamoDB
AWS.config.update({ region: process.env.AWS_REGION });
const dynamoDB = new AWS.DynamoDB.DocumentClient();
const TABLE_NAME = "chat_history"; // Change to your actual table name

// Health check endpoint
app.get("/health", (req, res) => {
  res.status(200).json({ status: "ok", timestamp: new Date().toISOString() });
});

// API endpoint to send a message, process with OpenAI, and store in DynamoDB
app.post("/api/chat", async (req, res) => {
  try {
    const { userId, message, conversationId } = req.body;
    if (!userId || !message || !conversationId) {
      return res
        .status(400)
        .json({ error: "User ID, message, and conversation ID are required" });
    }

    // Get response from ChatGPT
    const completion = await openai.chat.completions.create({
      messages: [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: message },
      ],
      model: "gpt-3.5-turbo",
      temperature: 0.7,
      max_tokens: 500,
    });

    const botResponse = completion.choices[0].message.content;

    // Store conversation history in DynamoDB (Write Only)
    const params = {
      TableName: TABLE_NAME,
      Item: {
        user_id: userId,
        session_id: conversationId,
        timestamp: new Date().toISOString(),
        history: JSON.stringify([
          { role: "user", content: message },
          { role: "assistant", content: botResponse },
        ]),
      },
    };
    await dynamoDB.put(params).promise();

    res.json({
      userId,
      history: [
        { role: "user", content: message },
        { role: "assistant", content: botResponse },
      ],
    });
  } catch (error) {
    console.error("❌ Error handling chat message:", error.message);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

// API endpoint to delete chat history
app.delete("/api/chat/:userId/:conversationId", async (req, res) => {
  try {
    const { userId, conversationId } = req.params;
    const params = {
      TableName: TABLE_NAME,
      Key: { user_id: userId, session_id: conversationId },
    };

    await dynamoDB.delete(params).promise();
    res.json({ message: "Chat deleted successfully." });
  } catch (error) {
    console.error("❌ Error deleting chat:", error.message);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

// Middleware for handling unexpected errors
app.use((err, req, res, next) => {
  console.error("❌ Unhandled Error:", err.message);
  res.status(500).json({ error: "Internal Server Error" });
});

// Start the Express server
const server = app.listen(PORT, "0.0.0.0", () => {
  console.log(`✅ Server running on port ${PORT}`);
  console.log(`🔍 Health check available at http://localhost:${PORT}/health`);
});

// Handle server-level errors
server.on("error", (error) => {
  console.error("❌ Server error:", error.message);
  process.exit(1);
});

// Catch and handle unhandled promise rejections
process.on("unhandledRejection", (reason, promise) => {
  console.error(
    "❌ Unhandled Promise Rejection at:",
    promise,
    "reason:",
    reason
  );
});

// Catch and handle uncaught exceptions
process.on("uncaughtException", (error) => {
  console.error("❌ Uncaught Exception:", error.message);
  process.exit(1);
});

// Export app for potential testing or other integrations
export default app;
