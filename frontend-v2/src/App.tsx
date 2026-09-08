import { HashRouter, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/shell/AppShell';
import { AuthProvider, useAuth } from './lib/AuthContext';
import { Dashboard } from './pages/Dashboard';
import { Login } from './pages/Login';
import { Messages } from './pages/Messages';
import { Requests } from './pages/Requests';
import { Suppliers } from './pages/Suppliers';

function Gate() {
  const { status } = useAuth();

  if (status === 'loading') {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-canvas text-[13px] text-ink-muted">
        Подключение к SupplyDesk…
      </div>
    );
  }

  if (status === 'anonymous') return <Login />;

  return (
    <HashRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="requests" element={<Requests />} />
          <Route path="suppliers" element={<Suppliers />} />
          <Route path="messages" element={<Messages />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}
