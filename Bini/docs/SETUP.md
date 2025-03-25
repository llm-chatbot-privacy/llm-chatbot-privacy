## UE-Lab Setup Guide

### Prerequisites

- Node.js 18+
- npm 9+
- AWS Account
- OpenAI API key

### AWS Setup

1. Create an AWS Account if you don't have one
2. Create an IAM User:
   - Go to AWS IAM Console
   - Create a new user or select existing
   - Attach `AmazonDynamoDBFullAccess` policy
   - Generate access keys

### Environment Variables

Create a `.env` file in the root directory:

```env
# API Configuration
VITE_API_URL=http://localhost:5001
PORT=5001

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=us-east-1
```

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   npm install
   ```

### Database Setup

1. Set up AWS credentials in `.env`
2. Write into the DynamoDB Table

### Development

1. Start the development server:
   ```bash
   npm run dev
   ```
2. Start the backend server:
   ```bash
   npm run server
   ```
3. Or run both simultaneously:
   ```bash
   npm start
   ```

### Production

1. Build the frontend:
   ```bash
   npm run build
   ```
2. Deploy the backend:
   ```bash
   node server.js
   ```

### Testing

- Frontend tests: Coming soon
- API tests: Coming soon
- Database tests: Coming soon

### Troubleshooting

#### DynamoDB Issues

- Check AWS credentials in `.env`
- Verify AWS region is correct
- Ensure IAM user has correct permissions
- Check DynamoDB access works

#### OpenAI API Issues

- Verify API key is valid
- Check rate limits
- Monitor API status

#### Development Server Issues

- Clear npm cache
- Check port availability
- Verify dependencies
