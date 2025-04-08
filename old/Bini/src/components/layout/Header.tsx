import React from 'react';
import { MessageCircle, ChevronLeft, ChevronRight, Sun, Moon } from 'lucide-react';

interface HeaderProps {
  showSidebar: boolean;
  setShowSidebar: (show: boolean) => void;
  userId: string;
  darkMode: boolean;
  toggleDarkMode: () => void;
}

const Header: React.FC<HeaderProps> = ({
  showSidebar,
  setShowSidebar,
  userId,
  darkMode,
  toggleDarkMode
}) => {
  return (
    <header className={`${
      darkMode ? 'bg-gray-800' : 'bg-white'
    } shadow-lg p-4 sticky top-0 z-50 flex justify-between items-center`}>
      <div className="flex items-center">
        <button
          onClick={() => setShowSidebar(!showSidebar)}
          className={`p-2 rounded-lg transition-colors ${
            darkMode
              ? 'hover:bg-gray-700'
              : 'hover:bg-gray-100'
          }`}
        >
          {showSidebar ? <ChevronLeft className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
        </button>
        <MessageCircle className={`h-8 w-8 ${darkMode ? 'text-gray-400' : 'text-gray-600'}`} />
        <h1 className={`ml-3 text-2xl font-bold ${darkMode ? 'text-gray-200' : 'text-gray-900'}`}>UE-Lab</h1>
        <span className={`ml-4 text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>User ID: {userId}</span>
      </div>
      <button
        onClick={toggleDarkMode}
        className={`p-2 rounded-lg transition-colors ${
          darkMode
            ? 'hover:bg-gray-700 text-gray-400'
            : 'hover:bg-gray-100 text-gray-600'
        }`}
      >
        {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
      </button>
    </header>
  );
};

export default Header;