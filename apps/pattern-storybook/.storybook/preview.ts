import type { Preview } from '@storybook/react-vite';
import '@jhworks/pattern/tokens.css';
import '@jhworks/pattern/components.css';
import './preview.css';

const preview: Preview = {
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
    a11y: { test: 'error' },
    controls: { expanded: true },
    docs: { toc: true },
  },
};
export default preview;
