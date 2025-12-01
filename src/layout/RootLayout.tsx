import React, { ReactNode } from 'react';
import Sidebar from '../components/Sidebar';
import TopBar from '../components/TopBar';
import type { PageId } from '../App';

interface Props {
  currentPage: PageId;
  onChangePage: (page: PageId) => void;
  children: ReactNode;
}

const RootLayout: React.FC<Props> = ({ currentPage, onChangePage, children }) => {
  return (
    <div className="app-root">
      <Sidebar currentPage={currentPage} onChangePage={onChangePage} />
      <div className="main-area">
        <TopBar />
        <main className="content">{children}</main>
      </div>
    </div>
  );
};

export default RootLayout;
