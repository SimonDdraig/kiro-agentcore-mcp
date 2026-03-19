// Copyright 2025 Bush Ranger AI Project. All rights reserved.
/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

const nodeModules = path.resolve(__dirname, 'node_modules');

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    fs: {
      strict: false,
      allow: ['..'],
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['../tests/frontend/**/*.test.{ts,tsx}'],
    alias: [
      { find: /^@testing-library\/(.*)$/, replacement: path.join(nodeModules, '@testing-library/$1') },
      { find: /^react$/, replacement: path.join(nodeModules, 'react') },
      { find: /^react\/(.*)$/, replacement: path.join(nodeModules, 'react/$1') },
      { find: /^react-dom$/, replacement: path.join(nodeModules, 'react-dom') },
      { find: /^react-dom\/(.*)$/, replacement: path.join(nodeModules, 'react-dom/$1') },
      { find: /^amazon-cognito-identity-js$/, replacement: path.join(nodeModules, 'amazon-cognito-identity-js') },
      { find: /^fast-check$/, replacement: path.join(nodeModules, 'fast-check') },
    ],
  },
});
