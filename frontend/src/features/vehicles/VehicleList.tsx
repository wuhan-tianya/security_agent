import { useEffect, useState, type FormEvent } from 'react';
import { getVehicles, registerVehicle, type Vehicle } from '../../api';
import { Monitor, Plus, Server, CheckCircle, XCircle } from 'lucide-react';

const VehicleList = () => {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newVehicle, setNewVehicle] = useState({ vehicle_name: '', ip: '', mcp_endpoint: '' });

  const fetchVehicles = async () => {
    setLoading(true);
    try {
      const data = await getVehicles();
      setVehicles(data);
    } catch (error) {
      console.error('Failed to fetch vehicles', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVehicles();
  }, []);

  const handleRegister = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await registerVehicle({
          ...newVehicle,
          status: 'online', // Default assumption
          is_configured: true
      });
      setShowAddModal(false);
      setNewVehicle({ vehicle_name: '', ip: '', mcp_endpoint: '' });
      fetchVehicles();
    } catch (error) {
      console.error('Failed to register vehicle', error);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto font-mono">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-security-primary flex items-center">
          <Server className="mr-2" /> VEHICLE_REGISTRY
        </h1>
        <button 
          onClick={() => setShowAddModal(true)}
          className="bg-security-primary text-black px-4 py-2 rounded font-bold hover:bg-green-400 flex items-center"
        >
          <Plus className="w-4 h-4 mr-2" /> ADD_TARGET
        </button>
      </div>

      {loading ? (
        <div className="text-center p-10 text-security-dim animate-pulse">Scanning network...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {vehicles.map((vehicle) => (
            <div key={vehicle.ip} className="bg-security-surface border border-gray-800 rounded-lg p-4 relative group hover:border-security-primary transition-colors">
              <div className="absolute top-4 right-4">
                {vehicle.status === 'online' ? (
                  <CheckCircle className="w-5 h-5 text-security-primary" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-500" />
                )}
              </div>
              
              <div className="flex items-center mb-4">
                <Monitor className="w-8 h-8 text-security-dim group-hover:text-security-primary transition-colors" />
                <div className="ml-3">
                  <h3 className="font-bold text-lg">{vehicle.vehicle_name}</h3>
                  <p className="text-xs text-gray-500">{vehicle.ip}</p>
                </div>
              </div>
              
              <div className="space-y-2 text-xs text-gray-400">
                <div className="flex justify-between">
                  <span>ENDPOINT:</span>
                  <span className="text-gray-300">{vehicle.mcp_endpoint}</span>
                </div>
                <div className="flex justify-between">
                  <span>CONFIGURED:</span>
                  <span className={vehicle.is_configured ? 'text-security-primary' : 'text-yellow-500'}>
                    {vehicle.is_configured ? 'YES' : 'NO'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>LAST SEEN:</span>
                  <span>{vehicle.last_seen_at || 'NEVER'}</span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-gray-800 flex justify-end space-x-2">
                 <button className="text-xs border border-gray-700 px-2 py-1 rounded hover:bg-gray-800">PING</button>
                 <button className="text-xs border border-gray-700 px-2 py-1 rounded hover:bg-gray-800">CONNECT</button>
              </div>
            </div>
          ))}
          
          {vehicles.length === 0 && (
            <div className="col-span-full text-center p-10 border border-dashed border-gray-800 rounded text-gray-500">
              No vehicles registered. Add a target to begin.
            </div>
          )}
        </div>
      )}

      {showAddModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-security-surface border border-security-primary p-6 rounded-lg w-full max-w-md shadow-[0_0_20px_rgba(0,255,65,0.2)]">
            <h2 className="text-xl font-bold mb-4 text-security-primary">REGISTER NEW TARGET</h2>
            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <label className="block text-xs mb-1 text-gray-400">VEHICLE ID</label>
                <input 
                  type="text" 
                  required
                  className="w-full bg-black border border-gray-700 p-2 rounded text-security-text focus:border-security-primary outline-none"
                  value={newVehicle.vehicle_name}
                  onChange={e => setNewVehicle({...newVehicle, vehicle_name: e.target.value})}
                />
              </div>
              <div>
                <label className="block text-xs mb-1 text-gray-400">IP ADDRESS</label>
                <input 
                  type="text" 
                  required
                  className="w-full bg-black border border-gray-700 p-2 rounded text-security-text focus:border-security-primary outline-none"
                  value={newVehicle.ip}
                  onChange={e => setNewVehicle({...newVehicle, ip: e.target.value})}
                />
              </div>
              <div>
                <label className="block text-xs mb-1 text-gray-400">MCP ENDPOINT</label>
                <input 
                  type="text" 
                  required
                  placeholder="http://10.x.x.x:9000"
                  className="w-full bg-black border border-gray-700 p-2 rounded text-security-text focus:border-security-primary outline-none"
                  value={newVehicle.mcp_endpoint}
                  onChange={e => setNewVehicle({...newVehicle, mcp_endpoint: e.target.value})}
                />
              </div>
              
              <div className="flex justify-end space-x-3 mt-6">
                <button 
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-gray-400 hover:text-white"
                >
                  CANCEL
                </button>
                <button 
                  type="submit"
                  className="bg-security-primary text-black px-4 py-2 rounded font-bold hover:bg-green-400"
                >
                  REGISTER
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default VehicleList;
