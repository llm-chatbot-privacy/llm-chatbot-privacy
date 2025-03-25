import React from 'react';
import { Plus, Archive, ArchiveRestore, MoreVertical, Trash2 } from 'lucide-react';
import { Conversation } from '../../types';

interface SidebarProps {
  show: boolean;
  conversations: Conversation[];
  selectedConversationId: string | null;
  darkMode: boolean;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  onArchiveConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onTitleEdit: (id: string, title: string) => void;
  onShowArchivedChats: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({
  show,
  conversations,
  selectedConversationId,
  darkMode,
  onNewChat,
  onSelectConversation,
  onArchiveConversation,
  onDeleteConversation,
  onTitleEdit,
  onShowArchivedChats
}) => {
  const [editingConversationId, setEditingConversationId] = React.useState<string | null>(null);
  const [showMenuId, setShowMenuId] = React.useState<string | null>(null);

  const activeConversations = conversations.filter(conv => 
    conv.status !== 'archived' && conv.status !== 'deleted'
  );

  return (
    <div className={`${show ? 'w-80' : 'w-0'} ${
      darkMode ? 'bg-gray-800' : 'bg-gray-50'
    } shadow-lg transition-all duration-300 overflow-hidden flex flex-col`}>
      <div className={`p-4 ${darkMode ? 'border-gray-700' : 'border-gray-200'} border-b`}>
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 p-3 bg-gray-700 dark:bg-gray-600 text-white rounded-lg hover:bg-gray-600 dark:hover:bg-gray-500 transition-colors"
        >
          <Plus className="h-5 w-5" />
          <span>New Chat</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeConversations.map((conversation) => (
          <div
            key={conversation.id}
            className={`w-full rounded-lg transition-colors ${
              selectedConversationId === conversation.id
                ? darkMode
                  ? 'bg-gray-700'
                  : 'bg-gray-200'
                : darkMode
                  ? 'hover:bg-gray-700'
                  : 'hover:bg-gray-100'
            }`}
          >
            <div className="p-4">
              <div className="flex items-center justify-between">
                {editingConversationId === conversation.id ? (
                  <input
                    type="text"
                    value={conversation.title}
                    onChange={(e) => onTitleEdit(conversation.id, e.target.value)}
                    onBlur={() => setEditingConversationId(null)}
                    className={`w-full px-2 py-1 rounded border focus:outline-none focus:ring-2 ${
                      darkMode 
                        ? 'bg-gray-700 text-gray-200 border-gray-600 focus:ring-gray-500' 
                        : 'bg-white text-gray-900 border-gray-300 focus:ring-gray-400'
                    }`}
                    autoFocus
                  />
                ) : (
                  <div className="flex items-center justify-between w-full">
                    <div 
                      className="flex-1 cursor-pointer" 
                      onClick={() => onSelectConversation(conversation.id)}
                    >
                      <h4 
                        className={`font-medium ${darkMode ? 'text-gray-200' : 'text-gray-900'}`}
                        onDoubleClick={() => setEditingConversationId(conversation.id)}
                      >
                        {conversation.title}
                      </h4>
                    </div>
                    <div className="relative">
                      <button
                        onClick={() => setShowMenuId(showMenuId === conversation.id ? null : conversation.id)}
                        className={`p-1 rounded-full transition-colors ${
                          darkMode
                            ? 'hover:bg-gray-600'
                            : 'hover:bg-gray-200'
                        }`}
                      >
                        <MoreVertical className={`h-4 w-4 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`} />
                      </button>
                      {showMenuId === conversation.id && (
                        <div className={`absolute right-0 mt-2 w-48 rounded-md shadow-lg z-50 ${
                          darkMode ? 'bg-gray-800' : 'bg-white'
                        }`}>
                          <div className="py-1">
                            <button
                              onClick={() => {
                                onArchiveConversation(conversation.id);
                                setShowMenuId(null);
                              }}
                              className={`w-full text-left px-4 py-2 text-sm ${
                                darkMode
                                  ? 'text-gray-300 hover:bg-gray-700'
                                  : 'text-gray-700 hover:bg-gray-100'
                              } flex items-center`}
                            >
                              <Archive className="h-4 w-4 mr-2" />
                              Archive
                            </button>
                            <button
                              onClick={() => {
                                onDeleteConversation(conversation.id);
                                setShowMenuId(null);
                              }}
                              className={`w-full text-left px-4 py-2 text-sm text-red-600 ${
                                darkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                              } flex items-center`}
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Delete
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
              <p className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-600'} line-clamp-2 mt-1`}>
                {conversation.lastMessage}
              </p>
              <div className="flex justify-between items-center mt-2">
                <span className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>
                  {new Date(conversation.timestamp).toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className={`p-4 ${darkMode ? 'border-gray-700' : 'border-gray-200'} border-t`}>
        <button
          onClick={onShowArchivedChats}
          className={`w-full flex items-center justify-center gap-2 p-3 rounded-lg transition-colors ${
            darkMode
              ? 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          <ArchiveRestore className="h-5 w-5" />
          <span>View Archived Chats</span>
        </button>
      </div>
    </div>
  );
};

export default Sidebar;