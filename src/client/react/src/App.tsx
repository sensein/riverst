import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Homepage from './pages/Homepage';
import AdvancedAvatarCreatorPage from './pages/AdvancedAvatarCreatorPage';
import AvatarCreatorPage from './pages/AvatarCreatorPage';
import AvatarInteraction from './pages/AvatarInteraction';

const App = () => {
  return (
    <Router>
      <Routes>
        <Route path='/' element={<Homepage />} />
        <Route path='/advanced-avatar-creation' element={<AdvancedAvatarCreatorPage />} />
        <Route path='/avatar-creation' element={<AvatarCreatorPage />} />
        <Route path='/avatar-interaction' element={<AvatarInteraction />} />
      </Routes>
    </Router>
  );
};

export default App;
