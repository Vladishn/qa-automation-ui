import React from 'react';

interface StbIpFieldProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

const DEFAULT_SUBNET = '192.168.1.';

export const StbIpField: React.FC<StbIpFieldProps> = ({
  value,
  onChange,
  disabled
}) => {
  const [advancedMode, setAdvancedMode] = React.useState(false);

  // suffix לשלושת הספרות האחרונות
  const suffix =
    value && value.startsWith(DEFAULT_SUBNET)
      ? value.slice(DEFAULT_SUBNET.length)
      : '';

  const handleSuffixChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/[^\d]/g, '').slice(0, 3); // רק ספרות, עד 3
    const num = raw === '' ? '' : String(Math.min(255, Number(raw))); // הגבלה ל-0–255 (קליל)
    onChange(num === '' ? DEFAULT_SUBNET : `${DEFAULT_SUBNET}${num}`);
  };

  const handleAdvancedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
  };

  return (
    <div className="flex items-center gap-2">
      {!advancedMode ? (
        <div className="flex w-full items-center rounded-2xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 shadow-inner focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500/60">
          <span className="select-none text-slate-400 mr-1">
            {DEFAULT_SUBNET}
          </span>
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]{1,3}"
            className="flex-1 bg-transparent outline-none text-slate-100 placeholder:text-slate-500"
            placeholder="202"
            value={suffix}
            onChange={handleSuffixChange}
            disabled={disabled}
          />
        </div>
      ) : (
        <input
          type="text"
          className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 shadow-inner outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/60"
          placeholder={DEFAULT_SUBNET + '202'}
          value={value}
          onChange={handleAdvancedChange}
          disabled={disabled}
        />
      )}

      <button
        type="button"
        onClick={() => setAdvancedMode((v) => !v)}
        className="whitespace-nowrap rounded-xl border border-slate-700 px-2 py-1 text-[11px] font-medium text-slate-300 hover:border-slate-500 hover:text-slate-100 bg-slate-900/70"
        disabled={disabled}
      >
        {advancedMode ? 'Lock subnet' : 'Advanced'}
      </button>
    </div>
  );
};

export default StbIpField;
