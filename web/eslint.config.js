import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

export default tseslint.config(
  { ignores: ['dist'] },
  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { globals: globals.browser },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
    },
  },
  /* FSD: слой импортирует только нижележащие слои */
  {
    files: ['src/{shared,entities,features,widgets}/**/*.{ts,tsx}'],
    rules: { 'no-restricted-imports': ['error', { patterns: [{ group: ['@/pages/*', '@/app/*'], message: 'FSD: нижние слои не импортируют верхние.' }] }] },
  },
  {
    files: ['src/pages/**/*.{ts,tsx}'],
    rules: { 'no-restricted-imports': ['error', { patterns: [{ group: ['@/app/*'], message: 'FSD: страницы не импортируют слой app.' }] }] },
  },
);
