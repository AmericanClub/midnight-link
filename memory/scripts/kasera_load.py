"""Kasera partner-payment load test (Sandbox). Mimics Midnight Club: burst creates + 4s polling."""
import asyncio, json, random, time, uuid, sys
import httpx

API = sys.argv[1]
N_BURST = int(sys.argv[2]) if len(sys.argv) > 2 else 30
N_LATE = int(sys.argv[3]) if len(sys.argv) > 3 else 10
POLL_S = 4
DURATION = int(sys.argv[4]) if len(sys.argv) > 4 else 100
ABANDON = 5
ADMIN = {"email": "admin@midnightlink.link", "password": "Admin123!"}

res = {"create": [], "poll_ok": 0, "poll_err": {}, "paid_seen": {}, "sim": {}, "sim_err": []}


async def create(c, key, i):
    t = time.perf_counter()
    try:
        r = await c.post(f"{API}/api/pay/charges", headers={"Authorization": f"Bearer {key}"},
                         json={"amount": random.choice([10000, 25000, 50000, 100000, 250000]),
                               "reference_id": f"LOAD-{uuid.uuid4().hex[:10]}",
                               "customer": {"name": f"Member {i}"}})
        dt = time.perf_counter() - t
        ok = r.status_code == 200 and r.json().get("qris_image")
        res["create"].append({"ok": bool(ok), "code": r.status_code, "s": round(dt, 2),
                              "err": None if ok else r.text[:160]})
        return r.json() if ok else None
    except Exception as e:  # noqa
        res["create"].append({"ok": False, "code": None, "s": round(time.perf_counter() - t, 2), "err": str(e)[:160]})
        return None


async def poller(c, key, ch, stop_at):
    while time.time() < stop_at:
        try:
            r = await c.get(f"{API}/api/pay/charges/{ch['id']}", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                res["poll_ok"] += 1
                if r.json().get("status") == "paid" and ch["id"] not in res["paid_seen"]:
                    res["paid_seen"][ch["id"]] = time.time()
                    return
            else:
                res["poll_err"][r.status_code] = res["poll_err"].get(r.status_code, 0) + 1
        except Exception as e:  # noqa
            res["poll_err"]["exc"] = res["poll_err"].get("exc", 0) + 1
        await asyncio.sleep(POLL_S)


async def simulate(c, ch, delay):
    await asyncio.sleep(delay)
    tok = ch["checkout_url"].split("/p/", 1)[1].split("?")[0]
    try:
        r = await c.post(f"https://pay.kasera.id/api/v1/checkout/{tok}/simulate-payment", json={"outcome": "succeeded"})
        if r.status_code < 300:
            res["sim"][ch["id"]] = time.time()
        else:
            res["sim_err"].append((r.status_code, r.text[:120]))
    except Exception as e:  # noqa
        res["sim_err"].append(("exc", str(e)[:120]))


async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{API}/api/auth/login", json=ADMIN); r.raise_for_status()
        cfg = (await c.get(f"{API}/api/admin/payment-config")).json()
        prev = cfg["active_gateway"]
        await c.put(f"{API}/api/admin/payment-config", json={"active_gateway": "kasera"})
        p = (await c.post(f"{API}/api/admin/partners", json={"name": "LoadTest Kasera",
                          "webhook_url": "https://httpbin.org/post"})).json()
        key, pid = p["api_key"], p["id"]
        print("partner", pid, "prev_gateway", prev, flush=True)
        t0 = time.time()
        stop_at = t0 + DURATION
        burst = await asyncio.gather(*[create(c, key, i) for i in range(N_BURST)])
        charges = [b for b in burst if b]
        print(f"burst: {len(charges)}/{N_BURST} ok in {time.time()-t0:.1f}s", flush=True)
        tasks = [asyncio.create_task(poller(c, key, ch, stop_at)) for ch in charges]
        payable = charges[ABANDON:]
        sims = [asyncio.create_task(simulate(c, ch, 8 + i * 1.5)) for i, ch in enumerate(payable)]
        await asyncio.sleep(25)
        late = await asyncio.gather(*[create(c, key, 1000 + i) for i in range(N_LATE)])
        late = [x for x in late if x]
        print(f"late creates under polling load: {len(late)}/{N_LATE} ok", flush=True)
        tasks += [asyncio.create_task(poller(c, key, ch, stop_at)) for ch in late]
        sims += [asyncio.create_task(simulate(c, ch, 5 + i * 2)) for i, ch in enumerate(late)]
        await asyncio.gather(*sims)
        await asyncio.gather(*tasks)
        t_end = time.time()
        await asyncio.sleep(12)
        allc = charges + late
        paid_ids = set(res["sim"])
        lat = [res["paid_seen"][i] - res["sim"][i] for i in paid_ids if i in res["paid_seen"]]
        out = {
            "partner_id": pid, "prev_gateway": prev, "t0": t0, "t_end": t_end,
            "creates_total": len(res["create"]), "creates_ok": sum(x["ok"] for x in res["create"]),
            "create_latency_s": sorted(x["s"] for x in res["create"]),
            "create_errors": [x for x in res["create"] if not x["ok"]][:8],
            "simulated_paid": len(paid_ids), "sim_errors": res["sim_err"][:5],
            "paid_seen_by_partner_poll": len([i for i in paid_ids if i in res["paid_seen"]]),
            "paid_latency_s": {"min": round(min(lat), 1) if lat else None,
                               "avg": round(sum(lat) / len(lat), 1) if lat else None,
                               "max": round(max(lat), 1) if lat else None},
            "polls_ok": res["poll_ok"], "poll_errors": res["poll_err"],
            "charge_ids": [x["id"] for x in allc], "paid_ids": list(paid_ids),
        }
        json.dump(out, open("/tmp/kasera_load_result.json", "w"))
        print(json.dumps({k: v for k, v in out.items() if k not in ("charge_ids", "paid_ids", "create_latency_s")}, indent=1))
        ls = out["create_latency_s"]
        print("create latency p50/p90/max:", ls[len(ls)//2] if ls else None, ls[int(len(ls)*0.9)] if ls else None, ls[-1] if ls else None)

asyncio.run(main())
