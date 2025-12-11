import React from 'react';

export const QA_CARD_BASE =
  'w-full rounded-3xl border border-slate-800 bg-slate-950/60 text-slate-100 shadow-xl';

interface DashboardCardProps {
  title?: string;
  rightSlot?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  children: React.ReactNode;
}

export const DashboardCard: React.FC<DashboardCardProps> = ({
  title,
  rightSlot,
  className = '',
  bodyClassName = '',
  children
}) => {
  const headerProvided = Boolean(title || rightSlot);
  const outerClassName = `${QA_CARD_BASE} ${className}`.trim();
  const bodyClasses = `px-8 py-6 ${bodyClassName}`.trim();

  return (
    <section className={outerClassName}>
      {headerProvided && (
        <header className="flex items-center justify-between border-b border-slate-800 px-8 py-4">
          {title ? (
            <h2 className="text-sm font-semibold tracking-tight text-slate-100">{title}</h2>
          ) : (
            <span />
          )}
          {rightSlot && <div className="text-xs text-slate-400">{rightSlot}</div>}
        </header>
      )}
      <div className={bodyClasses}>{children}</div>
    </section>
  );
};
