import FingerprintJS from '@fingerprintjs/fingerprintjs';

export const getUserId = async (): Promise<string> => {
  const fp = await FingerprintJS.load();
  const result = await fp.get();
  return result.visitorId; // consistent across sessions on same browser
};
