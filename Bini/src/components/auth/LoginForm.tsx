import React from "react";
import { MessageCircle } from "lucide-react";

interface LoginFormProps {
  userId: string; // The current user ID as a string.
  setUserId: (id: string) => void; // A function to update the user ID.
  onSubmit: () => void; // A function that gets triggered when the form is submitted.
  darkMode: boolean; // A boolean flag indicating whether dark mode is enabled.
}

const LoginForm: React.FC<LoginFormProps> = ({
  userId,
  setUserId,
  onSubmit,
  darkMode,
}) => {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit();
  };
  // UI
  return (
    <div className="min-h-screen bg-white dark:bg-gray-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8">
        <div className="text-center">
          <MessageCircle className="mx-auto h-12 w-12 text-gray-600 dark:text-gray-400" />
          <h2 className="mt-6 text-3xl font-bold text-gray-900 dark:text-gray">
            Welcome to UE-Lab
          </h2>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Please enter your user ID to continue
          </p>
        </div>
        <form onSubmit={handleSubmit} className="mt-8">
          <input // Input Field
            type="text"
            required
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-gray-400 dark:focus:ring-gray-500 focus:border-transparent"
            placeholder="Enter your user ID"
          />
          <button
            type="submit"
            disabled={!userId.trim()}
            className="mt-4 w-full bg-gray-800 dark:bg-gray-700 text-white py-3 rounded-lg hover:bg-gray-700 dark:hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Start Chatting
          </button>
        </form>
      </div>
    </div>
  );
};

export default LoginForm;
