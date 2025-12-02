import React, { useState } from 'react';
import RootLayout from './layout/RootLayout';
import Dashboard from './pages/Dashboard';
import FirmwareTests from './pages/FirmwareTests';
import AppTests from './pages/AppTests';
import Reports from './pages/Reports';
import QuickSetRunner from './pages/QuickSetRunner';

export type PageId =
  | 'dashboard'
  | 'fw-tests'
  | 'fw-s70'
  | 'fw-jade'
  | 'fw-x4'
  | 'fw-x4-quickset'
  | 'app-tests'
  | 'app-android-tv-vstb'
  | 'app-android-mobile'
  | 'app-smart-tv-lg'
  | 'app-smart-tv-samsung'
  | 'app-apple-tv'
  | 'app-ios'
  | 'reports';

const FwDevicePlaceholder: React.FC<{ deviceLabel: string }> = ({ deviceLabel }) => {
  return (
    <div className="page">
      <h1 className="page-title">FW Tests · STB — {deviceLabel}</h1>
      <p className="page-subtitle">
        This is a placeholder for device-specific FW tests for {deviceLabel}. Future FW
        scenarios and results for this STB will appear here.
      </p>
    </div>
  );
};

const AppClientPlaceholder: React.FC<{ clientLabel: string }> = ({ clientLabel }) => {
  return (
    <div className="page">
      <h1 className="page-title">App Tests · Platform — {clientLabel}</h1>
      <p className="page-subtitle">
        This is a placeholder for app/client-specific tests and dashboards for{' '}
        {clientLabel}. Future test flows and analytics for this platform will appear here.
      </p>
    </div>
  );
};

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<PageId>('dashboard');

  const renderPage = () => {
    switch (currentPage) {
      case 'fw-tests':
        // Existing generic FW Tests page – stays as-is
        return <FirmwareTests />;

      case 'fw-s70':
        return <FwDevicePlaceholder deviceLabel="S70" />;

      case 'fw-jade':
        return <FwDevicePlaceholder deviceLabel="Jade" />;

      case 'fw-x4':
        return <FwDevicePlaceholder deviceLabel="SEI X4" />;

      case 'fw-x4-quickset':
        // Full QuickSet runner page (summary, logs, steps, questions, etc.)
        return <QuickSetRunner />;

      case 'app-tests':
        // Existing generic App Tests page – stays as-is
        return <AppTests />;

      case 'app-android-tv-vstb':
        return <AppClientPlaceholder clientLabel="Android TV vSTB" />;

      case 'app-android-mobile':
        return <AppClientPlaceholder clientLabel="Android Mobile" />;

      case 'app-smart-tv-lg':
        return <AppClientPlaceholder clientLabel="Smart TV LG" />;

      case 'app-smart-tv-samsung':
        return <AppClientPlaceholder clientLabel="Smart TV Samsung" />;

      case 'app-apple-tv':
        return <AppClientPlaceholder clientLabel="Apple TV" />;

      case 'app-ios':
        return <AppClientPlaceholder clientLabel="iOS" />;

      case 'reports':
        return <Reports />;

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
