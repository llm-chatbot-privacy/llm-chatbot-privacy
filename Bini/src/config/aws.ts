//  Creates a DynamoDB client (dynamoClient) for direct API interactions.
//  Creates a Document Client (docClient) to simplify working with JSON data.
//  Uses environment variables for region and authentication.
//  Cleans up undefined values and converts empty values for DynamoDB compatibility.

import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";

// Initialize DynamoDB client
const dynamoClient = new DynamoDBClient({
  region: process.env.AWS_REGION || "us-east-2",
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID || "",
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || "",
  },
});

// Create document client
export const docClient = DynamoDBDocumentClient.from(dynamoClient, {
  marshallOptions: {
    removeUndefinedValues: true,
    convertEmptyValues: true,
  },
});

export default docClient;

export { dynamoClient };
