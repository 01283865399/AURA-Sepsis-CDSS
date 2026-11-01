import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

export const useUiStore = create(persist(
  (set) => ({
    theme: 'dark',
    language: 'ar',
    sidebarOpen: false,
    toggleTheme: () => set((state) => ({ theme: state.theme === 'light' ? 'dark' : 'light' })),
    setLanguage: (language) => set({ language }),
    setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  }),
  {
    name: 'aura-ui-preferences',
    storage: createJSONStorage(() => localStorage),
    partialize: ({ theme, language }) => ({ theme, language }),
  },
));
