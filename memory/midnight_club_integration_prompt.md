# Prompt: Tampilkan QRIS Midnight Link langsung di dalam aplikasi Midnight Club

> Serahkan prompt ini ke developer / AI builder Midnight Club. Midnight Club adalah aplikasi
> terpisah yang memakai **Midnight Link** sebagai payment provider (partner payment API).
> Tujuannya: saat member Midnight Club membayar, **QRIS tampil langsung di dalam aplikasi**
> (tidak membuka tab baru) — persis seperti pengalaman top-up di Midnight Link.

---

## Konteks

Midnight Link menyediakan **Partner Payment API**. Midnight Club memanggil API ini untuk:
1. Membuat charge (tagihan) → dapat data QRIS.
2. Menampilkan QRIS di dalam app + polling status sampai lunas.
3. (Opsional) menerima webhook `charge.paid` yang bertanda tangan HMAC.

Gateway aktif ditentukan oleh admin Midnight Link (Mayar **atau** KlikQRIS — hanya satu aktif).
- **KlikQRIS** → API mengembalikan `qris_image` + `qris_url` + `pay_amount` → **QRIS bisa dirender native di app** (inilah yang kita mau).
- **Mayar** → API hanya mengembalikan `checkout_url` (halaman checkout hosted Mayar). Mayar TIDAK memberi QRIS mentah, jadi untuk Mayar harus redirect/buka `checkout_url`.

Logika app: `if gateway === "klikqris"` → render QR in-app; `else (mayar)` → buka `checkout_url`.

---

## Konfigurasi (env di Midnight Club)

```
MIDNIGHTLINK_BASE_URL=   # TEST: https://link-midnight-design.preview.emergentagent.com
                         # LIVE: https://midnightlink.link
MIDNIGHTLINK_PARTNER_KEY=mgpay_live_xxxxxxxx   # dari Admin Midnight Link → Payment Partners
MIDNIGHTLINK_WEBHOOK_SECRET=mgwhsec_xxxxxxxx    # untuk verifikasi tanda tangan webhook
```
> Untuk uji coba aman, arahkan `MIDNIGHTLINK_BASE_URL` ke server **preview** dulu dan buat
> partner test di Admin preview. Jangan sentuh kredensial/partner produksi sampai siap live.

Semua request pakai header auth:
```
Authorization: Bearer <MIDNIGHTLINK_PARTNER_KEY>
```

---

## 1) Test koneksi
```
GET {BASE_URL}/api/pay/ping
→ 200 { "ok": true, "partner": "midnight", "min_amount": 10000, "max_amount": 10000000, "currency": "IDR" }
```

## 2) Buat charge
```
POST {BASE_URL}/api/pay/charges
Content-Type: application/json
{
  "amount": 15000,                 // Rp, integer. Min 10.000, max 10.000.000
  "reference_id": "ORDER-123",     // unik per pembayaran; idempotent (panggilan ulang → charge yang sama)
  "customer": { "name": "Budi", "email": "budi@x.com", "mobile": "081234567890" },
  "description": "Topup Midnight Club",
  "redirect_url": "https://midnightclub.app/pay/return"   // opsional (dipakai gateway hosted)
}
```
Response (201/200):
```json
{
  "id": "b1c2...",              // charge_id (dipakai untuk polling)
  "reference_id": "ORDER-123",
  "amount": 15000,
  "currency": "IDR",
  "status": "pending",          // pending | paid | expired
  "gateway": "klikqris",        // klikqris | mayar
  "checkout_url": "https://...",// halaman hosted (dipakai kalau gateway = mayar)
  "qris_url": "https://klikqris.com/q/....png",   // URL gambar QR (klikqris)
  "qris_image": "data:image/png;base64,....",     // QR base64 siap <img src> (klikqris); null utk mayar
  "pay_amount": 15234,          // NOMINAL PASTI yang harus dibayar (base + kode unik). TAMPILKAN INI.
  "expires_at": "2026-06-01T10:15:00+00:00",
  "created_at": "...", "paid_at": null
}
```

## 3) Cek status (polling)
```
GET {BASE_URL}/api/pay/charges/{charge_id}
→ response bentuknya sama seperti di atas (termasuk qris_image/qris_url/pay_amount).
  Server otomatis re-verify ke gateway; status berubah ke "paid" saat pembayaran terkonfirmasi.
```

---

## Contoh UI (React) — render QRIS in-app + polling

```jsx
async function startPayment({ amount, reference_id, customer }) {
  const res = await fetch(`${BASE_URL}/api/pay/charges`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${PARTNER_KEY}` },
    body: JSON.stringify({ amount, reference_id, customer, description: "Topup Midnight Club" }),
  });
  return res.json(); // charge
}

function PaymentModal({ charge, onPaid }) {
  const [status, setStatus] = React.useState(charge.status);

  // Gateway Mayar tidak punya QR mentah → buka checkout hosted
  React.useEffect(() => {
    if (charge.gateway === "mayar" && charge.checkout_url) {
      window.location.href = charge.checkout_url; // atau buka di tab/iframe
    }
  }, [charge]);

  // Polling status tiap 4 detik (fallback andal, tidak bergantung webhook)
  React.useEffect(() => {
    if (charge.gateway !== "klikqris") return;
    const t = setInterval(async () => {
      const r = await fetch(`${BASE_URL}/api/pay/charges/${charge.id}`, {
        headers: { Authorization: `Bearer ${PARTNER_KEY}` },
      });
      const d = await r.json();
      setStatus(d.status);
      if (d.status === "paid") { clearInterval(t); onPaid(d); }      // ⟵ kredit member DI SINI
      if (d.status === "expired") { clearInterval(t); }
    }, 4000);
    return () => clearInterval(t);
  }, [charge]);

  if (charge.gateway !== "klikqris") return null;
  return (
    <div className="qris-modal">
      <img src={charge.qris_image || charge.qris_url} alt="QRIS" width={220} height={220} />
      <p>Scan & bayar <b>Rp{charge.pay_amount.toLocaleString("id-ID")}</b></p>
      <p>Buka GoPay/OVO/DANA/ShopeePay/m-banking, scan, bayar nominal PERSIS di atas.</p>
      <Countdown until={charge.expires_at} />
      {status === "paid"    && <p>✅ Pembayaran diterima!</p>}
      {status === "expired" && <p>⛔ QR kadaluarsa, buat ulang.</p>}
    </div>
  );
}
```

---

## Webhook `charge.paid` (opsional, tapi disarankan)

Midnight Link mengirim POST ke `webhook_url` partner saat charge lunas:
```
POST <webhook_url partner>
Headers:
  X-MidnightLink-Event: charge.paid
  X-MidnightLink-Delivery: <uuid>
  X-MidnightLink-Signature: t=<unix_ts>,v1=<hmac_sha256_hex>
Body (JSON, compact):
  { "id":"...", "event":"charge.paid", "created_at":"...",
    "data": { "charge_id":"...", "reference_id":"ORDER-123", "amount":15000,
              "currency":"IDR", "status":"paid", "paid_at":"...", "customer":{...} } }
```
Skema tanda tangan: `v1 = HMAC_SHA256(WEBHOOK_SECRET, "<t>." + RAW_BODY)` (hex).
Verifikasi WAJIB pakai **raw body** (jangan JSON.parse lalu serialize ulang).

Contoh Node/Express:
```js
app.post("/api/midnightlink/webhook", express.raw({ type: "application/json" }), (req, res) => {
  const sigHeader = req.get("X-MidnightLink-Signature") || "";     // "t=...,v1=..."
  const parts = Object.fromEntries(sigHeader.split(",").map((p) => p.split("=")));
  const expected = crypto.createHmac("sha256", process.env.MIDNIGHTLINK_WEBHOOK_SECRET)
                         .update(`${parts.t}.`).update(req.body).digest("hex");
  const ok = parts.v1 && crypto.timingSafeEqual(Buffer.from(parts.v1), Buffer.from(expected));
  if (!ok) return res.status(401).end();

  const evt = JSON.parse(req.body.toString());
  // JANGAN langsung percaya "paid" — re-verify dulu:
  //   GET {BASE_URL}/api/pay/charges/{evt.data.charge_id}  → pastikan status === "paid"
  // Baru kredit member (idempotent per reference_id / charge_id).
  res.json({ ok: true });
});
```

## Aturan keamanan (penting)
- **Selalu kredit member berdasarkan hasil GET status = "paid"** (baik dari polling maupun setelah webhook). Jangan pernah mengkredit hanya karena UI/klien bilang "sudah bayar".
- **Idempotent**: pakai `reference_id` atau `charge_id` sebagai kunci unik agar member tidak dikredit dobel (webhook + polling bisa datang bersamaan).
- Webhook bersifat best-effort (ada retry). **Polling adalah fallback utama** — pastikan tetap jalan meski webhook tidak sampai.

## Checklist uji coba (di preview dulu)
1. `GET /api/pay/ping` → 200.
2. Pastikan gateway aktif di Admin Midnight Link = **KlikQRIS** (agar dapat QR mentah).
3. `POST /api/pay/charges` → tampilkan `qris_image` + `pay_amount` di modal.
4. Bayar nominal `pay_amount` → polling berubah ke `paid` → member terkredit sekali.
5. Uji webhook (signature valid → 200, invalid → 401).
6. Uji Mayar aktif → app membuka `checkout_url` (tab/iframe), bukan QR mentah.
7. Baru pindah `MIDNIGHTLINK_BASE_URL` + kredensial ke produksi saat sudah yakin.
