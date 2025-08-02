## 🔐 Аутентифікація користувачів

### 📥 Реєстрація

**Запит**
```http
POST /api/users/register/
Content-Type: application/json
```

**Тіло запиту**
```json
{
  "email": "petro@example.com",
  "password": "secret123",
  "first_name": "Петро",
  "last_name": "Петренко"
}
```

**Відповідь (201 Created)**
```json
{
  "message": "Будь ласка, підтвердіть вашу електронну пошту"
}
```

> Після реєстрації користувач отримує лист із посиланням для активації. Поки акаунт не активовано, JWT‑токени не видаються.

---

### 🔗 Активація акаунта

**Запит**
```http
GET /api/users/activate/{uidb64}/{token}/
```

**Відповідь (200 OK)**
```json
{
  "message": "Акаунт активовано"
}
```

**Якщо лінк недійсний (400 Bad Request)**
```json
{
  "message": "Невірне посилання для активації"
}
```

---

### 🔑 Вхід (Login)

**Запит**
```http
POST /api/users/token/
Content-Type: application/json
```

**Тіло запиту**
```json
{
  "email": "petro@example.com",
  "password": "secret123"
}
```

**Відповідь (200 OK)**
```json
{
  "access": "<новий_access_token>",
  "refresh": "<новий_refresh_token>"
}
```

**При невірних облікових даних (401 Unauthorized)**
```json
{
  "detail": "No active account found with the given credentials"
}
```

---

### 🔒 Доступ до захищених ендпоінтів

Додати заголовок до кожного запиту:
```http
Authorization: Bearer <access_token>
```

---

### ♻️ Оновлення access‑токена

Коли `access` закінчився (через 15 хвилин), обміняти `refresh` на новий `access`:

**Запит**
```http
POST /api/users/token/refresh/
Content-Type: application/json
```

**Тіло**
```json
{
  "refresh": "<refresh_token>"
}
```

**Відповідь (200 OK)**
```json
{
  "access": "<новий_access_token>"
}
```

**При невалідному чи простроченому `refresh` (400 Bad Request)**
```json
{
  "detail": "Token is invalid or expired"
}
```

---

### 🚪 Вихід (Logout)

**Запит**
```http
POST /api/users/logout/
Content-Type: application/json
Authorization: Bearer <access_token>
```

**Тіло**
```json
{
  "refresh": "<refresh_token>"
}
```

**Відповідь (205 Reset Content)**

> `refresh_token` потрапляє до чорного списку та більше не може бути використаний. На фронтенді потрібно видалити обидва токени та перенаправити користувача на сторінку входу.

---

### ✅ Як скористатися захищеним ендпоінтом

1. **Отримати токени** через `/api/users/token/`  
2. **Додати заголовок** `Authorization: Bearer <access_token>` до кожного захищеного запиту  

**Приклад через curl:**
```bash
curl -H "Authorization: Bearer <access_token>" http://127.0.0.1:8000/api/products/
```

---

### ⚠️ Swagger UI

1. Перейдіть на `/api/swagger/`  
2. Натисніть **Authorize**  
3. Введіть: `Bearer <access_token>`  
4. Натисніть **Authorize**, потім **Close**  
5. Тепер усі запити виконуватимуться з токеном  

---

### 📘 Примітка

- Використовується **JWT (JSON Web Token)**.  
- `access` має термін дії 15 хвилин.  
- `refresh` дозволяє оновлювати `access` без повторного логіна.  
