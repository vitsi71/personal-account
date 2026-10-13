// Проверяем местное время компьютера и преобразование выбранной даты в UTC.
import test from 'node:test';
import assert from 'node:assert/strict';
import { toUtc, formatRussian } from '../static/time.mjs';

test('Календарное время преобразуется в UTC с учётом часового пояса компьютера', () => {
  const local = new Date(2026, 11, 20, 15, 30);
  assert.equal(toUtc('2026-12-20T15:30'), local.toISOString());
});

test('Дата отображается по-русски в местном времени', () => {
  const local = new Date(2026, 11, 20, 15, 30);
  assert.equal(formatRussian(local.toISOString()), '20.12.2026 15:30');
});

test('Несуществующая календарная дата не нормализуется молча', () => {
  assert.throws(() => toUtc('2026-02-30T15:30'), RangeError);
  assert.throws(() => toUtc(''), RangeError);
});

test('Зимнее и летнее время преобразуются по правилам компьютера', () => {
  // Ожидаемые значения заданы независимо: Москва UTC+3, Нью-Йорк UTC−5/UTC−4.
  const fixtures = {
    'Europe/Moscow': ['2026-01-20T12:30:00.000Z', '2026-07-20T12:30:00.000Z'],
    'America/New_York': ['2026-01-20T20:30:00.000Z', '2026-07-20T19:30:00.000Z'],
  };
  const expected = fixtures[Intl.DateTimeFormat().resolvedOptions().timeZone];
  if (expected) {
    assert.equal(toUtc('2026-01-20T15:30'), expected[0]);
    assert.equal(toUtc('2026-07-20T15:30'), expected[1]);
  }
});

test('Пропущенный при переходе на летнее время час отклоняется', {
  skip: Intl.DateTimeFormat().resolvedOptions().timeZone !== 'America/New_York',
}, () => {
  assert.throws(() => toUtc('2026-03-08T02:30'), RangeError);
});
