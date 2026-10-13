// Проверяем привязку опроса к второй секунде каждой календарной минуты.
import test from 'node:test';
import assert from 'node:assert/strict';
import { delayUntilNextCheck } from '../static/notifications.mjs';

test('Опрос привязан к :02, а не к моменту открытия страницы', () => {
  assert.equal(delayUntilNextCheck(new Date('2026-10-13T10:20:01Z')), 1000);
  assert.equal(delayUntilNextCheck(new Date('2026-10-13T10:20:02Z')), 60000);
  assert.equal(delayUntilNextCheck(new Date('2026-10-13T10:20:02.500Z')), 59500);
  assert.equal(delayUntilNextCheck(new Date('2026-10-13T10:20:59Z')), 3000);
});
