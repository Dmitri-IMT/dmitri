import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useState } from 'react';

import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import ForgotPassword from './pages/ForgotPassword';
import DashboardLayout from './components/layout/DashboardLayout';

import Home from './pages/Home';
import MyDevices from './pages/MyDevices';
import Problems from './pages/Problems';
import Devices from './pages/Devices';
import NewScan from './pages/NewScan';
import Scanning from './pages/Scanning';
import History from './pages/History';
import Settings from './pages/Settings';

function App() {

  const navigate = useNavigate();

  const [isAuthenticated, setIsAuthenticated] = useState(() => 
    sessionStorage.getItem('dmitri_auth') === 'true'
  );

  const login = () => {
    sessionStorage.setItem('dmitri_auth', 'true');
    setIsAuthenticated(true);
    navigate('/dashboard');
  };

  const logout = () => {
    sessionStorage.removeItem('dmitri_auth');
    setIsAuthenticated(false);
    navigate('/');
  };

  return (
    <Routes>
      {/* Telas públicas */}
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={
        isAuthenticated ? <Navigate to="/dashboard" replace /> : <Login onLogin={login} />
      } />
      <Route path="/register" element={
        isAuthenticated ? <Navigate to="/dashboard" replace /> : <Register onRegister={login} />
      } />

      <Route path="/forgot-password" element={
        isAuthenticated ? <Navigate to="/dashboard" replace /> : <ForgotPassword />
      } />

      {/* Dashboard protegido */}
      <Route path="/dashboard" element={
        isAuthenticated ? <DashboardLayout onLogout={logout} /> : <Navigate to="/" replace />
      }>
        <Route index element={<Home />} />
        <Route path="my-devices" element={<MyDevices />} />
        <Route path="problems" element={<Problems />} />
        <Route path="devices" element={<Devices />} />
        <Route path="scan" element={<NewScan />} />
        <Route path="progress" element={<Scanning />} />
        <Route path="history" element={<History />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}

export default App;