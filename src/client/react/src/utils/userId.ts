import FingerprintJS from '@fingerprintjs/fingerprintjs';

export const getConsistentUserIdByDevice = async (): Promise<string> => {
  const fp = await FingerprintJS.load();
  const result = await fp.get();
  return result.visitorId; // consistent across sessions on same browser
};

export const getRandomUserId = (): string => {
  return crypto.randomUUID(); // generates a new unique ID every time
};
