import { addons } from 'storybook/manager-api';
import { create } from 'storybook/theming';

addons.setConfig({
  theme: create({
    base: 'light', brandTitle: 'JHW Pattern', brandUrl: 'https://groupware.pikan.dev/pattern',
    brandImage: './brand/jhworks-wordmark.svg', brandTarget: '_blank',
    colorPrimary: '#6554cf', colorSecondary: '#6554cf',
  }),
});
