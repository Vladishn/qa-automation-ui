import React, { CSSProperties, useEffect, useState } from 'react';

type BackendStatus = 'unknown' | 'ok' | 'down';

const HEALTH_ENDPOINT = 'http://localhost:8000/health';

const backendStatusBaseStyle: CSSProperties = {
  marginLeft: '12px',
  padding: '2px 10px',
  borderRadius: '999px',
  fontSize: '12px',
  border: '1px solid var(--color-border)',
  display: 'inline-flex',
  alignItems: 'center',
  minWidth: '90px',
  justifyContent: 'center',
};

const backendStatusVariants: Record<BackendStatus, CSSProperties> = {
  unknown: {
    color: 'var(--color-text-muted)',
    background: 'rgba(255, 255, 255, 0.05)',
    opacity: 0.8,
  },
  ok: {
    color: '#2ecc71',
    background: 'rgba(46, 204, 113, 0.15)',
  },
  down: {
    color: '#e74c3c',
    background: 'rgba(231, 76, 60, 0.15)',
  },
};

const TopBar: React.FC = () => {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('unknown');
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const checkHealth = async () => {
      try {
        const response = await fetch(HEALTH_ENDPOINT);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data: { status?: string } = await response.json();
        if (data?.status === 'ok') {
          if (isMounted) {
            setBackendStatus('ok');
            setLastError(null);
            setLastChecked(new Date());
          }
        } else {
          throw new Error('Unexpected response payload');
        }
      } catch (error) {
        console.error('[BackendHealth]', error);
        if (isMounted) {
          setBackendStatus('down');
          setLastError(error instanceof Error ? error.message : 'Unknown error');
          setLastChecked(new Date());
        }
      }
    };

    checkHealth();
    const intervalId = window.setInterval(checkHealth, 30_000);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const tooltip = lastChecked
    ? `Last checked: ${lastChecked.toLocaleTimeString()}${lastError ? `\nError: ${lastError}` : ''}`
    : 'Backend status not checked yet';

  const statusLabel = backendStatus === 'ok' ? 'OK' : backendStatus === 'down' ? 'DOWN' : '...';
  const statusStyle: CSSProperties = {
    ...backendStatusBaseStyle,
    ...backendStatusVariants[backendStatus],
  };

  return (
    <header className="top-bar">
      <div className="top-bar-left">
        <h1 className="top-bar-title">QA Control Center</h1>
        <span className="top-bar-subtitle">Partner TV · STB & Apps</span>
      </div>
      <div className="top-bar-right">
        <select className="top-bar-select">
          <option>Release: Auto</option>
          <option>Release: 25.3.303</option>
          <option>Release: FW_3.1.0_SEI_X4</option>
        </select>
        <select className="top-bar-select">
          <option>Env: QA</option>
          <option>Env: DEV</option>
          <option>Env: STAGE</option>
          <option>Env: PROD</option>
        </select>
        <span className={`backend-status backend-status--${backendStatus}`} style={statusStyle} title={tooltip}>
          Backend: {statusLabel}
        </span>
      </div>
    </header>
  );
};

export default TopBar;
