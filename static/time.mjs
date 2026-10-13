// Преобразуем выбранное в календаре местное время в UTC для отправки серверу.
export function toUtc(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) throw new RangeError('Выберите дату и время в календаре.');
  const [year, month, day, hour, minute] = match.slice(1).map(Number);
  const date = new Date(value);
  // Сравнение частей исключает нормализацию несуществующей даты и пропуск часа
  // при переходе на летнее время. При повторении часа браузер выбирает первый.
  if (year < 1 || !Number.isFinite(date.getTime()) ||
      date.getFullYear() !== year || date.getMonth() + 1 !== month ||
      date.getDate() !== day || date.getHours() !== hour || date.getMinutes() !== minute) {
    throw new RangeError('Такое местное время не существует. Выберите другое.');
  }
  return date.toISOString();
}

// Часовой пояс не задаём: Intl использует настройки компьютера посетителя.
export function formatRussian(iso) {
  const parts = new Intl.DateTimeFormat('ru-RU', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(iso));
  const fields = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${fields.day}.${fields.month}.${fields.year} ${fields.hour}:${fields.minute}`;
}

// Модуль можно импортировать в тестах Node.js без браузерного документа.
if (typeof document !== 'undefined') {
  for (const element of document.querySelectorAll('time[data-local-time]')) {
    element.textContent = formatRussian(element.dateTime);
  }
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  for (const element of document.querySelectorAll('[data-timezone]')) {
    element.textContent = `Местное время компьютера (${zone})`;
  }

  const form = document.querySelector('#reminder-form');
  if (form) {
    const calendar = form.querySelector('#due-local');
    const utcField = form.querySelector('[name="due_at"]');
    const preview = form.querySelector('#date-preview');
    const update = () => {
      calendar.setCustomValidity('');
      utcField.value = '';
      if (!calendar.value) {
        preview.textContent = 'Выберите дату и время по часам вашего компьютера.';
        return;
      }
      try {
        utcField.value = toUtc(calendar.value);
        preview.textContent = `Выбрано: ${formatRussian(utcField.value)}`;
      } catch (error) {
        calendar.setCustomValidity(error.message);
        preview.textContent = error.message;
      }
    };
    calendar.addEventListener('input', update);
    form.addEventListener('submit', event => {
      // Конвертируем непосредственно перед отправкой, в том числе после автозаполнения.
      update();
      if (!form.reportValidity() || !utcField.value) event.preventDefault();
    });
    update();
  }
}
