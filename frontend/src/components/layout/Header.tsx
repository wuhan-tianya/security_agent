import { useEffect, useState } from 'react';
import { Activity, Wifi, AlertTriangle } from 'lucide-react';
import { getHealth } from '../../api';

const Header = () => {
  const [health, setHealth] = useState<'ok' | 'error'>('ok');
  
  useEffect(() => {
    const checkHealth = async () => {
        try {
            await getHealth();
            setHealth('ok');
        } catch (e) {
            setHealth('error');
        }
    }
    
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-14 bg-security-bg border-b border-gray-800 flex items-center justify-between px-6 font-mono">
      <div className="flex items-center space-x-4">
        <span className="text-gray-400 text-sm">Target: <span className="text-security-primary">ALL_SYSTEMS</span></span>
      </div>

      <div className="flex items-center space-x-6 text-sm">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-security-primary" />
          <span className="text-security-text">CPU_LOAD: 12%</span>
        </div>
        
        <div className="flex items-center space-x-2">
            {health === 'ok' ? (
                 <>
                    <Wifi className="w-4 h-4 text-security-primary" />
                    <span className="text-security-primary">CONNECTED</span>
                 </>
            ) : (
                <>
                    <AlertTriangle className="w-4 h-4 text-security-alert" />
                    <span className="text-security-alert">DISCONNECTED</span>
                </>
            )}
         
        </div>
      </div>
    </header>
  );
};

export default Header;
