import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000'; // Adjust if backend runs on a different port

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Vehicle {
  vehicle_name: string;
  ip: string;
  mcp_endpoint: string;
  status: 'online' | 'offline';
  is_configured: boolean;
  last_seen_at?: string;
}

export interface Tool {
  vehicle_name: string;
  ip: string;
  name: string;
  description: string;
  input_schema: any;
  source_endpoint: string;
}

export interface SessionMemory {
  session_id: string;
  recent_messages: any[];
  latest_summary: string | null;
  last_vehicle_ip: string | null;
}

export const getHealth = async () => {
  const response = await api.get('/healthz');
  return response.data;
};

export const getVehicles = async () => {
  const response = await api.get('/v1/vehicles');
  return response.data.vehicles as Vehicle[];
};

export const registerVehicle = async (vehicle: Partial<Vehicle>) => {
  const response = await api.post('/v1/vehicles', vehicle);
  return response.data;
};

export const getTools = async (ip?: string) => {
  const params = ip ? { ip } : {};
  const response = await api.get('/v1/tools', { params });
  return response.data.tools as Tool[];
};

export interface Session {
  session_id: string;
  created_at: string;
  updated_at: string;
}

export const getSessions = async () => {
  const response = await api.get('/v1/sessions');
  return response.data.sessions as Session[];
};

export const getSessionMemory = async (sessionId: string) => {
  const response = await api.get(`/v1/sessions/${sessionId}/memory`);
  return response.data as SessionMemory;
};

export const resetSession = async (sessionId: string) => {
  const response = await api.post(`/v1/sessions/${sessionId}/reset`);
  return response.data;
};

export const CHAT_STREAM_URL = `${API_BASE_URL}/v1/chat/stream`;
export const CHAT_STREAM_UPLOAD_URL = `${API_BASE_URL}/v1/chat/stream/upload`;

export default api;
