import { describe, it, expect } from 'vitest';
import { inputNumber, inputChecked, uuid } from './util';

function inputEvent(props: { value?: string; checked?: boolean }): Event {
  return { target: props } as unknown as Event;
}

describe('inputNumber', () => {
  it('parses a numeric string', () => {
    expect(inputNumber(inputEvent({ value: '12.5' }))).toBe(12.5);
  });

  it('defaults empty input to 0', () => {
    expect(inputNumber(inputEvent({ value: '' }))).toBe(0);
  });

  it('defaults non-numeric input to 0', () => {
    expect(inputNumber(inputEvent({ value: 'abc' }))).toBe(0);
  });

  it('reads a leading number from mixed input', () => {
    expect(inputNumber(inputEvent({ value: '3px' }))).toBe(3);
  });
});

describe('inputChecked', () => {
  it('returns true when checked', () => {
    expect(inputChecked(inputEvent({ checked: true }))).toBe(true);
  });

  it('returns false when unchecked', () => {
    expect(inputChecked(inputEvent({ checked: false }))).toBe(false);
  });
});

describe('uuid', () => {
  it('produces unique v4-shaped ids', () => {
    const a = uuid();
    const b = uuid();
    expect(a).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
    expect(a).not.toBe(b);
  });
});
