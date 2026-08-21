# TOKEN API

Token generation system for PujoPay. Supports single, dual and bulk token generation with QR verification.

---

## Response envelope

All API responses follow the same envelope:

```json
{
  "message": "human-readable status",
  "data": { ... }
}
```

`data` is `[]` when there is nothing to return.

---

## Token object

```json
{
  "id": 1,
  "tokenNo": "PP-0047-A",
  "slNo": 47,
  "type": "single",
  "status": "active",
  "participantName": "Suresh Mondal",
  "topic": "Cultural Program",
  "orgName": "Durga Puja 2025",
  "generatedBy": { "id": 3, "name": "Rahul Das" },
  "generatedAt": "2026-08-22T10:32:00",
  "batchId": null,
  "printUrl": "/token/print/PP-0047-A",
  "viewUrl": "/token/PP-0047-A"
}
```

| Field | Type | Notes |
|---|---|---|
| `tokenNo` | string | Prefix + zero-padded number + Suffix |
| `slNo` | int | Raw serial counter value = SL No |
| `type` | `single` / `dual` / `bulk` | |
| `status` | `active` / `void` | Voided by admin |
| `participantName` | string / null | null for bulk tokens |
| `topic` | string / null | null for bulk tokens |
| `batchId` | UUID / null | Groups bulk tokens; null for single/dual |
| `printUrl` | path | Open in browser → triggers 2×2 in print |
| `viewUrl` | path | Public QR verification page |

---

## Token Config (Admin only)

### `GET /api/admin/token-config`

Returns current token number configuration.

**Auth:** Bearer JWT · Role: `admin`

**Response 200**

```json
{
  "message": "",
  "data": {
    "config": {
      "tokenPrefix": "PP-",
      "tokenSuffix": "-A",
      "tokenPadWidth": "4",
      "tokenStartNumber": "1",
      "tokenCurrentNumber": "47",
      "tokenDefaultTopic": "Cultural Program"
    }
  }
}
```

---

### `POST /api/admin/token-config`

Update one or more config values. All fields optional.

**Auth:** Bearer JWT · Role: `admin`

**Request body**

```json
{
  "tokenPrefix": "PP-",
  "tokenSuffix": "-A",
  "tokenPadWidth": "4",
  "tokenStartNumber": "1",
  "tokenDefaultTopic": "Cultural Program"
}
```

| Field | Type | Notes |
|---|---|---|
| `tokenPrefix` | string | Prepended to number, e.g. `"PP-"` |
| `tokenSuffix` | string | Appended after number, e.g. `"-A"` |
| `tokenPadWidth` | string (int) | Zero-padding width for number (default `"4"`) |
| `tokenStartNumber` | string (int) | Counter resets to this value on reset |
| `tokenDefaultTopic` | string | Fallback topic when none provided |

**Response 200**

```json
{
  "message": "token config updated",
  "data": { "tokenPrefix": "PP-", "tokenSuffix": "-A" }
}
```

---

### `POST /api/admin/token-config/reset`

Reset the counter back to `tokenStartNumber`. Does **not** affect already-generated tokens.  
Next generated token will receive `tokenStartNumber`.

**Auth:** Bearer JWT · Role: `admin` only (executive/admin role check enforced)

**Request body:** none

**Response 200**

```json
{
  "message": "token counter reset",
  "data": { "nextTokenStartsAt": 1 }
}
```

**Errors**

| Code | message |
|---|---|
| 403 | `only admin can reset the token counter` |

---

## Token Generation

### `POST /api/token/generate`

Generate a **single** or **dual** token with full participant details.

- **Single** → 1 sticker (1-page PDF at 2×2 in)  
- **Dual** → 2 stickers: Participant Copy + Official Copy (2-page PDF, each page 2×2 in)

**Auth:** Bearer JWT · Permission: `token.generate`

**Request body**

```json
{
  "type": "dual",
  "participantName": "Suresh Mondal",
  "topic": "Cultural Program"
}
```

| Field | Required | Notes |
|---|---|---|
| `type` | ✅ | `single` or `dual` |
| `participantName` | ✅ | 1–120 chars |
| `topic` | — | Up to 200 chars. Falls back to `tokenDefaultTopic` config if omitted |

**Response 201**

```json
{
  "message": "token generated",
  "data": {
    "id": 1,
    "tokenNo": "PP-0047-A",
    "slNo": 47,
    "type": "dual",
    "status": "active",
    "participantName": "Suresh Mondal",
    "topic": "Cultural Program",
    "orgName": "Durga Puja 2025",
    "generatedBy": { "id": 3, "name": "Rahul Das" },
    "generatedAt": "2026-08-22T10:32:00",
    "batchId": null,
    "printUrl": "/token/print/PP-0047-A",
    "viewUrl": "/token/PP-0047-A"
  }
}
```

**Errors**

| Code | message |
|---|---|
| 422 | `validation failed` + field errors |
| 403 | `access denied` |

---

### `POST /api/token/bulk`

Generate N blank tokens in a single batch. Tokens have no participant name or topic — pre-printed stock.

**Auth:** Bearer JWT · Permission: `token.bulk`

**Request body**

```json
{ "count": 50 }
```

| Field | Required | Notes |
|---|---|---|
| `count` | ✅ | Integer 1–500 |

**Response 201**

```json
{
  "message": "bulk tokens generated",
  "data": {
    "batchId": "f4c3b2a1-...",
    "count": 50,
    "tokens": [ { ...token object... }, ... ],
    "printUrl": "/token/print/bulk/f4c3b2a1-..."
  }
}
```

**Errors**

| Code | message |
|---|---|
| 422 | `validation failed` |
| 403 | `access denied` |

---

## Token Management

### `GET /api/token/list`

List all tokens, newest first. Paginated at 50 per page.

**Auth:** Bearer JWT · Permission: `token.generate`

**Query params**

| Param | Notes |
|---|---|
| `page` | Page number (default 1) |
| `batchId` | Filter by bulk batch UUID |

**Response 200**

```json
{
  "message": "",
  "data": {
    "tokens": [ { ...token object... } ],
    "total": 120,
    "page": 1,
    "pages": 3
  }
}
```

---

### `GET /api/token/<token_no>`

Fetch a single token by its token number (e.g. `PP-0047-A`).

**Auth:** Bearer JWT · Permission: `token.generate`

**Response 200** — token object

**Errors**

| Code | message |
|---|---|
| 404 | `token not found` |

---

### `POST /api/token/<token_no>/void`

Mark a token as void. Voided tokens still exist in DB and the QR verification page shows them as invalid.

**Auth:** Bearer JWT · Permission: `users.manage` (admin)

**Request body:** none

**Response 200**

```json
{
  "message": "token voided",
  "data": { ...token object with status "void"... }
}
```

**Errors**

| Code | message |
|---|---|
| 404 | `token not found` |
| 403 | `access denied` |

---

## Public Pages (No Auth)

### `GET /token/<token_no>`

Public QR verification page. Shows token details and whether it is **Genuine (active)** or **Voided**.  
This is the URL embedded in every token's QR code.

**Auth:** None

**Returns:** HTML page

---

### `GET /token/print/<token_no>`

Print-ready HTML page for a single or dual token.

- Opens browser print dialog automatically on load
- `@page { size: 2in 2in; margin: 1.5mm }` — one sticker per page
- Dual type prints 2 pages: Participant Copy then Official Copy
- Use browser → Save as PDF to get a PDF file, or print directly to a label printer

**Auth:** None (URL contains token_no which serves as the access key)

---

### `GET /token/print/bulk/<batch_id>`

Print-ready HTML page for an entire bulk batch. N pages = N stickers.

**Auth:** None

---

## Token number format

```
tokenNo = tokenPrefix + zeroPad(serial, tokenPadWidth) + tokenSuffix
```

Example with `prefix="PP-"`, `suffix="-A"`, `padWidth=4`, `serial=47`:

```
PP-0047-A
```

The counter increments atomically using a PostgreSQL CTE (`INSERT … ON CONFLICT DO UPDATE … RETURNING`), ensuring no two tokens ever share the same serial even under concurrent requests.

---

## Permissions

| Permission key | Default roles |
|---|---|
| `token.generate` | admin, executive, committee, general |
| `token.bulk` | admin |
| `token.view` | admin, executive |

Admin can change grants via the permissions management API.
