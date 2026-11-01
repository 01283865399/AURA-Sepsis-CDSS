import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

const MAX_HISTORY = 100;

export const usePredictionStore = create(persist(
  (set) => ({
    history: [],
    addRecord: (record) => set((state) => ({
      history: [record, ...state.history].slice(0, MAX_HISTORY),
    })),
    clearHistory: () => set({ history: [] }),
    removeRecord: (id) => set((state) => ({
      history: state.history.filter((record) => record.id !== id),
    })),
  }),
  {
    name: 'aura-prediction-history-v1',
    storage: createJSONStorage(() => localStorage),
  },
));
