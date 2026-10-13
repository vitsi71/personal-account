// Каждый опрос привязан к :02 календарной минуты; задержка запроса не накапливается.
export function delayUntilNextCheck(now = new Date()) {
  const delay = (2000 - (now.getTime() % 60000) + 60000) % 60000;
  return delay || 60000;
}

// Обновляем статусы без перезагрузки страницы и без потери заполненной формы.
const panel = typeof document === 'undefined' ? null : document.querySelector('[data-notifications-url]');
if (panel) {
  const notice = document.querySelector('#live-notification');
  const noticeText = document.querySelector('#live-notification-text');
  const connection = document.querySelector('#notification-connection');
  let active = true;
  async function refreshNotifications() {
    try {
      const response = await fetch(panel.dataset.notificationsUrl, {cache: 'no-store'});
      if (response.redirected) {
        active = false;
        connection.textContent = 'Сессия завершена. Войдите снова для получения уведомлений.';
        return;
      }
      if (!response.ok) throw new Error('Ошибка проверки уведомлений');
      const data = await response.json();
      const delivered = new Set(data.delivered_ids.map(String));
      const messages = [];
      for (const item of panel.querySelectorAll('[data-pending]')) {
        if (!delivered.has(item.dataset.reminderId)) continue;
        item.querySelector('.status').textContent = 'Уведомление доставлено';
        item.removeAttribute('data-pending');
        messages.push(item.querySelector('p').textContent);
      }
      if (messages.length) {
        // textContent безопасно выводит пользовательские сообщения без HTML.
        const text = messages.join('\n');
        // Если окно уже открыто, добавляем новые сообщения, не теряя предыдущие.
        noticeText.textContent = notice.open ? `${noticeText.textContent}\n${text}` : text;
        if (!notice.open) notice.showModal();
      }
      connection.textContent = '';
    } catch {
      connection.textContent = 'Связь с сервером потеряна. Проверка уведомлений будет повторена.';
    } finally {
      // Следующая проверка — на второй секунде минуты, после задачи планировщика.
      if (active) setTimeout(refreshNotifications, delayUntilNextCheck());
    }
  }
  // Первый запрос тоже выполняем в :02, а не в произвольный момент открытия.
  setTimeout(refreshNotifications, delayUntilNextCheck());
}
