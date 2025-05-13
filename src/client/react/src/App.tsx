import { ConfigProvider } from 'antd';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Homepage from './pages/Homepage';
import { appTheme } from './theme';
import FullPageLoader from './components/FullPageLoader';

import { Suspense, lazy } from 'react';

const AdvancedAvatarCreatorPage = lazy(() => import('./pages/AdvancedAvatarCreatorPage'));
const AvatarCreatorPage = lazy(() => import('./pages/AvatarCreatorPage'));
const AvatarInteraction = lazy(() => import('./pages/AvatarInteraction'));
const AvatarInteractionSettings = lazy(() => import('./pages/AvatarInteractionSettings'));

const App = () => {
  return (
    <ConfigProvider theme={appTheme}>
      <Router>
        <Suspense fallback={<FullPageLoader />}>
          <Routes>
            <Route path="/" element={<Homepage />} />
            <Route path="/advanced-avatar-creation" element={<AdvancedAvatarCreatorPage />} />
            <Route path="/avatar-creation" element={<AvatarCreatorPage />} />
            <Route path="/avatar-interaction-settings" element={<AvatarInteractionSettings />} />
            <Route path="/avatar-interaction/:sessionId" element={<AvatarInteraction />} />
          </Routes>
        </Suspense>
      </Router>
    </ConfigProvider>
  );
};

export default App;