import { Outlet } from 'react-router';
import { Header } from './Header';
import { Toaster } from './ui/sonner';

export const Layout = () => {
  return (
    <div className="min-h-screen bg-white">
      <Header />
      <main>
        <Outlet />
      </main>
      <Toaster position="top-center" richColors />
    </div>
  );
};
