import React from 'react';
import type { PageId } from '../App';

interface SidebarProps {
  currentPage: PageId;
  onChangePage: (page: PageId) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ currentPage, onChangePage }) => {
  const items: { id: PageId; label: string }[] = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'fw-tests', label: 'FW Tests (STB)' },
    { id: 'app-tests', label: 'App Tests (Partner TV)' },
    { id: 'reports', label: 'Reports & Analytics' },
    { id: 'quickset', label: 'QuickSet Runner' }
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="logo-mark">QA</span>
        <span className="logo-text">Automation</span>
      </div>
      <nav>
        {items.map((item) => (
          <button
            key={item.id}
            className={`sidebar-item ${currentPage === item.id ? 'active' : ''}`}
            onClick={() => onChangePage(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
    </aside>
  );
};

export default Sidebar;
