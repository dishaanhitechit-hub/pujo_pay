# PujoPay — Backend API Reference

## Base URL
```
http://<server-ip>:5999
```

## Authentication
All `/api/*` routes (except `/api/auth/login`) require a JWT token in the header:
```
Authorization: Bearer <access_token>
```

## Response Format
Every API response always follows this structure:
```json
{
  "message": "human readable message",
  "data": {}
}
```
`data` is `[]` (empty array) when there is nothing to return.

---

## Roles & Permissions

| Role | What they can do |
|---|---|
| `admin` | Everything |
| `executive` | Initiate payments, view all collector summaries, dashboard |
| `committee` | Initiate payments, view own collections only |
| `general` | Initiate payments only |

---

## ⚙️ Which Modules Are Backend-Rendered (No Frontend Needed)

These pages are **fully served by the backend as HTML**. Frontend only needs to redirect the browser to these URLs — the backend handles everything including forms, confirm logic, and the final receipt.

| URL | Triggered by | What it does |
|---|---|---|
| `GET /pay/qr/<payment_id>` | Frontend redirects after `POST /api/payment/initiate` (UPI) | Shows QR code + 10-min timer + UTR field |
| `POST /pay/qr/<payment_id>/confirm` | QR page form submit (auto) | Confirms UPI payment, redirects to receipt |
| `GET /pay/cash/<payment_id>` | Frontend redirects after `POST /api/payment/initiate` (cash) | Shows cash confirm page |
| `POST /pay/cash/<payment_id>/confirm` | Cash page form submit (auto) | Confirms cash payment, redirects to receipt |
| `GET /pay/receipt/<payment_id>` | Backend redirect after confirm (auto) | Shows HTML receipt page |
| `GET /receipt/<receipt_no>` | Frontend link / WhatsApp share link | Streams PDF receipt from disk |

---

## Frontend Must Build Forms/Screens For

| Screen | API call needed |
|---|---|
| Login screen | `POST /api/auth/login` |
| Create / manage collectors (admin) | `POST /api/users/`, `PATCH /api/users/<id>`, `DELETE /api/users/<id>` |
| Set UPI ID + org name (admin, once) | `POST /api/admin/config` |
| Payment initiate form (collector) | `POST /api/payment/initiate` → read `nextUrl` → redirect browser |
| Own collection summary (collector) | `GET /api/collector/summary` |
| Own payment list (collector) | `GET /api/collector/payments` |
| Admin dashboard | `GET /api/dashboard/summary`, `/collectors`, `/payments` |

---

## API Endpoints

---

### 1. Auth — `/api/auth`

---

#### `POST /api/auth/login`
Login and get access token. No auth header needed.

**Request Body:**
```json
{
  "email": "admin@pujopay.local",
  "password": "PujoAdmin@2026"
}
```

**Response `200`:**
```json
{
  "message": "login successful",
  "data": {
    "accessToken": "eyJhbGci...",
    "user": {
      "id": 1,
      "name": "Admin",
      "email": "admin@pujopay.local",
      "phone": null,
      "upiId": null,
      "whatsappNo": null,
      "role": "admin",
      "isActive": true,
      "createdAt": "2024-10-12T10:00:00"
    }
  }
}
```

**Response `401`:**
```json
{ "message": "invalid credentials", "data": [] }
```

---

#### `POST /api/auth/logout`
Invalidate the current token. Requires auth header.

**Request Body:** none

**Response `200`:**
```json
{ "message": "logged out", "data": [] }
```

---

#### `GET /api/auth/me`
Get current logged-in user details.

**Response `200`:**
```json
{
  "message": "",
  "data": {
    "id": 2,
    "name": "Ramesh Das",
    "email": "ramesh@pujopay.local",
    "phone": "9800000001",
    "upiId": null,
    "whatsappNo": "9800000001",
    "role": "committee",
    "isActive": true,
    "createdAt": "2024-10-12T10:05:00"
  }
}
```

---

### 2. Users — `/api/users`
> Requires role: `admin`

---

#### `GET /api/users/`
List all users.

**Response `200`:**
```json
{
  "message": "",
  "data": [
    {
      "id": 1,
      "name": "Admin",
      "email": "admin@pujopay.local",
      "phone": null,
      "upiId": null,
      "whatsappNo": null,
      "role": "admin",
      "isActive": true,
      "createdAt": "2024-10-12T10:00:00"
    }
  ]
}
```

---

#### `POST /api/users/`
Create a new user (collector/member).

**Request Body:**
```json
{
  "name": "Ramesh Das",
  "email": "ramesh@pujopay.local",
  "password": "Secret@123",
  "phone": "9800000001",
  "upiId": null,
  "whatsappNo": "9800000001",
  "role": "committee"
}
```
> `role` must be one of: `admin`, `executive`, `committee`, `general`
> `name`, `email`, `password` are required. All others optional.

**Response `201`:**
```json
{
  "message": "user created",
  "data": { ...user object... }
}
```

**Response `409`:**
```json
{ "message": "email already registered", "data": [] }
```

---

#### `GET /api/users/<id>`
Get a single user by ID.

**Response `200`:**
```json
{ "message": "", "data": { ...user object... } }
```

---

#### `PATCH /api/users/<id>`
Update a user. Only send fields you want to change.

**Request Body (all optional):**
```json
{
  "name": "Ramesh Kumar",
  "phone": "9800000002",
  "upiId": null,
  "whatsappNo": "9800000002",
  "role": "executive",
  "password": "NewPass@123",
  "isActive": true
}
```

**Response `200`:**
```json
{ "message": "user updated", "data": { ...user object... } }
```

---

#### `DELETE /api/users/<id>`
Soft-deactivate a user (`isActive` → `false`). Cannot deactivate yourself.

**Response `200`:**
```json
{ "message": "user 'Ramesh Das' deactivated", "data": [] }
```

---

### 3. Admin Config — `/api/admin`
> Requires role: `admin`

Used once to set the global UPI ID before any payments start.

---

#### `GET /api/admin/config`
Get current app configuration.

**Response `200`:**
```json
{
  "message": "",
  "data": {
    "config": {
      "upi_id": "committee@upi",
      "org_name": "Durga Puja 2024"
    },
    "allowedKeys": {
      "upi_id": "UPI ID (e.g. committee@upi)",
      "org_name": "Organisation name shown on QR and receipts"
    }
  }
}
```

---

#### `POST /api/admin/config`
Set one or more config values.

**Request Body:**
```json
{
  "upi_id": "committee@upi",
  "org_name": "Durga Puja 2024"
}
```

**Response `200`:**
```json
{
  "message": "config updated",
  "data": {
    "upi_id": "committee@upi",
    "org_name": "Durga Puja 2024"
  }
}
```

---

### 4. Payment — `/api/payment`
> Requires permission: `payment.initiate`

---

#### `POST /api/payment/initiate`
Start a new payment. Creates donor record + payment record.
Frontend reads `nextUrl` from response and **redirects the browser** to it.

**Request Body:**
```json
{
  "donor_name": "Suresh Mondal",
  "donor_phone": "9700000001",
  "donor_address": "12 Lake Road, Kolkata",
  "donor_notes": "Annual member",
  "amount": "500.00",
  "method": "upi"
}
```
> `donor_name`, `amount`, `method` are required.
> `method` must be `"upi"` or `"cash"`.
> `donor_phone`, `donor_address`, `donor_notes` are optional.

**Response `201`:**
```json
{
  "message": "payment initiated",
  "data": {
    "paymentId": 42,
    "method": "upi",
    "amount": "500.00",
    "donorName": "Suresh Mondal",
    "status": "pending",
    "nextUrl": "/pay/qr/42"
  }
}
```
> For cash: `nextUrl` will be `/pay/cash/42`
> **Frontend must redirect browser to `nextUrl` immediately after this response.**

---

#### `GET /api/payment/receipt/<id>`
Get payment receipt as JSON (for confirmed payments only).

**Response `200`:**
```json
{
  "message": "",
  "data": {
    "id": 42,
    "receiptNo": "RCP-A1B2C3D4",
    "donor": {
      "id": 10,
      "name": "Suresh Mondal",
      "phone": "9700000001",
      "address": "12 Lake Road, Kolkata",
      "notes": "Annual member",
      "createdAt": "2024-10-12T14:30:00"
    },
    "collector": { "id": 3, "name": "Ramesh Das" },
    "amount": "500.00",
    "method": "upi",
    "utrNumber": "426112345678",
    "status": "confirmed",
    "whatsappSent": false,
    "confirmedAt": "2024-10-12T14:35:00",
    "receiptPdfPath": "/srv/pujo/recipet/storages/pdf/Ramesh_Das/upi/RCP-A1B2C3D4_20241012_143500.pdf",
    "createdAt": "2024-10-12T14:30:00"
  }
}
```

---

### 5. Backend-Rendered Pages — `/pay/`

These are **not JSON APIs** — they return full HTML pages. Frontend only redirects to them.

---

#### `GET /pay/qr/<payment_id>`
Renders the UPI payment page.

**Auto-triggered by:** Frontend redirect to `nextUrl` from `/api/payment/initiate` (when method is `upi`)

**What the page shows:**
- Donor name + amount
- QR code (UPI deep link with amount pre-filled — donor scans, amount auto-fills in their app)
- 10-minute countdown timer
- Optional UTR / Transaction Number input field
- "Payment Done" submit button (disabled when timer expires)

**No frontend work needed for this page.**

---

#### `POST /pay/qr/<payment_id>/confirm`
Submitted by the QR page form automatically. Not called by frontend directly.

**Form fields:**
- `utr_number` (optional text)

**On success:** Redirects to `/pay/receipt/<payment_id>`
**On failure (expired/already processed):** Re-renders QR page with error message

---

#### `GET /pay/cash/<payment_id>`
Renders the cash payment confirm page.

**Auto-triggered by:** Frontend redirect to `nextUrl` from `/api/payment/initiate` (when method is `cash`)

**What the page shows:**
- Donor name + amount + collector name
- "Confirm Cash Received" button

**No frontend work needed for this page.**

---

#### `POST /pay/cash/<payment_id>/confirm`
Submitted by the cash page form automatically. Not called by frontend directly.

**On success:** Redirects to `/pay/receipt/<payment_id>`

---

#### `GET /pay/receipt/<payment_id>`
Renders the HTML receipt page after confirmation.

**Auto-triggered by:** Backend redirect after confirm. No frontend work needed.

**What the page shows:**
- Receipt number, donor name, amount, method, UTR (if UPI), collector name, date/time

---

### 6. PDF Receipt — `/receipt/`
Public URL — no login required.

---

#### `GET /receipt/<receipt_no>`
Serve the PDF receipt file directly in browser.

**Example:** `GET /receipt/RCP-A1B2C3D4`

**Response:** PDF file streamed inline in browser.

**`404`** if receipt number is invalid or PDF was not generated.

> This URL can be shared via WhatsApp or printed on a physical receipt.

---

### 7. Collector — `/api/collector`
> Requires permission: `collector.view_own`
> Each collector sees **only their own** data.

---

#### `GET /api/collector/summary`
Get own collection totals.

**Response `200`:**
```json
{
  "message": "",
  "data": {
    "cashTotal": "5000.00",
    "upiTotal": "12500.00",
    "grandTotal": "17500.00",
    "confirmedCount": 23
  }
}
```

---

#### `GET /api/collector/payments`
Get own payment list (paginated).

**Query Params:**
| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `perPage` | int | 20 | Items per page (max 100) |
| `method` | string | — | Filter: `cash` or `upi` |
| `date` | string | — | Filter by date: `YYYY-MM-DD` |

**Response `200`:**
```json
{
  "message": "",
  "data": {
    "payments": [ { ...payment object... } ],
    "page": 1,
    "perPage": 20,
    "total": 23,
    "pages": 2
  }
}
```

---

### 8. Dashboard — `/api/dashboard`
> Requires permission: `dashboard.view` (roles: `admin`, `executive`)

---

#### `GET /api/dashboard/summary`
Grand totals across all collectors.

**Response `200`:**
```json
{
  "message": "",
  "data": {
    "cashTotal": "15000.00",
    "upiTotal": "27500.00",
    "grandTotal": "42500.00",
    "confirmedCount": 230,
    "pendingCount": 5,
    "totalDonors": 228
  }
}
```

---

#### `GET /api/dashboard/collectors`
Per-collector breakdown for audit.

**Response `200`:**
```json
{
  "message": "",
  "data": [
    {
      "collector": { "id": 2, "name": "Ramesh Das", "role": "committee" },
      "cashTotal": "5000.00",
      "upiTotal": "12500.00",
      "grandTotal": "17500.00",
      "confirmedCount": 23
    },
    {
      "collector": { "id": 3, "name": "Priya Sen", "role": "executive" },
      "cashTotal": "10000.00",
      "upiTotal": "15000.00",
      "grandTotal": "25000.00",
      "confirmedCount": 47
    }
  ]
}
```

---

#### `GET /api/dashboard/payments`
All payments across all collectors (paginated + filterable).

**Query Params:**
| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `perPage` | int | 20 | Items per page (max 100) |
| `method` | string | — | Filter: `cash` or `upi` |
| `status` | string | — | Filter: `pending`, `confirmed`, `expired` |
| `collectorId` | int | — | Filter by collector ID |
| `date` | string | — | Filter by date: `YYYY-MM-DD` |

**Response `200`:**
```json
{
  "message": "",
  "data": {
    "payments": [ { ...payment object... } ],
    "page": 1,
    "perPage": 20,
    "total": 230,
    "pages": 12
  }
}
```

---

## Complete Payment Flow

```
COLLECTOR LOGIN
     │
     ▼
POST /api/auth/login  →  get accessToken
     │
     ▼
FILL PAYMENT FORM (frontend)
  - donor name (required)
  - phone, address, notes (optional)
  - amount (required)
  - method: cash or upi (required)
     │
     ▼
POST /api/payment/initiate  →  get nextUrl
     │
     ├── method = "upi" ──► redirect browser to /pay/qr/<id>
     │                            │
     │                      Backend serves QR page:
     │                       - QR with amount pre-filled
     │                       - 10-min countdown timer
     │                       - UTR input (optional)
     │                       - "Payment Done" button
     │                            │
     │                      Donor scans QR → pays in UPI app
     │                            │
     │                      Collector enters UTR (optional)
     │                      clicks "Payment Done"
     │                            │
     │                      POST /pay/qr/<id>/confirm (auto)
     │                            │
     └── method = "cash" ──► redirect browser to /pay/cash/<id>
                                  │
                            Backend serves cash confirm page
                                  │
                            Collector clicks "Confirm Cash Received"
                                  │
                            POST /pay/cash/<id>/confirm (auto)

          BOTH FLOWS MEET HERE
                    │
                    ▼
           Payment marked confirmed
           Receipt number generated (RCP-XXXXXXXX)
           PDF saved to disk automatically
                    │
                    ▼
          GET /pay/receipt/<id>  ←  HTML receipt shown
                    │
                    ▼
          GET /receipt/<receipt_no>  ←  PDF shareable link
```

---

## First-Time Server Setup (Admin Checklist)

```bash
# 1. Run migrations
flask db migrate -m "initial schema"
flask db upgrade

# 2. Start server
python run.py

# 3. Login as admin
POST /api/auth/login
{ "email": "admin@pujopay.local", "password": "PujoAdmin@2026" }

# 4. Set global UPI ID and org name (do this once)
POST /api/admin/config
{ "upi_id": "committee@upi", "org_name": "Durga Puja 2024" }

# 5. Create collector accounts
POST /api/users/
{ "name": "Ramesh Das", "email": "ramesh@pujopay.local",
  "password": "Pass@123", "role": "committee", "whatsappNo": "9800000001" }

# 6. Collectors can now log in and start collecting
```

---

## Error Codes

| Code | Meaning |
|---|---|
| `400` | Bad request / validation error |
| `401` | Invalid or missing credentials |
| `403` | Permission denied for your role |
| `404` | Resource not found |
| `409` | Conflict (e.g. duplicate email) |
| `422` | Validation failed (field-level errors in `data`) |
