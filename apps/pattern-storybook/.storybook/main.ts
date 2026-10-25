import type { StorybookConfig } from '@storybook/react-vite';

const config: StorybookConfig = {
  framework: '@storybook/react-vite',
  stories: ['../stories/**/*.stories.tsx'],
  addons: ['@storybook/addon-docs', '@storybook/addon-a11y'],
  core: { disableTelemetry: true },
  staticDirs: [
    { from: '../../web/public/brand', to: '/brand' },
    { from: '../../web/src/app/icon.svg', to: '/favicon.svg' },
  ],
};
export default config;
