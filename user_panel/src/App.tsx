import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { AuthContextProvider } from './context/AuthContext';
import { AppContextProvider } from './context/AppContext';
import { CartContextProvider } from './context/CartContext';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60 * 1000 },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthContextProvider>
        <AppContextProvider>
          <CartContextProvider>
            <RouterProvider router={router} />
          </CartContextProvider>
        </AppContextProvider>
      </AuthContextProvider>
    </QueryClientProvider>
  );
}

export default App;
