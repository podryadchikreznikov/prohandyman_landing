(function () {
  'use strict';

  // ------------------------------
  // ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ОВЕРЛЕЯ
  // ------------------------------

  /**
   * Создаёт overlay и контейнер для SmartCaptcha, если их ещё нет.
   * Overlay по умолчанию скрыт (display: none; задаётся в CSS).
   */
  function ensureOverlay() {
    var overlay = document.getElementById('smartcaptcha-overlay');
    if (overlay) {
      // На всякий случай убеждаемся, что внутри есть контейнер
      var container = document.getElementById('smartcaptcha-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'smartcaptcha-container';
        overlay.appendChild(container);
      }
      return overlay;
    }

    overlay = document.createElement('div');
    overlay.id = 'smartcaptcha-overlay';

    var container = document.createElement('div');
    container.id = 'smartcaptcha-container';
    overlay.appendChild(container);

    document.body.appendChild(overlay);
    return overlay;
  }

  function getOverlay() {
    return document.getElementById('smartcaptcha-overlay') || ensureOverlay();
  }

  function showOverlayNow() {
    var overlay = getOverlay();
    overlay.style.display = 'flex';
  }

  function hideOverlayNow() {
    var overlay = getOverlay();
    overlay.style.display = 'none';
  }

  /**
   * Таймер для предотвращения "мигания" оверлея:
   * если challenge открылся и сразу закрылся, мы не успеваем показать оверлей.
   */
  var overlayTimerId = null;
  var OVERLAY_SHOW_DELAY_MS = 150; // можно подправить, если нужно

  function scheduleOverlayShow() {
    // Если уже запланировано — повторно не планируем
    if (overlayTimerId !== null) {
      return;
    }
    overlayTimerId = window.setTimeout(function () {
      overlayTimerId = null;
      showOverlayNow();
    }, OVERLAY_SHOW_DELAY_MS);
  }

  function cancelOverlayAndHide() {
    if (overlayTimerId !== null) {
      window.clearTimeout(overlayTimerId);
      overlayTimerId = null;
    }
    hideOverlayNow();
  }

  // ------------------------------
  // ИНИЦИАЛИЗАЦИЯ SMARTCAPTCHA
  // ------------------------------

  // Глобальный ID инстанса виджета
  window.smartCaptchaInstanceId = null;

  /**
   * Инициализация SmartCaptcha в невидимом режиме.
   * Вызывается из Flutter/Dart один раз при старте.
   *
   * @param {string} sitekey - client key из Yandex Cloud.
   */
  window.initSmartCaptcha = function (sitekey) {
    if (!window.smartCaptcha) {
      console.warn('Yandex SmartCaptcha script not loaded yet');
      return;
    }

    if (!sitekey) {
      console.warn('SmartCaptcha sitekey is empty');
      return;
    }

    if (window.smartCaptchaInstanceId !== null) {
      // Уже инициализировано — повторная инициализация не нужна
      return;
    }

    // Обеспечиваем наличие overlay + контейнера, но они остаются скрыты
    ensureOverlay();

    var widgetId = window.smartCaptcha.render('smartcaptcha-container', {
      sitekey: sitekey,
      invisible: true,       // невидимый режим
      hideShield: true,      // <<< ГЛАВНАЯ ПРАВКА: скрываем плавающий shield с политикой

      // Успешное прохождение капчи: прислать токен во Flutter и убрать оверлей
      callback: function (token) {
        cancelOverlayAndHide();

        try {
          window.postMessage(
            JSON.stringify({
              channel: 'SMARTCAPTCHA_BRIDGE',
              type: 'SMARTCAPTCHA_TOKEN',
              token: token,
            }),
            '*'
          );
        } catch (e) {
          console.warn('Failed to post SMARTCAPTCHA_TOKEN', e);
        }
      },

      // Токен протух / просрочен
      'expired-callback': function () {
        cancelOverlayAndHide();

        try {
          window.postMessage(
            JSON.stringify({
              channel: 'SMARTCAPTCHA_BRIDGE',
              type: 'SMARTCAPTCHA_EXPIRED',
            }),
            '*'
          );
        } catch (e) {
          console.warn('Failed to post SMARTCAPTCHA_EXPIRED', e);
        }
      },

      // Ошибка в процессе проверки
      'error-callback': function () {
        cancelOverlayAndHide();

        try {
          window.postMessage(
            JSON.stringify({
              channel: 'SMARTCAPTCHA_BRIDGE',
              type: 'SMARTCAPTCHA_ERROR',
            }),
            '*'
          );
        } catch (e) {
          console.warn('Failed to post SMARTCAPTCHA_ERROR', e);
        }
      },
    });

    window.smartCaptchaInstanceId = widgetId;

    // Подписываемся на события.
    // challenge-visible / challenge-hidden используются для управления оверлеем.
    if (typeof window.smartCaptcha.subscribe === 'function') {
      try {
        // Окно задания (challenge) стало видимым.
        // НЕ показываем оверлей мгновенно, а с задержкой:
        // если SmartCaptcha быстро решит, что челлендж не нужен,
        // challenge-hidden придёт раньше, чем сработает таймер.
        window.smartCaptcha.subscribe(
          widgetId,
          'challenge-visible',
          function () {
            scheduleOverlayShow();
          }
        );

        // Окно задания (challenge) скрыто — отменяем таймер и прячем оверлей.
        window.smartCaptcha.subscribe(
          widgetId,
          'challenge-hidden',
          function () {
            cancelOverlayAndHide();
          }
        );

        // Дополнительно реагируем на сетевые и JS-ошибки, чтобы не зависал оверлей.
        window.smartCaptcha.subscribe(
          widgetId,
          'network-error',
          function () {
            cancelOverlayAndHide();
          }
        );

        window.smartCaptcha.subscribe(
          widgetId,
          'javascript-error',
          function () {
            cancelOverlayAndHide();
          }
        );

        window.smartCaptcha.subscribe(
          widgetId,
          'token-expired',
          function () {
            cancelOverlayAndHide();
          }
        );
      } catch (e) {
        console.warn('SmartCaptcha subscribe failed', e);
      }
    }
  };

  /**
   * Запуск невидимой проверки для текущего пользователя.
   *
   * ВАЖНО:
   * - здесь НЕТ прямого включения оверлея;
   * - оверлей включится только если SmartCaptcha реально решит
   *   показать окно задания и сработает событие challenge-visible
   *   с учётом задержки OVERLAY_SHOW_DELAY_MS.
   */
  window.showSmartCaptcha = function () {
    if (!window.smartCaptcha || window.smartCaptchaInstanceId === null) {
      console.warn('SmartCaptcha not initialized');
      return;
    }

    try {
      window.smartCaptcha.execute(window.smartCaptchaInstanceId);
    } catch (e) {
      console.warn('SmartCaptcha execute failed', e);
    }
  };

  /**
   * Сброс текущего инстанса капчи.
   * Можно вызвать, если вы хотите явно сбросить состояние между формами.
   */
  window.resetSmartCaptcha = function () {
    if (!window.smartCaptcha || window.smartCaptchaInstanceId === null) {
      return;
    }

    try {
      window.smartCaptcha.reset(window.smartCaptchaInstanceId);
    } catch (e) {
      console.warn('SmartCaptcha reset failed', e);
    } finally {
      cancelOverlayAndHide();
    }
  };

  // ------------------------------
  // ПРОБОС ФРОНТОВЫХ JS-ОШИБОК ВО FLUTTER (НЕ ОБЯЗАТЕЛЬНО, НО ПОЛЕЗНО)
  // ------------------------------

  function postJsError(payload) {
    try {
      window.postMessage(
        JSON.stringify({
          channel: 'FRONTEND_ERROR_BRIDGE',
          type: 'FRONTEND_JS_ERROR',
          message: payload.message || 'Unknown JS error',
          source: payload.source || 'unknown',
          filename: payload.filename || null,
          lineno: payload.lineno || null,
          colno: payload.colno || null,
        }),
        '*'
      );
    } catch (e) {
      // Не допускаем рекурсивных сбоев в репортере: просто глушим ошибку.
    }
  }

  window.addEventListener(
    'error',
    function (event) {
      if (!event) return;
      postJsError({
        message: event.message,
        source: 'window.error',
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      });
    },
    true
  );

  window.addEventListener(
    'unhandledrejection',
    function (event) {
      if (!event) return;
      var reason = event.reason;
      var message =
        typeof reason === 'string'
          ? reason
          : (reason && reason.message) || 'Unhandled promise rejection';
      postJsError({
        message: message,
        source: 'unhandledrejection',
      });
    },
    true
  );
})();
