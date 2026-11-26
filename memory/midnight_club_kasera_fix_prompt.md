# PROMPT UNTUK AGENT MIDNIGHT CLUB — Perbaiki "Failed to create payment" (QRIS via Midnight Link / Kasera)

## Masalah
Di modal "Top Up Credits" → tab QRIS → klik "Pay with QRIS", Midnight Club menampilkan
**"Failed to create payment"** dan QRIS tidak muncul.

Padahal sudah DIPASTIKAN dari log server Midnight Link (nginx + backend):
- `POST https://midnightlink.link/api/pay/charges` dari backend Midnight Club (python-httpx)
  dijawab **HTTP 200 OK dalam ±1–2 detik**, body ±2,9 KB, sudah berisi gambar QR.
- Charge tersimpan "pending" di Midnight Link, dan transaksi QRIS juga terbuat (pending) di Kasera.
- Setelah POST yang "gagal" itu, Midnight Club TIDAK pernah memanggil
  `GET /api/pay/charges/{id}` (tidak polling). Artinya Midnight Club membuang jawaban
  yang sebenarnya sukses, lalu menampilkan "Failed".
- Ada 1 charge (13:35 UTC, id `de749354-...`) yang berhasil dan di-polling, jadi API key
  dan koneksi BENAR. Masalahnya ada di cara Midnight Club MEMBACA / MEMPROSES jawaban.

Gateway pembayaran di Midnight Link sekarang **`kasera`** (dulu `klikqris` / `mayar`).
Kemungkinan besar kode Midnight Club masih hanya mengenal `klikqris`/`mayar`, atau
menganggap error kalau `qris_url` null / `pay_amount` ≠ `amount`.

**JANGAN ubah apa pun di sisi Midnight Link. Perbaikan HANYA di kode Midnight Club.**

---

## Kontrak API Midnight Link (sumber kebenaran)

Base URL: `https://midnightlink.link`
Auth: header `Authorization: Bearer <PARTNER_API_KEY>` (atau `X-Partner-Key: <key>`).
Simpan key di env backend Midnight Club. JANGAN panggil API ini dari browser/frontend,
selalu dari backend Midnight Club.

### 1. Buat charge
```
POST /api/pay/charges
Content-Type: application/json
{
  "amount": 700000,                       // integer Rupiah, min 10.000, max 10.000.000
  "reference_id": "MC-<uuid unik>",       // UNIK per percobaan bayar, max 120 karakter
  "customer": { "name": "Tama Go", "email": "tama@midnight.club", "mobile": "08xxxxxxxxxx" },
  "description": "Top up 700 credits — Tama Go",   // max 200 karakter
  "redirect_url": "https://<domain-midnight-club>/..."   // opsional
}
```
Panggilan ulang dengan `reference_id` yang SAMA akan mengembalikan charge yang SAMA
(idempotent), tidak membuat QRIS baru. Gunakan ini untuk retry yang aman.

Contoh jawaban 200 (gateway kasera):
```json
{
  "id": "c81c6cb9-....",                 // charge_id → simpan, dipakai untuk polling
  "reference_id": "MC-....",
  "amount": 700000,                      // nominal dasar yang diminta
  "currency": "IDR",
  "status": "pending",                   // pending | paid | expired
  "gateway": "kasera",                   // BISA: kasera | klikqris | mayar
  "checkout_url": "https://pay.kasera.id/p/....",   // halaman bayar hosted (cadangan)
  "qris_url": null,                      // NULL untuk kasera — jangan dianggap error
  "qris_image": "data:image/png;base64,iVBOR...",   // gambar QR siap <img src>
  "qr_string": "00020101021226...",      // kode QRIS mentah (EMV), boleh di-render sendiri
  "pay_amount": 705187,                  // NOMINAL PASTI yang dibayar user (termasuk biaya QRIS)
  "description": "Top up 700 credits — Tama Go",
  "created_at": "2026-11-26T13:36:34+00:00",
  "paid_at": null,
  "expires_at": "2026-11-26T14:36:34+00:00",
  "livemode": true                       // false = sandbox (uang tidak sungguhan)
}
```
Error: 400 (nominal di luar batas), 401 (API key salah), 422 (body tidak valid),
502 `{"detail": "Could not create payment: <alasan>"}` (gateway gagal).
Tampilkan `detail` ke user/log bila ada.

### 2. Cek status (polling) — WAJIB
```
GET /api/pay/charges/{charge_id}
Authorization: Bearer <PARTNER_API_KEY>
```
Bentuk jawaban sama dengan di atas. Server otomatis verifikasi ulang ke Kasera.
Poll tiap 4–5 detik sampai `status` = `paid` atau `expired` (QR berlaku ±60 menit).

### 3. Webhook `charge.paid` (opsional, best-effort; polling tetap jalan)
POST ke webhook_url Midnight Club:
```json
{ "id": "<delivery_id>", "event": "charge.paid", "created_at": "...",
  "data": { "charge_id": "...", "reference_id": "...", "amount": 700000, "currency": "IDR",
            "status": "paid", "paid_at": "...", "customer": {...} } }
```
Header: `X-MidnightLink-Signature: t=<unix>,v1=<hex>`, dengan
`v1 = HMAC_SHA256(webhook_secret, "<t>." + raw_body)` (hex). Verifikasi dengan RAW body.
Setelah webhook masuk, tetap konfirmasi via `GET /api/pay/charges/{id}` sebelum menambah kredit.

---

## Yang harus dikerjakan (urut)

1. **Cari sumber error dulu.** Temukan di kode Midnight Club (backend + frontend) tempat teks
   `"Failed to create payment"` dibuat. Tambahkan logging sementara: status code + body
   mentah jawaban dari `POST /api/pay/charges`, dan exception lengkap (traceback).
   Reproduksi top up (misal Rp10.000), lalu laporkan baris yang gagal.

2. **Dukung gateway `kasera`.** Jangan pernah menolak/mengabaikan jawaban hanya karena
   `gateway` bukan `klikqris`/`mayar`. Aturan tampilan:
   - Jika `qris_image` ada → tampilkan `<img src={qris_image}>` di modal (utama).
   - else jika `qris_url` ada → `<img src={qris_url}>`.
   - else jika `qr_string` ada → render QR dari string itu (library QR).
   - else jika `checkout_url` ada → tombol "Buka halaman pembayaran" (buka tab baru).
   - Hanya jika SEMUA kosong → baru tampilkan error.

3. **`qris_url: null` dan `pay_amount` ≠ `amount` itu NORMAL.**
   - Jangan validasi `pay_amount == amount`.
   - Tampilkan ke user: "Bayar **Rp{pay_amount}**" (format id-ID), dan jumlah kredit yang
     didapat tetap dihitung dari `amount` (bukan pay_amount).

4. **Validasi sukses = HTTP 2xx + ada field `id`.** Jangan bergantung pada field lain
   (mis. `klik_order_id`, `signature`, `invoice_id`) yang tidak ada di jawaban kasera.
   Akses field secara aman (`.get()` / optional chaining), jangan `data["qris_url"]` lalu crash.

5. **Simpan charge di DB Midnight Club** (invoice/top-up): `charge_id`, `reference_id`,
   `amount`, `pay_amount`, `gateway`, `status`, `expires_at`. Kolom `qris_url` harus boleh null.
   `reference_id` dibuat unik per percobaan (mis. `MC-<uuid4>`), agar tidak bentrok unique
   index di DB Midnight Club.

6. **Polling untuk semua gateway** (termasuk `kasera`), tiap 4–5 detik via backend
   Midnight Club → `GET /api/pay/charges/{id}`. Saat `status == "paid"`: tambah kredit user
   SEKALI saja (idempotent per `charge_id` — cek dulu apakah sudah dikredit). Saat
   `expired`: tutup QR, tampilkan "QR kedaluwarsa, buat ulang".

7. **Timeout & retry.** Timeout HTTP ke Midnight Link minimal 30 detik
   (`httpx.AsyncClient(timeout=30)`). Kalau timeout/5xx, retry POST dengan
   **reference_id yang sama** (aman, tidak membuat QRIS dobel).

8. **Pesan error yang jelas.** Jika API membalas non-2xx, tampilkan `detail` dari body
   (mis. "Minimum amount is Rp10,000"), bukan teks generik.

9. **"My Invoices".** Invoice pending yang punya `charge_id` bisa dibuka lagi untuk
   menampilkan QR yang sama (ambil dari `GET /api/pay/charges/{id}`), bukan membuat baru.

## Cara uji (wajib sebelum selesai)
- Top up Rp10.000 → QR tampil di modal dalam < 3 detik, nominal "Bayar Rp…" = `pay_amount`.
- Log backend menunjukkan POST 200 lalu GET polling berkala ke `/api/pay/charges/{id}`.
- Tutup & buka "My Invoices" → QR yang sama muncul lagi, tidak membuat charge baru.
- Simulasikan jawaban `gateway:"kasera"`, `qris_url:null`, `pay_amount > amount` di unit test
  → tidak boleh dianggap gagal.
- Setelah dibayar (atau status `paid` dari polling) → kredit bertambah tepat 1x
  sebesar `amount / rate`, dan webhook + polling bersamaan tidak membuat kredit dobel.
- Laporkan: file & baris penyebab "Failed to create payment", dan apa yang diubah.
