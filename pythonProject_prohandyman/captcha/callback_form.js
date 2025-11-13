// callback_form.js

let currentCaptchaToken = null;
let currentCaptchaWindow = null;

function openSmartCaptchaPopup() {
    // Открываем попап, размеры можно настроить под задачу
    const w = 420;
    const h = 520;
    const left = window.screenX + (window.innerWidth - w) / 2;
    const top = window.screenY + (window.innerHeight - h) / 2;

    currentCaptchaWindow = window.open(
        "/smartcaptcha-popup.html", // путь до файла из предыдущего блока
        "smartcaptcha_popup",
        `width=${w},height=${h},left=${left},top=${top},resizable=no,scrollbars=no`
    );

    if (!currentCaptchaWindow) {
        console.error("Не удалось открыть окно с капчей (popup заблокирован).");
    }
}

// Слушаем сообщения от попапа
window.addEventListener("message", (event) => {
    // При необходимости сузить origin, здесь можно явно указать:
    // if (event.origin !== "https://ваш-домен") return;

    const data = event.data || {};
    if (data.type === "smartcaptcha-token" && data.token) {
        currentCaptchaToken = data.token;
        console.log("Получен SmartCaptcha токен:", currentCaptchaToken);

        // Здесь можно:
        // 1) обновить UI (убрать лоадер / текст "идёт проверка")
        // 2) автоматически отправить форму на backend

        if (currentCaptchaWindow && !currentCaptchaWindow.closed) {
            try {
                currentCaptchaWindow.close();
            } catch (e) {
                // игнорируем
            }
        }
    }
});

// Пример отправки заявки на backend с токеном
async function sendCallbackRequest(payload) {
    if (!currentCaptchaToken) {
        console.warn("Нет токена SmartCaptcha, сначала нужно пройти проверку.");
        return;
    }

    const correlationId = crypto.randomUUID
        ? crypto.randomUUID()
        : String(Date.now());

    const resp = await fetch("https://d5dii40lrt3h821egn3i.fary004x.apigw.yandexcloud.net/callback/request", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-Correlation-Id": correlationId,
            "SmartCaptcha-Token": currentCaptchaToken,
        },
        body: JSON.stringify(payload),
    });

    const text = await resp.text();
    let data;
    try {
        data = JSON.parse(text);
    } catch {
        data = text;
    }

    console.log("Ответ callback-request:", resp.status, data);
}

// Пример/обработчик кнопки
document.getElementById("callback-submit").addEventListener("click", () => {
    const payload = {
        phone_number: document.getElementById("phone").value || undefined,
        email: document.getElementById("email").value || undefined,
        user_name: document.getElementById("name").value || undefined,
        comment: document.getElementById("comment").value || undefined,
    };

    // Сначала открываем невидимую капчу, которая при необходимости покажет челлендж,
    // а после успешного прохождения пришлёт токен и закроется.
    openSmartCaptchaPopup();

    // А сам вызов sendCallbackRequest(payload) можно триггерить
    // либо по получению токена (в обработчике message),
    // либо здесь после того, как currentCaptchaToken будет установлен.
});
