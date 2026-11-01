import { useCallback, useState } from 'react';

export function useLocalStorage(key, initialValue) {
  const [value, setValue] = useState(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored == null ? initialValue : JSON.parse(stored);
    } catch {
      return initialValue;
    }
  });

  const update = useCallback((nextValue) => {
    setValue((current) => {
      const resolved = typeof nextValue === 'function' ? nextValue(current) : nextValue;
      try {
        localStorage.setItem(key, JSON.stringify(resolved));
      } catch {
        return current;
      }
      return resolved;
    });
  }, [key]);

  return [value, update];
}
