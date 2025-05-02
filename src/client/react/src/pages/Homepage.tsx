import React from 'react';
import { useNavigate } from 'react-router-dom';

const Homepage = () => {
  const navigate = useNavigate();

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial' }}>
      <h1>Activities</h1>

      <ul style={{ listStyle: 'none', paddingLeft: 0 }}>
        <li>
          <strong>1.</strong> Basic avatar choice{' '}
          <button onClick={() => navigate('/avatar-creation')}>Start</button>
        </li>
        <li>
          <strong>2.</strong> Advanced avatar customization{' '}
          <button onClick={() => navigate('/advanced-avatar-creation')}>Start</button>
        </li>
        <li>
          <strong>3.</strong> Avatar interaction - Child vocabulary training{' '}
          <button onClick={() => navigate('/avatar-interaction')}>Start</button>
        </li>
        <li>
          <strong>4.</strong> Avatar interaction - Adult training{' '}
          <button disabled onClick={() => navigate('/avatar-interaction')}>Start</button>
        </li>
        <li>
          <strong>5.</strong> Read a book{' '}
          <button disabled>Open</button>
        </li>
      </ul>
    </div>
  );
};

export default Homepage;
