import React from 'react';

const Dashboard: React.FC = () => {
  return (
    <section>
      <h2 className="page-title">Overview</h2>
      <p className="page-subtitle">
        Overall view of all QA test coverage across STB Firmware and Partner TV Applications.
      </p>

      <div className="grid-3">
        <div className="card">
          <h3>FW · STB</h3>
          <p>Tracks S70PCI, Jade, and SEI X4 firmware tests and QuickSet flows.</p>
          <div className="metric">
            <span className="metric-label">Overall Pass Rate</span>
            <span className="metric-value">–%</span>
          </div>
        </div>

        <div className="card">
          <h3>Partner TV · Apps</h3>
          <p>Covers App versions for Android TV, Mobile, Smart TV, Apple TV, and iOS.</p>
          <div className="metric">
            <span className="metric-label">Platforms Covered</span>
            <span className="metric-value">0 / 7</span>
          </div>
        </div>

        <div className="card">
          <h3>Open Issues</h3>
          <p>Critical & High issues for Jira and management overview.</p>
          <div className="metric">
            <span className="metric-label">Critical / High</span>
            <span className="metric-value">0 / 0</span>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Dashboard;
