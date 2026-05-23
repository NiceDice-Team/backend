## 🔐 User Authentication

### 📥 Registration

**Request**
```http
POST /api/users/register/
Content-Type: application/json
```

**Request Body**
```json
{
  "email": "petro@example.com",
  "password": "secret123",
  "first_name": "Peter",
  "last_name": "Petrenko"
}
```

**Response (201 Created)**
```json
{
  "message": "Please confirm your email address"
}
```

> After registration, the user receives an email with an activation link. JWT tokens are not issued until the account is activated.

---

### 🔗 Account Activation

**Request**
```http
GET /api/users/activate/{uidb64}/{token}/
```

**Response (200 OK)**
```json
{
  "message": "Account successfully activated"
}
```

**If the link is invalid (400 Bad Request)**
```json
{
  "message": "Invalid activation link"
}
```

---

### 🔑 Login

**Request**
```http
POST /api/users/token/
Content-Type: application/json
```

**Request Body**
```json
{
  "email": "petro@example.com",
  "password": "secret123"
}
```

**Response (200 OK)**
```json
{
  "access": "<new_access_token>",
  "refresh": "<new_refresh_token>"
}
```

**For invalid credentials (401 Unauthorized)**
```json
{
  "detail": "No active account found with the given credentials"
}
```

---

### 🔒 Accessing Protected Endpoints

Add this header to each request:
```http
Authorization: Bearer <access_token>
```

---

### ♻️ Refreshing the Access Token

When the `access` token expires (after 15 minutes), exchange the `refresh` token for a new `access` token:

**Request**
```http
POST /api/users/token/refresh/
Content-Type: application/json
```

**Body**
```json
{
  "refresh": "<refresh_token>"
}
```

**Response (200 OK)**
```json
{
  "access": "<new_access_token>"
}
```

**If `refresh` is invalid or expired (400 Bad Request)**
```json
{
  "detail": "Token is invalid or expired"
}
```

---

### 🚪 Logout

**Request**
```http
POST /api/users/logout/
Content-Type: application/json
Authorization: Bearer <access_token>
```

**Body**
```json
{
  "refresh": "<refresh_token>"
}
```

**Response (205 Reset Content)**

> The `refresh_token` is blacklisted and can no longer be used. On the frontend, remove both tokens and redirect the user to the login page.

---

### ✅ How to Use a Protected Endpoint

1. **Get tokens** via `/api/users/token/`  
2. **Add the header** `Authorization: Bearer <access_token>` to each protected request  

**Example using curl:**
```bash
curl -H "Authorization: Bearer <access_token>" http://127.0.0.1:8000/api/products/
```

---

### ⚠️ Swagger UI

1. Open `/api/swagger/`  
2. Click **Authorize**  
3. Enter: `Bearer <access_token>`  
4. Click **Authorize**, then **Close**  
5. All requests will now be sent with the token  

---

### 📘 Note

- **JWT (JSON Web Token)** is used.  
- `access` is valid for 15 minutes.  
- `refresh` lets you renew `access` without logging in again.  
