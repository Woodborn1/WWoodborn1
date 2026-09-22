# 🎬 Vamous Stream Clips API

Готовий REST API сервіс для отримання нарізок та кліпів сайту **Vamous** (Twitch / Kick / YouTube), оптимізований для простого деплою на **Render** та інтеграції з пайплайном Obsidian.

---

## 📋 Структура даних кліпу (Response Schema)

Кожен об'єкт кліпу повертає такі поля:
* `id` (*string*): Унікальний ідентифікатор кліпу.
* `url` (*string*): Посилання на кліп (Twitch, Kick, YouTube).
* `streamer` (*string*): Нікнейм стрімера (наприклад, `Leb1ga`, `Kavalets`, `Ghostik`).
* `title` (*string*): Назва кліпу.
* `views` (*integer*): Кількість переглядів.
* `category` (*string*): Категорія або назва гри (наприклад, `Just Chatting`, `Dota 2`, `IRL`).
* `created_at` (*string*): ISO 8601 дата створення кліпу.
* `chat_activity` (*integer*, опціонально): Кількість повідомлень у чаті за час кліпу.

---

## 🚀 Основні ендпоінти API

### 1. Отримати список кліпів
```http
GET /api/clips?limit=50&offset=0&min_views=50&streamer=Leb1ga&category=Just%20Chatting
```
**Приклад відповіді (200 OK):**
```json
{
  "total": 4,
  "clips": [
    {
      "id": "clip_9842",
      "url": "https://clips.twitch.tv/SparklingPleasantDootCoolCat",
      "streamer": "Leb1ga",
      "title": "Лебіга про Альпи та лижі",
      "views": 1250,
      "category": "Just Chatting",
      "created_at": "2026-09-22T07:45:00Z",
      "chat_activity": 85
    }
  ]
}
```

### 2. Отримати чергу для обробки (Pipeline Queue)
```http
GET /api/clips/queue?limit=50&min_views=50
```

### 3. Додати новий кліп (Webhook / Manual)
```http
POST /api/clips
Content-Type: application/json

{
  "id": "clip_new_101",
  "url": "https://clips.twitch.tv/ExampleSlug",
  "streamer": "Leb1ga",
  "title": "Смішний момент на стрімі",
  "views": 450,
  "category": "Just Chatting",
  "chat_activity": 60
}
```

### 4. Оновити статус обробки
```http
PATCH /api/clips/clip_9842/status
Content-Type: application/json

{
  "status": "processed"
}
```

### 5. Оновити базу кліпів (Twitch Sync)
```http
POST /api/refresh-database
```

---

## 🛠️ Локальний запуск

```bash
# 1. Створити та активувати віртуальне середовище
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 2. Встановити залежності
pip install -r requirements.txt

# 3. Запустити сервер
uvicorn main:app --reload --port 8000
```
Інтерактивна документація Swagger UI доступна за адресою: `http://localhost:8000/docs`.

---

## ☁️ Деплой на Render за 2 хвилини

### Варіант А: Автоматичний (Blueprint через `render.yaml`)
1. Створіть новий репозиторій на GitHub (наприклад, `vamous-api`) та запуште цей код:
   ```bash
   git init
   git add .
   git commit -m "Initial commit for Vamous Clips API"
   git branch -M main
   git remote add origin https://github.com/Woodborn1/vamous-api.git
   git push -u origin main
   ```
2. Відкрийте [Render Dashboard](https://dashboard.render.com/).
3. Натисніть **Blueprints** ➔ **New Blueprint Instance**.
4. Виберіть репозиторій `vamous-api`.
5. Render автоматично прочитає `render.yaml`, встановить залежності та запустить сервіс!

### Варіант Б: Вручну як Web Service
1. На Render виберіть **New +** ➔ **Web Service**.
2. Виберіть ваш репозиторій GitHub `vamous-api`.
3. Заповніть налаштування:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Натисніть **Create Web Service**.
