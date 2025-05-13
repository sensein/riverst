import { blue } from '@ant-design/colors';
import Panel from 'antd/es/splitter/Panel';

export const appTheme = {
  token: {
    colorPrimary: blue[5],
    colorBorderSecondary: blue[1],
    colorTextBase: '#1f1f1f',
    fontFamily: "'Open Sans', sans-serif",
  },
  components: {
    Layout: {
      bodyBg: '#e6f4ff',
    },
    Card: {
      borderRadius: 12,
      boxShadow: '0 4px 10px rgba(0, 0, 0, 0.05)',
      headerBg: blue[1],
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
