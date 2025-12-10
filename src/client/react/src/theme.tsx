/**
 * theme.tsx
 * Ant Design theme configuration for the application.
 * - Defines global color tokens and font family.
 * - Customizes component-specific styles for Layout, Card, Collapse, and Button.
 */

import { blue } from '@ant-design/colors';

export const appTheme = {
  token: {
    // Global color and font tokens
    colorPrimary: blue[5], // Main brand color
    colorBorderSecondary: blue[1], // Secondary border color
    colorTextBase: '#1f1f1f', // Base text color
    fontFamily: "'Open Sans', sans-serif", // Global font
  },
  components: {
    // Component-specific customizations
    Layout: {
      bodyBg: '#e6f4ff', // Light blue background for layout
    },
    Card: {
      borderRadius: 12,
      boxShadow: '0 4px 10px rgba(0, 0, 0, 0.05)',
      headerBg: blue[1], // Card header background
    },
    Collapse: {
      headerPadding: '12px 24px',
      contentPadding: '16px',
    },
    Button: {
      colorPrimary: blue[5],
      fontWeight: 600,
    },
  },
};
