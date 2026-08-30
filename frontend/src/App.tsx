import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/lib/auth';
import { Layout } from '@/components/Layout';
import { RequestPage } from '@/components/RequestPage';
import { Dashboard } from '@/pages/Dashboard';
import { RequestsList } from '@/pages/RequestsList';
import { NewRequest } from '@/pages/NewRequest';
import { Login } from '@/pages/Login';
import { Messages } from '@/pages/Messages';
import { Suppliers } from '@/pages/Suppliers';
import { Blacklist } from '@/pages/Blacklist';
import { Settings } from '@/pages/Settings';
import { NotFound } from '@/pages/NotFound';
import { CampaignPage } from '@/pages/CampaignPage';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-ink-400">Загрузка…</div>
    );
  }
  if (status === 'anonymous') return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/requests" element={<RequestsList />} />
        <Route path="/requests/new" element={<NewRequest />} />
        <Route path="/requests/:id" element={<RequestPage />} />
        <Route path="/messages" element={<Messages />} />
        <Route path="/mail/campaigns/:id" element={<CampaignPage />} />
        <Route path="/suppliers" element={<Suppliers />} />
        <Route path="/blacklist" element={<Blacklist />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
