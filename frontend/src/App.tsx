import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/lib/auth';
import { Layout } from '@/components/Layout';
import { RequestPage } from '@/components/RequestPage';

const Dashboard = lazy(() => import('@/pages/Dashboard').then(({ Dashboard: component }) => ({ default: component })));
const RequestsList = lazy(() => import('@/pages/RequestsList').then(({ RequestsList: component }) => ({ default: component })));
const NewRequest = lazy(() => import('@/pages/NewRequest').then(({ NewRequest: component }) => ({ default: component })));
const Login = lazy(() => import('@/pages/Login').then(({ Login: component }) => ({ default: component })));
const Messages = lazy(() => import('@/pages/Messages').then(({ Messages: component }) => ({ default: component })));
const Suppliers = lazy(() => import('@/pages/Suppliers').then(({ Suppliers: component }) => ({ default: component })));
const Blacklist = lazy(() => import('@/pages/Blacklist').then(({ Blacklist: component }) => ({ default: component })));
const Settings = lazy(() => import('@/pages/Settings').then(({ Settings: component }) => ({ default: component })));
const NotFound = lazy(() => import('@/pages/NotFound').then(({ NotFound: component }) => ({ default: component })));
const CampaignPage = lazy(() => import('@/pages/CampaignPage').then(({ CampaignPage: component }) => ({ default: component })));

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
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-sm text-ink-400">Загрузка…</div>}>
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
    </Suspense>
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
