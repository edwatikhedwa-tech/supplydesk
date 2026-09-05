import { HashRouter, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/shell/AppShell';
import { Dashboard } from './pages/Dashboard';
import { Messages } from './pages/Messages';
import { Requests } from './pages/Requests';
import { Suppliers } from './pages/Suppliers';

export default function App() {
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
