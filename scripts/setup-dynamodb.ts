import { DescribeTableCommand } from "@aws-sdk/client-dynamodb";
import { PutCommand } from "@aws-sdk/lib-dynamodb";
import { dynamoClient } from "../src/config/aws";
import { TableNames } from "../src/services/dynamodb";

async function checkTableStatus() {
  try {
    await dynamoClient.send(
      new DescribeTableCommand({ TableName: TableNames.MESSAGES })
    );
    console.log(`✅ Table "${TableNames.MESSAGES}" exists and is ready.`);
    return true;
  } catch (error: any) {
    if (error.name === "ResourceNotFoundException") {
      console.error(
        `❌ Table "${TableNames.MESSAGES}" does not exist. Please create it first.`
      );
    } else {
      console.error("❌ Error checking table status:", error);
    }
    return false;
  }
}

async function insertSampleMessages() {
  const sampleMessages = [
    {
      user_id: "test_user_1",
      session_id: "session_123",
      timestamp: new Date().toISOString(),
      history: JSON.stringify([
        { role: "user", content: "Hello" },
        { role: "assistant", content: "Hi there! How can I assist you?" },
      ]),
    },
    {
      user_id: "test_user_2",
      session_id: "session_456",
      timestamp: new Date().toISOString(),
      history: JSON.stringify([
        { role: "user", content: "Tell me a joke" },
        {
          role: "assistant",
          content:
            "Why did the chicken join a band? Because it had the drumsticks!",
        },
      ]),
    },
  ];

  try {
    for (const message of sampleMessages) {
      await dynamoClient.send(
        new PutCommand({
          TableName: TableNames.MESSAGES,
          Item: message,
        })
      );
      console.log(`✅ Inserted message for user ${message.user_id}`);
    }
  } catch (error) {
    console.error("❌ Error inserting sample messages:", error);
  }
}

async function setupDynamoDB() {
  const tableExists = await checkTableStatus();
  if (tableExists) {
    await insertSampleMessages();
    console.log("✅ Sample messages inserted successfully!");
  } else {
    console.log("⚠️ Setup aborted: Table does not exist.");
  }
}

setupDynamoDB();
