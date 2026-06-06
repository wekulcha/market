import type { ReactNode } from 'react';

interface MiniAppShellProps {
  children: ReactNode;
}

export function MiniAppShell({ children }: MiniAppShellProps) {
  return (
    <div className="min-h-screen flex justify-center bg-slate-100">
      <div className="w-full max-w-[430px] bg-neutral-50 px-4 py-4 lg:rounded-3xl">
        {children}
      </div>
    </div>
  );
}
