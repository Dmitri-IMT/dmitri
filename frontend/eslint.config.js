import js from '@eslint/js'
import local from './eslint-rules/index.js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: [
      'src/components/ui/**',
      'src/**/*.test.{ts,tsx}',
      'src/test/**',
    ],
    plugins: {
      local,
    },
    rules: {
      'local/no-arbitrary-utility': 'error',
      'local/no-raw-type-size': 'error',
      'local/spacing-scale': 'error',
      'local/no-bare-interactive': 'error',
      'local/no-raw-hex': 'error',
      'local/no-dark-variant': 'error',
    },
  },
)
