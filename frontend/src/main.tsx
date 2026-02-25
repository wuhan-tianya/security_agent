import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App.tsx'
import MainLayout from './components/layout/MainLayout.tsx'
import './index.css'

import VehicleList from './features/vehicles/VehicleList'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<App />} />
          <Route path="vehicles" element={<VehicleList />} />
          <Route path="logs" element={<div className="p-4">Logs Page (To Be Implemented)</div>} />
          <Route path="settings" element={<div className="p-4">Settings Page (To Be Implemented)</div>} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
