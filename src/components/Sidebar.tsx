import React, { useState } from 'react';
import type { PageId } from '../App';

interface SidebarProps {
  currentPage: PageId;
  onChangePage: (page: PageId) => void;
}

const FW_PAGES: PageId[] = ['fw-tests', 'fw-s70', 'fw-jade', 'fw-x4', 'fw-x4-quickset'];
const APP_PAGES: PageId[] = [
  'app-tests',
  'app-android-tv-vstb',
  'app-android-mobile',
  'app-smart-tv-lg',
  'app-smart-tv-samsung',
  'app-apple-tv',
  'app-ios',
];

const Sidebar: React.FC<SidebarProps> = ({ currentPage, onChangePage }) => {
  const [fwOpen, setFwOpen] = useState<boolean>(true);
  const [appOpen, setAppOpen] = useState<boolean>(true);

  const isFwActive = FW_PAGES.includes(currentPage);
  const isAppActive = APP_PAGES.includes(currentPage);

  const navButtonClass = (id: PageId, extra?: string) =>
    ['sidebar-item', currentPage === id ? 'active' : '', extra ?? '']
      .filter(Boolean)
      .join(' ');

  return (
    <aside className="sidebar">
      {/* HEADER / LOGO */}
      <div className="sidebar-header">
        <div className="logo-mark">QA</div>
        <div className="logo-text">QA Automation UI</div>
      </div>

      <nav className="sidebar-nav">
        {/* Dashboard */}
        <button
          className={navButtonClass('dashboard')}
          onClick={() => onChangePage('dashboard')}
        >
          Dashboard
        </button>

        {/* FW Tests · STB group */}
        <div className="sidebar-group">
          <button
            className={[
              'sidebar-item',
              'sidebar-parent',
              isFwActive ? 'active' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            onClick={() => setFwOpen((open) => !open)}
          >
            FW Tests (STB)
          </button>

          {fwOpen && (
            <div className="sidebar-children">
              <button
                className={navButtonClass('fw-tests', 'sidebar-child')}
                onClick={() => onChangePage('fw-tests')}
              >
                Overview
              </button>
              <button
                className={navButtonClass('fw-s70', 'sidebar-child')}
                onClick={() => onChangePage('fw-s70')}
              >
                S70
              </button>
              <button
                className={navButtonClass('fw-jade', 'sidebar-child')}
                onClick={() => onChangePage('fw-jade')}
              >
                Jade
              </button>
              <button
                className={navButtonClass('fw-x4', 'sidebar-child')}
                onClick={() => onChangePage('fw-x4')}
              >
                X4
              </button>
              <button
                className={navButtonClass('fw-x4-quickset', 'sidebar-child nested')}
                onClick={() => onChangePage('fw-x4-quickset')}
              >
                QuickSet (X4)
              </button>
            </div>
          )}
        </div>

        {/* App Tests · Apps group */}
        <div className="sidebar-group">
          <button
            className={[
              'sidebar-item',
              'sidebar-parent',
              isAppActive ? 'active' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            onClick={() => setAppOpen((open) => !open)}
          >
            App Tests (Apps)
          </button>

          {appOpen && (
            <div className="sidebar-children">
              <button
                className={navButtonClass('app-tests', 'sidebar-child')}
                onClick={() => onChangePage('app-tests')}
              >
                Overview
              </button>
              <button
                className={navButtonClass('app-android-tv-vstb', 'sidebar-child')}
                onClick={() => onChangePage('app-android-tv-vstb')}
              >
                Android TV vSTB
              </button>
              <button
                className={navButtonClass('app-android-mobile', 'sidebar-child')}
                onClick={() => onChangePage('app-android-mobile')}
              >
                Android Mobile
              </button>
              <button
                className={navButtonClass('app-smart-tv-lg', 'sidebar-child')}
                onClick={() => onChangePage('app-smart-tv-lg')}
              >
                Smart TV LG
              </button>
              <button
                className={navButtonClass('app-smart-tv-samsung', 'sidebar-child')}
                onClick={() => onChangePage('app-smart-tv-samsung')}
              >
                Smart TV Samsung
              </button>
              <button
                className={navButtonClass('app-apple-tv', 'sidebar-child')}
                onClick={() => onChangePage('app-apple-tv')}
              >
                Apple TV
              </button>
              <button
                className={navButtonClass('app-ios', 'sidebar-child')}
                onClick={() => onChangePage('app-ios')}
              >
                iOS
              </button>
            </div>
          )}
        </div>

        {/* Reports */}
        <div className="sidebar-group sidebar-group-last">
          <button
            className={navButtonClass('reports')}
            onClick={() => onChangePage('reports')}
          >
            Reports &amp; Analytics
          </button>
        </div>
      </nav>
    </aside>
  );
};

export default Sidebar;
