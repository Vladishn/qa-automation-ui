import React, { CSSProperties, useEffect, useState } from 'react';

type BackendStatus = 'UP' | 'DOWN';

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
  UP: {
    color: '#2ecc71',
    background: 'rgba(46, 204, 113, 0.15)',
  },
  DOWN: {
    color: '#e74c3c',
    background: 'rgba(231, 76, 60, 0.15)',
  },
};

const TopBar: React.FC = () => {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('DOWN');

  useEffect(() => {
    let isMounted = true;

    const resolveBaseUrl = () => {
      try {
        // @ts-ignore
        if (typeof API_BASE_URL !== 'undefined') return API_BASE_URL;
      } catch {}
      try {
        // @ts-ignore
        if (typeof apiBaseUrl !== 'undefined') return apiBaseUrl;
      } catch {}
      return (
        import.meta.env.VITE_QUICKSET_API_BASE_URL ??
        import.meta.env.VITE_API_BASE_URL ??
        'http://localhost:8000'
      );
    };

    const baseUrl = resolveBaseUrl();
    const url = `${baseUrl}/health`;

    const checkHealth = async () => {
      if (!isMounted) return;

      try {
        const res = await fetch(url, {
          method: 'GET',
        });

        if (!isMounted) return;

        if (res.ok) {
          setBackendStatus('UP');
        } else {
          setBackendStatus('DOWN');
        }
      } catch (error: any) {
        if (!isMounted) return;
        setBackendStatus('DOWN');
      }
    };

    checkHealth();
    const intervalId = window.setInterval(checkHealth, 15_000);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const backendBadgeClass = `backend-status backend-status--${backendStatus} `;
  const statusStyle: CSSProperties = {
    ...backendStatusBaseStyle,
    ...backendStatusVariants[backendStatus],
  };
  const statusText = backendStatus === 'UP' ? 'Backend: UP' : 'Backend: DOWN';

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
        <span className={backendBadgeClass.trim()} style={statusStyle}>
          {statusText}
        </span>
      </div>
    </header>
  );
};

export default TopBar;
