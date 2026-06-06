import React, { PropsWithChildren } from "react";

export const AdminAppShell: React.FC<PropsWithChildren> = ({ children }) => {
  return (
    <div className="min-h-dvh w-full bg-slate-900 md:p-4 xl:p-6">
      <div className="mx-auto flex min-h-dvh w-full max-w-screen-2xl items-stretch justify-center md:min-h-[calc(100dvh-2rem)]">
        <div className="flex min-h-dvh w-full flex-col overflow-hidden bg-slate-50 shadow-xl md:min-h-[calc(100dvh-2rem)] md:max-h-[calc(100dvh-2rem)] md:rounded-3xl lg:max-w-5xl xl:max-w-6xl">
        {children}
        </div>
      </div>
    </div>
  );
};
