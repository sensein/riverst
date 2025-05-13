export const getUserId = (): string => {
  const storedId = localStorage.getItem('user_id');
  if (storedId) return storedId;
  const generatedId = 'user_' + Math.random().toString(36).substr(2, 9);
  localStorage.setItem('user_id', generatedId);
  return generatedId;
};

export const setUserId = (id: string): void => {
  localStorage.setItem('user_id', id);
};
