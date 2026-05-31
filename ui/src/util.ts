// Shared, framework-agnostic helpers.

/** Parse the numeric value of an <input> event, defaulting to 0 on NaN. */
export function inputNumber(e: Event): number {
  return parseFloat((e.target as HTMLInputElement).value) || 0;
}

/** Read the checked state of a checkbox <input> event. */
export function inputChecked(e: Event): boolean {
  return (e.target as HTMLInputElement).checked;
}

/** RFC 4122 v4 id, using the platform crypto when available. */
export function uuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}
