import React from 'react';
import Header from './Header';
import Sidebar from './Sidebar';
import { Conversation } from '../../types';

interface LayoutProps {
  children: React.ReactNode;
  userId: string;
  showSidebar: boolean;
  setShowSidebar: (show: boolean) => void;
  darkMode: boolean;
  toggleDarkMode: () => void;
  conversations: Conversation[];
  selectedConversationId: string | null;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  onArchiveConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onTitleEdit: (id: string, title: string) => void;
  onShowArchivedChats: () => void;
}

const Layout: React.FC<LayoutProps> = ({
  children,
  userId,
  showSidebar,
  setShowSidebar,
  darkMode,
  toggleDarkMode,
  conversations,
  selectedConversationId,
  onNewChat,
  onSelectConversation,
  onArchiveConversation,
  onDeleteConversation,
  onTitleEdit,
  onShowArchivedChats
}) => {
  return (
    <div className={`flex h-screen ${darkMode ? 'bg-gray-900' : 'bg-white'} transition-colors duration-200`}>
      <Sidebar
        show={showSidebar}
        conversations={conversations}
        selectedConversationId={selectedConversationId}
        darkMode={darkMode}
        onNewChat={onNewChat}
        onSelectConversation={onSelectConversation}
        onArchiveConversation={onArchiveConversation}
        onDeleteConversation={onDeleteConversation}
        onTitleEdit={onTitleEdit}
        onShowArchivedChats={onShowArchivedChats}
      />
      <div className="flex-1 flex flex-col">
        <Header
          showSidebar={showSidebar}
          setShowSidebar={setShowSidebar}
          userId={userId}
          darkMode={darkMode}
          toggleDarkMode={toggleDarkMode}
        />
        {children}
      </div>
    </div>
  );
};

export default Layout;