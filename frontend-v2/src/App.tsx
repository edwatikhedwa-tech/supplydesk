import { lazy, Suspense } from 'react';
import { HashRouter, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/shell/AppShell';
import { AuthProvider, useAuth } from './lib/AuthContext';

const Blacklist = lazy(() => import('./pages/Blacklist').then(({ Blacklist }) => ({ default: Blacklist })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(({ Dashboard }) => ({ default: Dashboard })));
const Login = lazy(() => import('./pages/Login').then(({ Login }) => ({ default: Login })));
const Messages = lazy(() => import('./pages/Messages').then(({ Messages }) => ({ default: Messages })));
const RequestDetail = lazy(() => import('./pages/RequestDetail').then(({ RequestDetail }) => ({ default: RequestDetail })));
const Requests = lazy(() => import('./pages/Requests').then(({ Requests }) => ({ default: Requests })));
const Settings = lazy(() => import('./pages/Settings').then(({ Settings }) => ({ default: Settings })));
const SupplierDetail = lazy(() => import('./pages/SupplierDetail').then(({ SupplierDetail }) => ({ default: SupplierDetail })));
const Suppliers = lazy(() => import('./pages/Suppliers').then(({ Suppliers }) => ({ default: Suppliers })));

function PageFallback() {
  return <div className="flex h-full items-center justify-center text-[13px] text-ink-muted">Загружаем экран…</div>;
}

function Gate() {
  const { status } = useAuth();

  if (status === 'loading') {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-canvas text-[13px] text-ink-muted">
        Подключение к SupplyDesk…
      </div>
    );
  }

  if (status === 'anonymous') {
    return (
      <Suspense fallback={<PageFallback />}>
        <Login />
      </Suspense>
    );
  }

  return (
    <Suspense fallback={<PageFallback />}>
      <HashRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="requests" element={<Requests />} />
            <Route path="requests/:id" element={<RequestDetail />} />
            <Route path="suppliers" element={<Suppliers />} />
            <Route path="suppliers/:id" element={<SupplierDetail />} />
            <Route path="messages" element={<Messages />} />
            <Route path="blacklist" element={<Blacklist />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </HashRouter>
    </Suspense>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}
