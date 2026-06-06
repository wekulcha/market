import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Restaurant } from '../types/restaurant';

export type ServiceType = 'DELIVERY' | 'DINE_IN';

export interface AppContextValue {
  serviceType: ServiceType;
  setServiceType: (type: ServiceType) => void;
  selectedRestaurant: Restaurant | null;
  setSelectedRestaurant: (restaurant: Restaurant | null) => void;
}

const AppContext = createContext<AppContextValue | undefined>(undefined);

export const AppContextProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [serviceType, setServiceType] = useState<ServiceType>('DELIVERY');
  const [selectedRestaurant, setSelectedRestaurant] = useState<Restaurant | null>(null);

  return (
    <AppContext.Provider value={{ serviceType, setServiceType, selectedRestaurant, setSelectedRestaurant }}>
      {children}
    </AppContext.Provider>
  );
};

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error('useAppContext must be used within AppContextProvider');
  }
  return ctx;
}

