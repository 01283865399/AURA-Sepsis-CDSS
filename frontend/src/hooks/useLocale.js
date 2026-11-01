import { useTranslation } from 'react-i18next';

export function useLocale() {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';
  return {
    isEnglish,
    text: (arabic, english) => isEnglish ? english : arabic,
  };
}
