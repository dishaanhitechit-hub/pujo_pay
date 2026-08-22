# PujoPay — Full API Reference

**Base URL:** `http://132.154.156.82:5999`

All JSON API endpoints follow a uniform envelope:

```json
{
  "success": true,
  "message": "human-readable message",
  "data": { ... }
}
```

`data` is `null` when there is nothing to return. On error `success` is `false` and `data` may contain validation details.

---

## Authentication

All protected endpoints require:

```
Authorization: Bearer <accessToken>
```

Token is obtained from `POST /api/auth/login`.

---

## Permission Matrix (Default)

| Permission key         | admin | executive | committee | general |
|------------------------|:-----:|:---------:|:---------:|:-------:|
| `payment.initiate`     | ✓     | ✓         | ✓         | ✓       |
| `payment.confirm`      | ✓     | ✓         | ✓         | ✓       |
| `payment.view_receipt` | ✓     | ✓         | ✓         | ✓       |
| `collector.view_own`   | ✓     | ✓         | ✓         |         |
| `dashboard.view`       | ✓     | ✓         |           |         |
| `users.manage`         | ✓     |           |           |         |
| `permissions.manage`   | ✓     |           |           |         |
| `token.generate`       | ✓     | ✓         | ✓         | ✓       |
| `token.bulk`           | ✓     |           |           |         |
| `token.view`           | ✓     | ✓         |           |         |

---

## Common Objects

### Donor Object
```json
{
  "id": 10,
  "name": "Subhash Roy",
  "phone": "9800000010",
  "address": "12 Park Street, Kolkata",
  "notes": "regular donor",
  "donorType": "individual",
  "createdAt": "2024-09-01T12:00:00"
}
```

### Payment Object
```json
{
  "id": 42,
  "receiptNo": "RCP-A1B2C3D4",
  "donor": { ...donor object... },
  "collector": { "id": 3, "name": "Ramesh Das" },
  "amount": "500.00",
  "method": "upi",
  "utrNumber": "UTR123456789",
  "chequeNumber": null,
  "bankName": null,
  "chequeDate": null,
  "pledgeId": null,
  "status": "confirmed",
  "whatsappSent": false,
  "confirmedAt": "2024-09-01T12:05:00",
  "cancelledAt": null,
  "receiptPdfPath": null,
  "createdAt": "2024-09-01T12:00:00"
}
```

`method`: `cash` | `upi` | `cheque`
`status`: `pending` | `confirmed` | `cancelled` | `expired`
`chequeNumber`, `bankName`, `chequeDate` — populated only for cheque payments, `null` otherwise.
`pledgeId` — populated only when payment is an installment against a pledge, `null` otherwise.

### Token Object
```json
{
  "id": 12,
  "tokenNo": "PP0001SS",
  "slNo": 1,
  "type": "single",
  "status": "active",
  "participantName": "Subhash Roy",
  "topic": "Durga Puja 2024",
  "orgName": "Durga Puja Committee",
  "generatedBy": { "id": 3, "name": "Ramesh Das" },
  "generatedAt": "2024-09-01T14:30:00",
  "batchId": null,
  "printUrl": "/token/print/PP0001SS",
  "viewUrl": "/token/PP0001SS"
}
```

`type`: `single` | `dual` | `bulk`
`status`: `active` | `void`

### Pledge Object
```json
{
  "id": 1,
  "donor": { ...donor object... },
  "collector": { "id": 3, "name": "Ramesh Das" },
  "totalAmount": "10000.00",
  "paidAmount": "5000.00",
  "outstandingAmount": "5000.00",
  "status": "open",
  "notes": "Paying in 2 installments",
  "createdAt": "2024-09-01T12:00:00"
}
```

`status`: `open` | `complete` | `cancelled`
`outstandingAmount = totalAmount − paidAmount` (computed, not stored).

---

## 1. Auth

### POST /api/auth/login
No auth required.

**Request**
```json
{
  "email": "admin@pujo.local",
  "password": "secret123"
}
```

**Response 200**
```json
{
  "success": true,
  "message": "login successful",
  "data": {
    "accessToken": "eyJ...",
    "user": {
      "id": 1,
      "name": "Admin User",
      "email": "admin@pujo.local",
      "phone": "9800000001",
      "upiId": null,
      "whatsappNo": null,
      "role": "admin",
      "isActive": true,
      "createdAt": "2024-09-01T10:00:00"
    }
  }
}
```

**Errors**

| Code | message |
|------|---------|
| 400  | `email and password are required` |
| 401  | `invalid credentials` |

---

### POST /api/auth/logout
Requires: JWT (any role). Invalidates the token immediately.

**Request** — no body.

**Response 200**
```json
{ "success": true, "message": "logged out", "data": null }
```

---

### GET /api/auth/me
Requires: JWT (any role).

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "id": 1,
    "name": "Admin User",
    "email": "admin@pujo.local",
    "phone": "9800000001",
    "upiId": null,
    "whatsappNo": null,
    "role": "admin",
    "isActive": true,
    "createdAt": "2024-09-01T10:00:00"
  }
}
```

---

## 2. Admin Config

### GET /api/admin/config
Requires: `users.manage`

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "config": {
      "upi_id": "committee@upi",
      "org_name": "Durga Puja 2024"
    },
    "allowedKeys": ["upiId", "orgName"]
  }
}
```

---

### POST /api/admin/config
Requires: `users.manage`

**Request** (any subset of allowed keys)
```json
{
  "upiId": "committee@upi",
  "orgName": "Durga Puja 2024"
}
```

**Response 200**
```json
{
  "success": true,
  "message": "config updated",
  "data": { "upiId": "committee@upi", "orgName": "Durga Puja 2024" }
}
```

**Error 400** (unknown key)
```json
{
  "success": false,
  "message": "some keys were rejected",
  "data": {
    "updated": { "orgName": "Durga Puja 2024" },
    "errors": { "badKey": "unknown key — allowed: ['upiId', 'orgName']" }
  }
}
```

---

## 3. Users

### GET /api/users/
Requires: `users.manage`

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": [
    {
      "id": 1,
      "name": "Admin User",
      "email": "admin@pujo.local",
      "phone": "9800000001",
      "upiId": null,
      "whatsappNo": null,
      "role": "admin",
      "isActive": true,
      "createdAt": "2024-09-01T10:00:00"
    }
  ]
}
```

---

### POST /api/users/
Requires: `users.manage`

**Request**
```json
{
  "name": "Ramesh Das",
  "email": "ramesh@pujo.local",
  "password": "pass1234",
  "phone": "9800000002",
  "whatsappNo": "9800000002",
  "role": "committee"
}
```

| Field        | Required | Notes |
|--------------|----------|-------|
| `name`       | Yes      | max 120 chars |
| `email`      | Yes      | must be unique |
| `password`   | Yes      | min 6 chars |
| `phone`      | No       | |
| `whatsappNo` | No       | |
| `role`       | No       | `admin` `executive` `committee` `general`; default `general` |

**Response 201**
```json
{
  "success": true,
  "message": "user created",
  "data": { ...user object... }
}
```

**Errors**

| Code | message |
|------|---------|
| 409  | `email already registered` |
| 422  | `validation failed` |

---

### GET /api/users/:id
Requires: `users.manage` — returns single user object. **Error 404** — `user not found`

---

### PATCH /api/users/:id
Requires: `users.manage`

**Request** (any subset)
```json
{
  "name": "Ramesh Kumar Das",
  "phone": "9800000099",
  "whatsappNo": "9800000099",
  "role": "executive",
  "isActive": true
}
```

**Response 200** — updated user object.

---

### DELETE /api/users/:id
Requires: `users.manage`. Soft-deactivates the user. Cannot deactivate your own account.

**Response 200**
```json
{ "success": true, "message": "user 'Ramesh Das' deactivated", "data": null }
```

**Errors**

| Code | message |
|------|---------|
| 400  | `cannot deactivate your own account` |
| 404  | `user not found` |

---

## 4. Payment

### POST /api/payment/initiate
Requires: `payment.initiate` (admin role is blocked)

**Request**
```json
{
  "donorName": "Subhash Roy",
  "donorPhone": "9800000010",
  "donorAddress": "12 Park Street",
  "donorNotes": "VIP donor",
  "donorType": "individual",
  "amount": "500.00",
  "method": "upi",
  "pledgeId": null
}
```

| Field         | Required | Notes |
|---------------|----------|-------|
| `donorName`   | Yes      | max 120 chars |
| `donorPhone`  | No       | max 20 chars |
| `donorAddress`| No       | |
| `donorNotes`  | No       | |
| `donorType`   | No       | free text, e.g. `individual`, `organisation` |
| `amount`      | Yes      | positive decimal |
| `method`      | Yes      | `upi` `cash` `cheque` |
| `pledgeId`    | No       | link payment to an existing open pledge; amount must not exceed outstanding |

**Response 201**
```json
{
  "success": true,
  "message": "payment initiated",
  "data": {
    "paymentId": 42,
    "method": "upi",
    "amount": "500.00",
    "donorName": "Subhash Roy",
    "status": "pending",
    "pledgeId": null,
    "nextUrl": "/pay/qr/42"
  }
}
```

`nextUrl` → `/pay/qr/<id>` (UPI) · `/pay/cash/<id>` (cash) · `/pay/cheque/<id>` (cheque). Open in browser to complete.

**Errors**

| Code | message |
|------|---------|
| 400  | `pledge not found` |
| 400  | `pledge is complete — cannot add payments` |
| 400  | `amount exceeds outstanding balance of ₹…` |
| 403  | `admin accounts cannot collect payments` |
| 422  | `validation failed` |

---

### GET /api/payment/receipt/:payment_id
Requires: `payment.view_receipt` — JSON receipt for a confirmed payment.

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "id": 42,
    "receiptNo": "RCP-A1B2C3D4",
    "donor": {
      "id": 10,
      "name": "Subhash Roy",
      "phone": "9800000010",
      "address": "12 Park Street",
      "notes": null,
      "donorType": "individual",
      "createdAt": "2024-09-01T12:00:00"
    },
    "collector": { "id": 3, "name": "Ramesh Das" },
    "amount": "500.00",
    "method": "upi",
    "utrNumber": "UTR123456789",
    "chequeNumber": null,
    "bankName": null,
    "chequeDate": null,
    "pledgeId": null,
    "status": "confirmed",
    "whatsappSent": false,
    "confirmedAt": "2024-09-01T12:05:00",
    "cancelledAt": null,
    "receiptPdfPath": null,
    "createdAt": "2024-09-01T12:00:00"
  }
}
```

**Errors**

| Code | message |
|------|---------|
| 400  | `payment not confirmed yet` |
| 404  | `payment not found` |

---

### GET /api/payment/by-receipt/:receipt_no
Requires: `payment.view_receipt` — same response shape, looked up by receipt number string.

---

## 5. Payment UI Pages (Browser)

These routes return HTML — open in browser, not API client.

| Method | Path | Description |
|--------|------|-------------|
| GET  | `/pay/qr/<id>` | UPI QR scan page |
| POST | `/pay/qr/<id>/confirm` | Submit UTR and confirm UPI payment |
| POST | `/pay/qr/<id>/cancel` | Cancel UPI payment |
| GET  | `/pay/cash/<id>` | Cash confirmation page |
| POST | `/pay/cash/<id>/confirm` | Confirm cash received |
| POST | `/pay/cash/<id>/cancel` | Cancel cash payment |
| GET  | `/pay/cheque/<id>` | Cheque details entry page |
| POST | `/pay/cheque/<id>/confirm` | Submit cheque details and confirm |
| POST | `/pay/cheque/<id>/cancel` | Cancel cheque payment |
| GET  | `/pay/receipt/<id>` | HTML receipt — 30 s auto-redirect + Download as PDF |
| GET  | `/receipt/<receipt_no>` | Same receipt page, lookup by receipt number |

**Cheque confirm form fields** (all optional):

| Field | Description |
|-------|-------------|
| `cheque_number` | Cheque number, max 50 chars |
| `bank_name` | Bank name, max 100 chars |
| `cheque_date` | Date of cheque (`YYYY-MM-DD`) |

---

## 6. Collector

### GET /api/collector/summary
Requires: `collector.view_own` — totals for the logged-in collector only.

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "cashTotal": "1200.00",
    "upiTotal": "3500.00",
    "grandTotal": "4700.00",
    "confirmedCount": 12,
    "pendingCount": 2
  }
}
```

---

### GET /api/collector/payments
Requires: `collector.view_own`

**Query params**

| Param | Type | Notes |
|-------|------|-------|
| `page` | int | default `1` |
| `perPage` | int | default `20`, max `100` |
| `method` | string | `cash` `upi` `cheque` |
| `date` | string | `YYYY-MM-DD` |

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "payments": [ { ...payment object... } ],
    "page": 1,
    "perPage": 20,
    "total": 45,
    "pages": 3
  }
}
```

---

## 7. Dashboard

### GET /api/dashboard/summary
Requires: `dashboard.view` — grand totals across all collectors, including pledge stats.

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "cashTotal": "25000.00",
    "upiTotal": "48000.00",
    "chequeTotal": "3000.00",
    "grandTotal": "76000.00",
    "confirmedCount": 180,
    "pendingCount": 5,
    "totalDonors": 170,
    "totalPledged": "50000.00",
    "totalPledgePaid": "30000.00",
    "totalPledgeOutstanding": "20000.00",
    "openPledgeCount": 5
  }
}
```

---

### GET /api/dashboard/collectors
Requires: `dashboard.view` — per-collector confirmed payment breakdown.

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": [
    {
      "collector": { "id": 3, "name": "Ramesh Das", "role": "committee" },
      "cashTotal": "5000.00",
      "upiTotal": "12000.00",
      "grandTotal": "17000.00",
      "confirmedCount": 42
    }
  ]
}
```

---

### GET /api/dashboard/payments
Requires: `dashboard.view` — all payments across all collectors, paginated.

**Query params**

| Param | Type | Notes |
|-------|------|-------|
| `page` | int | default `1` |
| `perPage` | int | default `20`, max `100` |
| `method` | string | `cash` `upi` `cheque` |
| `status` | string | `pending` `confirmed` `expired` `cancelled` |
| `collectorId` | int | filter by collector |
| `date` | string | `YYYY-MM-DD` |
| `donorType` | string | filter by donor type |

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "payments": [ { ...payment object... } ],
    "page": 1,
    "perPage": 20,
    "total": 180,
    "pages": 9
  }
}
```

---

## 8. Token Config (Admin)

### GET /api/admin/token-config
Requires: `users.manage`

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "config": {
      "tokenPrefix": "PP",
      "tokenSuffix": "SS",
      "tokenPadWidth": "4",
      "tokenStartNumber": "1",
      "tokenCurrentNumber": "102",
      "tokenDefaultTopic": "Durga Puja 2024"
    }
  }
}
```

`tokenCurrentNumber` is `null` if no token has been generated yet.

---

### POST /api/admin/token-config
Requires: `users.manage`

**Request** (any subset)
```json
{
  "tokenPrefix": "PP",
  "tokenSuffix": "SS",
  "tokenPadWidth": "4",
  "tokenStartNumber": "1",
  "tokenDefaultTopic": "Durga Puja 2024"
}
```

| Field | Notes |
|-------|-------|
| `tokenPrefix` | prepended to serial, e.g. `PP` |
| `tokenSuffix` | appended after serial, e.g. `SS` |
| `tokenPadWidth` | zero-pad width (default `4`) |
| `tokenStartNumber` | first serial after a counter reset (default `1`) |
| `tokenDefaultTopic` | fallback topic for single/dual tokens |

Token number format: `{prefix}{serial:0>padWidth}{suffix}` → e.g. `PP0001SS`

**Response 200**
```json
{
  "success": true,
  "message": "token config updated",
  "data": { "tokenPrefix": "PP", "tokenSuffix": "SS" }
}
```

---

### POST /api/admin/token-config/reset
Requires: `users.manage` **and** role must be `admin`. Resets running counter to `tokenStartNumber`.

**Request** — no body.

**Response 200**
```json
{
  "success": true,
  "message": "token counter reset",
  "data": { "nextTokenStartsAt": 1 }
}
```

**Error 403** — `only admin can reset the token counter`

---

## 9. Token Generation

### POST /api/token/generate
Requires: `token.generate`

- **single** → 1 sticker
- **dual** → 2 stickers (participant copy + official copy), same token number

**Request**
```json
{
  "type": "dual",
  "participantName": "Subhash Roy",
  "topic": "Durga Puja 2024"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `type` | Yes | `single` or `dual` |
| `participantName` | Yes | max 120 chars |
| `topic` | No | max 200 chars; falls back to `tokenDefaultTopic` |

**Response 201**
```json
{
  "success": true,
  "message": "token generated",
  "data": { ...token object... }
}
```

**Error 422** — `validation failed`

---

### POST /api/token/bulk
Requires: `token.bulk` — generates multiple minimal tokens (no name/topic).

**Request**
```json
{ "count": 50 }
```

`count`: 1–500.

**Response 201**
```json
{
  "success": true,
  "message": "bulk tokens generated",
  "data": {
    "batchId": "550e8400-e29b-41d4-a716-446655440000",
    "count": 50,
    "tokens": [ { ...token object... } ],
    "printUrl": "/token/print/bulk/550e8400-e29b-41d4-a716-446655440000"
  }
}
```

---

## 10. Token Queries

### GET /api/token/list
Requires: `token.generate`

**Query params**

| Param | Type | Notes |
|-------|------|-------|
| `page` | int | default `1` |
| `batchId` | string | filter to one bulk batch |

Returns 50 per page, newest first.

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "tokens": [ { ...token object... } ],
    "total": 102,
    "page": 1,
    "pages": 3
  }
}
```

---

### GET /api/token/:token_no
Requires: `token.generate` — case-insensitive lookup.

**Response 200** — token object. **Error 404** — `token not found`

---

### POST /api/token/:token_no/void
Requires: `users.manage` — marks token void (irreversible).

**Request** — no body.

**Response 200**
```json
{
  "success": true,
  "message": "token voided",
  "data": { ...token object with status "void"... }
}
```

**Error 404** — `token not found`

---

## 11. Token Pages (Browser)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/token/<token_no>` | Public QR verification page — shows active/void badge, full details. No auth. |
| GET | `/token/print/<token_no>` | Sticker print page — auto-opens print dialog. 2×2 in page size. |
| GET | `/token/print/bulk/<batch_id>` | Bulk sticker print — one minimal sticker per token in the batch. |

---

## 12. Cheque Payments

`method: "cheque"` is accepted everywhere `"cash"` and `"upi"` are — initiation, filters, summaries.

### Payment Object additions (cheque)

Cheque payments populate these otherwise-null fields:

```json
{
  "chequeNumber": "123456",
  "bankName": "State Bank of India",
  "chequeDate": "2024-09-01"
}
```

### Cheque UI Pages

| Method | Path | Description |
|--------|------|-------------|
| GET  | `/pay/cheque/<id>` | Cheque details form |
| POST | `/pay/cheque/<id>/confirm` | Submit `cheque_number`, `bank_name`, `cheque_date` (all optional) |
| POST | `/pay/cheque/<id>/cancel` | Cancel the payment |

---

## 13. Pledge (Partial / EMI Payments)

A pledge records a donor's total commitment. Installment payments are collected against it one at a time. The pledge auto-completes when fully paid.

**Pledge statuses:** `open` · `complete` (auto-set when paid ≥ total) · `cancelled`

> **Note:** Each installment payment reuses the pledge's original donor record — no new donor row is created per installment.

---

### POST /api/pledge/
Requires: `payment.initiate` (admin blocked)
Creates a pledge and a new donor record.

**Request**
```json
{
  "donorName": "Donor A",
  "donorPhone": "9800000010",
  "donorAddress": "12 Park Street",
  "donorNotes": null,
  "donorType": "individual",
  "totalAmount": "10000.00",
  "notes": "Paying in 2 installments"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `donorName` | Yes | max 120 chars |
| `donorPhone` | No | |
| `donorAddress` | No | |
| `donorNotes` | No | |
| `donorType` | No | |
| `totalAmount` | Yes | positive decimal — the full commitment |
| `notes` | No | pledge-level notes |

**Response 201**
```json
{
  "success": true,
  "message": "pledge created",
  "data": { ...pledge object... }
}
```

**Errors**

| Code | message |
|------|---------|
| 403  | `admin accounts cannot create pledges` |
| 422  | `validation failed` |

---

### POST /api/pledge/:id/pay
Requires: `payment.initiate` (admin blocked)
Initiates one installment against an open pledge.

**Request**
```json
{
  "amount": "5000.00",
  "method": "cash"
}
```

`method`: `cash` | `upi` | `cheque`
`amount` must not exceed `outstandingAmount`.

**Response 201**
```json
{
  "success": true,
  "message": "installment payment initiated",
  "data": {
    "paymentId": 55,
    "pledgeId": 1,
    "method": "cash",
    "amount": "5000.00",
    "status": "pending",
    "nextUrl": "/pay/cash/55"
  }
}
```

Open `nextUrl` in browser to confirm the payment. On confirmation the pledge's `paidAmount` updates automatically and status flips to `complete` if fully paid.

**Errors**

| Code | message |
|------|---------|
| 400  | `pledge not found` |
| 400  | `pledge is complete — cannot add payments` |
| 400  | `pledge is cancelled — cannot add payments` |
| 400  | `amount exceeds outstanding balance of ₹5000.00` |
| 422  | `validation failed` |

---

### GET /api/pledge/
Requires: `dashboard.view`

**Query params**

| Param | Type | Notes |
|-------|------|-------|
| `page` | int | default `1` |
| `perPage` | int | default `20`, max `100` |
| `status` | string | `open` `complete` `cancelled` |
| `collectorId` | int | filter by collector |

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "pledges": [ { ...pledge object... } ],
    "page": 1,
    "perPage": 20,
    "total": 12,
    "pages": 1
  }
}
```

---

### GET /api/pledge/:id
Requires: `payment.view_receipt` — full pledge + all its installment payments.

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "pledge": {
      "id": 1,
      "donor": { "id": 10, "name": "Donor A", "phone": "9800000010", "address": null, "notes": null, "donorType": "individual", "createdAt": "2024-09-01T12:00:00" },
      "collector": { "id": 3, "name": "Ramesh Das" },
      "totalAmount": "10000.00",
      "paidAmount": "5000.00",
      "outstandingAmount": "5000.00",
      "status": "open",
      "notes": "Paying in 2 installments",
      "createdAt": "2024-09-01T12:00:00"
    },
    "payments": [
      {
        "id": 55,
        "receiptNo": "RCP-A1B2C3D4",
        "amount": "5000.00",
        "method": "cash",
        "status": "confirmed",
        "utrNumber": null,
        "chequeNumber": null,
        "bankName": null,
        "chequeDate": null,
        "collector": { "id": 3, "name": "Ramesh Das" },
        "confirmedAt": "2024-09-01T15:00:00",
        "createdAt": "2024-09-01T14:55:00"
      }
    ]
  }
}
```

Payments are newest-first. All statuses included (`pending`, `confirmed`, `cancelled`, `expired`).

**Error 404** — `pledge not found`

---

### POST /api/pledge/:id/cancel
Requires: `users.manage` — cancels an open pledge. Completed pledges cannot be cancelled.

**Request** — no body.

**Response 200**
```json
{
  "success": true,
  "message": "pledge cancelled",
  "data": { ...pledge object with status "cancelled"... }
}
```

**Errors**

| Code | message |
|------|---------|
| 400  | `pledge not found` |
| 400  | `cannot cancel a completed pledge` |

---

## 14. Donor

> A new donor record is created per payment/pledge initiation. The same real person paying twice = two donor rows. The list reflects this.

### GET /api/donor/
Requires: `dashboard.view`

**Query params**

| Param | Type | Notes |
|-------|------|-------|
| `page` | int | default `1` |
| `perPage` | int | default `20`, max `100` |
| `search` | string | case-insensitive substring match on `name` or `phone` |
| `donorType` | string | case-insensitive exact match |

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "donors": [
      {
        "id": 10,
        "name": "Subhash Roy",
        "phone": "9800000010",
        "address": "12 Park Street, Kolkata",
        "notes": "regular donor",
        "donorType": "individual",
        "createdAt": "2024-09-01T12:00:00",
        "totalDonated": "1500.00",
        "confirmedCount": 3,
        "lastDonatedAt": "2024-09-05T10:30:00"
      }
    ],
    "page": 1,
    "perPage": 20,
    "total": 85,
    "pages": 5
  }
}
```

`totalDonated`, `confirmedCount`, `lastDonatedAt` — from confirmed payments only.

---

### GET /api/donor/:id
Requires: `dashboard.view` — full donor profile + complete payment history.

**Response 200**
```json
{
  "success": true,
  "message": null,
  "data": {
    "donor": {
      "id": 10,
      "name": "Subhash Roy",
      "phone": "9800000010",
      "address": "12 Park Street, Kolkata",
      "notes": "regular donor",
      "donorType": "individual",
      "createdAt": "2024-09-01T12:00:00",
      "totalDonated": "1500.00",
      "confirmedCount": 3,
      "lastDonatedAt": "2024-09-05T10:30:00"
    },
    "payments": [
      {
        "id": 42,
        "receiptNo": "RCP-A1B2C3D4",
        "amount": "500.00",
        "method": "upi",
        "status": "confirmed",
        "utrNumber": "UTR123456789",
        "collector": { "id": 3, "name": "Ramesh Das" },
        "confirmedAt": "2024-09-01T12:05:00",
        "createdAt": "2024-09-01T12:00:00"
      }
    ]
  }
}
```

Payments newest-first. All statuses included.

**Error 404** — `donor not found`

---

## Error Reference

All errors follow the same envelope:

```json
{
  "success": false,
  "message": "human-readable reason",
  "data": null
}
```

| HTTP Code | Meaning |
|-----------|---------|
| 400 | Bad request / business rule violated |
| 401 | Missing or invalid JWT |
| 403 | Authenticated but insufficient permission |
| 404 | Resource not found |
| 409 | Conflict (e.g. duplicate email) |
| 422 | Schema validation failed — `data` contains field-level errors |
| 500 | Internal server error |
