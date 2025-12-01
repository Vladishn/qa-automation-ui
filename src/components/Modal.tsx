// src/components/Modal.tsx
import React from 'react';

interface ModalProps {
  open: boolean;
  title?: string;
  onClose: () => void;
  children: React.ReactNode;
}

const Modal: React.FC<ModalProps> = ({ open, title, onClose, children }) => {
  if (!open) return null;

  const backdropStyle: React.CSSProperties = {
    position: 'fixed',
    inset: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.65)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000
  };

  const modalStyle: React.CSSProperties = {
    backgroundColor: '#080b12',
    borderRadius: 12,
    border: '1px solid rgba(255,255,255,0.08)',
    width: 'min(900px, 95vw)',
    maxHeight: '85vh',
    boxShadow: '0 18px 45px rgba(0,0,0,0.55)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden'
  };

  const headerStyle: React.CSSProperties = {
    padding: '12px 16px',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12
  };

  const titleStyle: React.CSSProperties = {
    fontSize: 16,
    fontWeight: 600
  };

  const closeBtnStyle: React.CSSProperties = {
    border: '1px solid rgba(255,255,255,0.2)',
    borderRadius: 999,
    padding: '4px 10px',
    background: 'transparent',
    color: 'inherit',
    cursor: 'pointer',
    fontSize: 13
  };

  const bodyStyle: React.CSSProperties = {
    padding: 16,
    overflowY: 'auto'
  };

  return (
    <div style={backdropStyle} onClick={onClose}>
      <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
        <div style={headerStyle}>
          <div style={titleStyle}>{title}</div>
          <button type="button" style={closeBtnStyle} onClick={onClose}>
            Close
          </button>
        </div>
        <div style={bodyStyle}>{children}</div>
      </div>
    </div>
  );
};

export default Modal;
