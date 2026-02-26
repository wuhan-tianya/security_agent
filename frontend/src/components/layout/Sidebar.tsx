import { NavLink } from 'react-router-dom';
import { Shield, MessageSquare, Settings } from 'lucide-react';

const Sidebar = () => {
  const navItems = [
    { name: 'Chat', icon: MessageSquare, path: '/' },
    { name: 'Settings', icon: Settings, path: '/settings' },
  ];

  return (
    <div className="w-64 h-screen bg-security-surface border-r border-gray-800 flex flex-col font-mono text-sm">
      <div className="p-4 flex items-center space-x-2 border-b border-gray-800">
        <Shield className="w-6 h-6 text-security-primary animate-pulse" />
        <span className="font-bold text-lg tracking-wider text-security-primary">SEC_AGENT</span>
      </div>
      
      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.name}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center space-x-3 px-3 py-2 rounded transition-colors duration-200 ${
                isActive
                  ? 'bg-gray-800 text-security-primary border-l-2 border-security-primary'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`
            }
          >
            <item.icon className="w-5 h-5" />
            <span>{item.name}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-800 text-xs text-gray-500">
        <p>SYSTEM STATUS: <span className="text-security-primary">ONLINE</span></p>
        <p>VERSION: 1.0.0-alpha</p>
      </div>
    </div>
  );
};

export default Sidebar;
