import React, { useState } from 'react';
import RootLayout from './layout/RootLayout';
import Dashboard from './pages/Dashboard';
import FirmwareTests from './pages/FirmwareTests';
import AppTests from './pages/AppTests';
import Reports from './pages/Reports';
import QuickSetRunner from './pages/QuickSetRunner';

export type PageId = 'dashboard' | 'fw-tests' | 'app-tests' | 'reports' | 'quickset';

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<PageId>('dashboard');

  const renderPage = () => {
    switch (currentPage) {
      case 'fw-tests':
        return <FirmwareTests />;
      case 'app-tests':
        return <AppTests />;
      case 'reports':
        return <Reports />;
      case 'quickset':
        return <QuickSetRunner />;
      case 'dashboard':
      default:
        return <Dashboard />;
    }
  };

  return (
    <RootLayout currentPage={currentPage} onChangePage={setCurrentPage}>
      {renderPage()}
    </RootLayout>
  );
};

export default App;
