/**
 * studentCode.ts
 * Helpers for student codes (teacher dashboard): remembering a code for this tab, building share links,
 * and copying to the clipboard.
 */

import { App } from "antd";
import axios from "axios";

export const STUDENT_CODE_KEY = "kiva_student_code";

/** Saves a student code for this browser tab; ignores storage errors. */
export const saveStudentCode = (code: string) => {
  try {
    sessionStorage.setItem(STUDENT_CODE_KEY, code.trim().toUpperCase());
  } catch {
    // Storage can be unavailable in private windows; the student can still type the code in the form.
  }
};

/** Reads the saved student code, if any. */
export const readStudentCode = (): string => {
  try {
    return sessionStorage.getItem(STUDENT_CODE_KEY) ?? "";
  } catch {
    return "";
  }
};

/** Full URL a student opens to start KIVA with their code. */
export const fullStudentLink = (link: string): string =>
  `${window.location.origin}${link}`;

/** Copies text and confirms with a toast. */
export const useCopy = () => {
  const { message } = App.useApp();
  return async (text: string, what: string) => {
    try {
      await navigator.clipboard.writeText(text);
      message.success(`${what} copied`);
    } catch {
      message.error(
        `Couldn't copy the ${what.toLowerCase()}. Select it and copy it by hand.`,
      );
    }
  };
};

/** HTTP status of a failed request, if it got a response. */
export const httpStatus = (err: unknown): number | undefined =>
  axios.isAxiosError(err) ? err.response?.status : undefined;

/** The server's plain-language `detail` message of a failed request, if any. */
export const httpDetail = (err: unknown): string | undefined => {
  const detail = axios.isAxiosError(err)
    ? err.response?.data?.detail
    : undefined;
  return typeof detail === "string" ? detail : undefined;
};
