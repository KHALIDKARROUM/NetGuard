"""
test_api.py — Script de test complet de l'API Flask backend.
Lance ce script pendant que le backend tourne (python main.py).

Usage :
    python test_api.py
    python test_api.py --host http://localhost:5000
    python test_api.py --csv ../data/UNSW_NB15_training-set.csv
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_HOST = "http://localhost:5000"
DEFAULT_CSV = "../data/UNSW_NB15_training-set.csv"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ── Helpers ───────────────────────────────────────────────────────────────────

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg):  print(f"  {RED}✗{RESET} {msg}")
def info(msg):  print(f"  {BLUE}→{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET} {msg}")

def section(title):
    print(f"\n{BOLD}{'─' * 55}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─' * 55}{RESET}")

def check_response(r, expected_status=200):
    try:
        data = r.json()
    except Exception:
        fail(f"Réponse non-JSON reçue (status {r.status_code})")
        print(f"    Raw: {r.text[:200]}")
        return None
    if r.status_code == expected_status:
        ok(f"Status {r.status_code} — OK")
        return data
    else:
        fail(f"Status attendu {expected_status}, reçu {r.status_code}")
        if "error" in data:
            print(f"    Erreur : {data['error']}")
        return None


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_health(host):
    section("1. Health Check — GET /health")
    try:
        r = requests.get(f"{host}/health", timeout=5)
        data = check_response(r)
        if data:
            info(f"Service : {data.get('service')}")
            return True
    except requests.ConnectionError:
        fail(f"Impossible de se connecter à {host}")
        print(f"    → Le backend est-il lancé ? (python main.py)")
    return False


def test_root(host):
    section("2. Route racine — GET /")
    r = requests.get(f"{host}/", timeout=5)
    data = check_response(r)
    if data:
        info(f"Service : {data.get('service')}")
        info("Routes disponibles :")
        for route, desc in data.get("routes", {}).items():
            print(f"      {BLUE}{route}{RESET} → {desc}")
        return True
    return False


def test_swagger(host):
    section("2b. Swagger UI — GET /docs")
    r = requests.get(f"{host}/docs", timeout=5)
    if r.status_code == 200 and "swagger" in r.text.lower():
        ok(f"Swagger UI accessible → {host}/docs")
        info("Ouvre cette URL dans ton navigateur pour tester l'API visuellement.")
        return True
    fail(f"Swagger UI inaccessible (status {r.status_code})")
    return False


def test_upload(host, csv_path):
    section("3. Upload Dataset — POST /api/upload")
    csv_file = Path(csv_path)
    if not csv_file.exists():
        warn(f"Fichier CSV introuvable : {csv_path}")
        warn("Génération d'un mini-CSV (100 lignes) pour le test...")
        csv_path = _generate_mini_csv()

    info(f"Fichier : {csv_path}")
    start = time.perf_counter()

    with open(csv_path, "rb") as f:
        r = requests.post(
            f"{host}/api/upload",
            files={"file": (Path(csv_path).name, f, "text/csv")},
            timeout=60,
        )

    elapsed = time.perf_counter() - start
    data = check_response(r)

    if data:
        ov = data.get("overview", {})
        info(f"Temps : {elapsed:.2f}s")
        info(f"Lignes : {ov.get('n_rows', '?'):,}")
        info(f"Colonnes : {ov.get('n_cols', '?')}")
        info(f"Anomalies : {ov.get('n_anomalies', '?')} ({ov.get('anomaly_rate', '?')}%)")
        info(f"Mémoire : {ov.get('memory_mb', '?')} Mo")
        missing = ov.get("missing_values", {})
        if missing:
            warn(f"Valeurs manquantes détectées : {missing}")
        else:
            ok("Aucune valeur manquante")
        ok(f"Échantillon reçu : {len(data.get('sample', []))} lignes")
        return True
    return False


def test_invalid_upload(host):
    section("3b. Upload invalide — doit retourner 400")

    r = requests.post(f"{host}/api/upload", timeout=5)
    data = r.json()
    if r.status_code == 400:
        ok(f"Sans fichier → 400 : {data.get('error')}")
    else:
        fail(f"Attendu 400, reçu {r.status_code}")

    r = requests.post(
        f"{host}/api/upload",
        files={"file": ("test.txt", b"pas un csv", "text/plain")},
        timeout=5,
    )
    data = r.json()
    if r.status_code == 400:
        ok(f"Fichier non-CSV → 400 : {data.get('error')}")
    else:
        fail(f"Attendu 400, reçu {r.status_code}")

    return True


def test_train(host, params=None):
    section("4. Entraînement — POST /api/train")
    params = params or {
        "contamination": 0.1,
        "n_estimators": 50,
        "eps": 0.5,
        "min_samples": 10,
    }
    info(f"Paramètres : {params}")
    start = time.perf_counter()

    r = requests.post(f"{host}/api/train", json=params, timeout=300)
    elapsed = time.perf_counter() - start
    data = check_response(r)

    if data:
        info(f"Temps total : {elapsed:.2f}s")
        tt = data.get("train_times", {})
        info(f"  Isolation Forest : {tt.get('isolation_forest_train_time', '?')}s")
        info(f"  DBSCAN           : {tt.get('dbscan_train_time', '?')}s")
        info(f"Samples : {data.get('n_samples_train', '?'):,}  |  Features : {data.get('n_features', '?')}")

        metrics = data.get("metrics", {})
        if metrics:
            ok("Métriques calculées :")
            for key, m in metrics.items():
                print(f"\n    {BOLD}{m.get('model', key)}{RESET}")
                print(f"      F1-Score  : {m.get('f1_score', '?')}")
                print(f"      ROC-AUC   : {m.get('roc_auc', '?')}")
                print(f"      Precision : {m.get('precision', '?')}")
                print(f"      Recall    : {m.get('recall', '?')}")
                cm = m.get("confusion_matrix", {})
                print(f"      Confusion  : TP={cm.get('tp')} TN={cm.get('tn')} FP={cm.get('fp')} FN={cm.get('fn')}")
        else:
            warn("Pas de métriques (colonne 'label' absente ?)")
        return True
    return False


def test_invalid_train(host):
    section("4b. Train invalide — doit retourner 400")

    r = requests.post(f"{host}/api/train", json={"contamination": 0.99}, timeout=10)
    data = r.json()
    if r.status_code == 400:
        ok(f"contamination=0.99 → 400 : {data.get('error')}")
    else:
        fail(f"Attendu 400, reçu {r.status_code}")

    r = requests.post(f"{host}/api/train", json={"n_estimators": 5}, timeout=10)
    data = r.json()
    if r.status_code == 400:
        ok(f"n_estimators=5 → 400 : {data.get('error')}")
    else:
        fail(f"Attendu 400, reçu {r.status_code}")

    return True


def test_predict(host):
    section("5. Prédictions — POST /api/predict")

    r = requests.post(f"{host}/api/predict", json={"model": "both"}, timeout=60)
    data = check_response(r)

    if data:
        for key, s in data.get("summaries", {}).items():
            print(f"\n    {BOLD}{s.get('model', key)}{RESET}")
            info(f"Anomalies : {s.get('n_anomalies', '?'):,}")
            info(f"Normal    : {s.get('n_normal', '?'):,}")
            info(f"Taux      : {s.get('anomaly_rate', '?')}%")
            info(f"Score moy : {s.get('score_mean', 0):.4f}  |  P95 : {s.get('score_p95', 0):.4f}")
        n = len(data.get("sample", {}).get("if_predictions", []))
        ok(f"Échantillon : {n} observations")
        return True
    return False


def test_metrics(host):
    section("6. Métriques — GET /api/metrics")

    r = requests.get(f"{host}/api/metrics", timeout=30)
    data = check_response(r)

    if data:
        info(f"Depuis cache : {data.get('from_cache', False)}")
        for key, m in data.get("metrics", {}).items():
            print(f"\n    {BOLD}{m.get('model', key)}{RESET}")
            print(f"      Precision  : {m.get('precision', '?')}")
            print(f"      Recall     : {m.get('recall', '?')}")
            print(f"      F1         : {m.get('f1_score', '?')}")
            print(f"      ROC-AUC    : {m.get('roc_auc', '?')}")
            print(f"      TPR / FPR  : {m.get('true_positive_rate', '?')} / {m.get('false_positive_rate', '?')}")
        ok("Matrices de confusion reçues") if data.get("confusion_matrices") else None
        return True
    return False


def test_metrics_summary(host):
    section("6b. Résumé métriques — GET /api/metrics/summary")

    r = requests.get(f"{host}/api/metrics/summary", timeout=10)
    data = check_response(r)

    if data:
        for key, s in data.get("summary", {}).items():
            print(f"\n    {BOLD}{s.get('model', key)}{RESET}")
            print(f"      F1      : {s.get('f1_score', '?')}")
            print(f"      ROC-AUC : {s.get('roc_auc', '?')}")
        info(f"Params : {data.get('train_params', {})}")
        return True
    return False


def test_visualizations(host):
    section("7. Visualisations — GET /api/visualization")

    viz_types = ["labels", "distributions", "scores", "pca"]
    results = {}

    for vtype in viz_types:
        url = f"{host}/api/visualization?type={vtype}&model=isolation_forest"
        start = time.perf_counter()
        r = requests.get(url, timeout=120)
        elapsed = time.perf_counter() - start

        if r.status_code == 200:
            vdata = r.json().get("data", {})
            size = len(json.dumps(vdata))
            size_str = f"~{size//1000} Ko" if size > 1000 else f"~{size} o"
            ok(f"type={vtype:<14} {elapsed:.2f}s   {size_str}")
            results[vtype] = True
        else:
            try:
                err = r.json().get("error", "?")
            except Exception:
                err = r.text[:80]
            fail(f"type={vtype} → {r.status_code} : {err}")
            results[vtype] = False

    warn("t-SNE skippé (lent) — tester manuellement :")
    info(f"curl '{host}/api/visualization?type=tsne'")
    return all(results.values())


def test_404(host):
    section("8. Route inexistante — doit retourner 404 JSON")
    r = requests.get(f"{host}/api/inexistant", timeout=5)
    data = r.json()
    if r.status_code == 404 and "error" in data:
        ok(f"404 retourné proprement : {data['error']}")
        return True
    fail(f"Attendu 404 JSON, reçu {r.status_code}")
    return False


# ── Génération mini-CSV ───────────────────────────────────────────────────────

def _generate_mini_csv():
    import random, csv, tempfile

    columns = [
        "id","dur","proto","service","state","spkts","dpkts","sbytes","dbytes",
        "rate","sttl","dttl","sload","dload","sloss","dloss","sinpkt","dinpkt",
        "sjit","djit","swin","stcpb","dtcpb","dwin","tcprtt","synack","ackdat",
        "smean","dmean","trans_depth","response_body_len","ct_srv_src","ct_state_ttl",
        "ct_dst_ltm","ct_src_dport_ltm","ct_dst_sport_ltm","ct_dst_src_ltm",
        "is_ftp_login","ct_ftp_cmd","ct_flw_http_mthd","ct_src_ltm","ct_srv_dst",
        "is_sm_ips_ports","attack_cat","label"
    ]
    protos = ["tcp","udp","icmp"]
    services = ["-","http","ftp","dns","ssh"]
    states = ["FIN","CON","INT","REQ"]
    attack_cats = ["Normal","Exploits","Reconnaissance","DoS","Generic"]

    rows = []
    for i in range(200):
        is_anomaly = 1 if random.random() < 0.2 else 0
        rows.append({
            "id": i+1, "dur": round(random.uniform(0,100),4),
            "proto": random.choice(protos), "service": random.choice(services),
            "state": random.choice(states), "spkts": random.randint(1,1000),
            "dpkts": random.randint(0,1000), "sbytes": random.randint(100,100000),
            "dbytes": random.randint(0,100000), "rate": round(random.uniform(0,1000),4),
            "sttl": random.choice([64,128,255]), "dttl": random.choice([0,64,128]),
            "sload": round(random.uniform(0,1e6),2), "dload": round(random.uniform(0,1e6),2),
            "sloss": random.randint(0,10), "dloss": random.randint(0,10),
            "sinpkt": round(random.uniform(0,100),4), "dinpkt": round(random.uniform(0,100),4),
            "sjit": round(random.uniform(0,50),4), "djit": round(random.uniform(0,50),4),
            "swin": random.choice([0,255]), "stcpb": random.randint(0,2**31),
            "dtcpb": random.randint(0,2**31), "dwin": random.choice([0,255]),
            "tcprtt": round(random.uniform(0,1),4), "synack": round(random.uniform(0,1),4),
            "ackdat": round(random.uniform(0,1),4), "smean": random.randint(0,1000),
            "dmean": random.randint(0,1000), "trans_depth": random.randint(0,5),
            "response_body_len": random.randint(0,10000), "ct_srv_src": random.randint(1,100),
            "ct_state_ttl": random.randint(0,6), "ct_dst_ltm": random.randint(1,100),
            "ct_src_dport_ltm": random.randint(1,100), "ct_dst_sport_ltm": random.randint(1,100),
            "ct_dst_src_ltm": random.randint(1,100), "is_ftp_login": random.randint(0,1),
            "ct_ftp_cmd": random.randint(0,5), "ct_flw_http_mthd": random.randint(0,10),
            "ct_src_ltm": random.randint(1,100), "ct_srv_dst": random.randint(1,100),
            "is_sm_ips_ports": random.randint(0,1),
            "attack_cat": "Normal" if not is_anomaly else random.choice(attack_cats[1:]),
            "label": is_anomaly,
        })

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", newline="")
    writer = csv.DictWriter(tmp, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    tmp.close()
    return tmp.name


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Test API Flask — Anomaly Detection")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument("--skip-train", action="store_true")
    args = parser.parse_args()
    host = args.host.rstrip("/")

    print(f"\n{BOLD}{'=' * 55}{RESET}")
    print(f"{BOLD}  TEST API — Anomaly Detection Backend{RESET}")
    print(f"{BOLD}  Host : {host}{RESET}")
    print(f"{BOLD}{'=' * 55}{RESET}")

    results = {}

    if not test_health(host):
        print(f"\n{RED}{BOLD}Backend inaccessible. Arrêt des tests.{RESET}")
        sys.exit(1)

    results["root"]           = test_root(host)
    results["swagger"]        = test_swagger(host)
    results["upload"]         = test_upload(host, args.csv)
    results["upload_invalid"] = test_invalid_upload(host)

    if not results["upload"]:
        print(f"\n{RED}Upload échoué — arrêt.{RESET}")
        sys.exit(1)

    if not args.skip_train:
        results["train"]         = test_train(host)
        results["train_invalid"] = test_invalid_train(host)
    else:
        warn("Entraînement skippé (--skip-train)")
        results["train"] = True

    if not results["train"]:
        print(f"\n{RED}Entraînement échoué — arrêt.{RESET}")
        sys.exit(1)

    results["predict"]         = test_predict(host)
    results["metrics"]         = test_metrics(host)
    results["metrics_summary"] = test_metrics_summary(host)
    results["visualization"]   = test_visualizations(host)
    results["404"]             = test_404(host)

    section("Résumé final")
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  [{status}] {name}")

    print()
    if passed == total:
        print(f"{GREEN}{BOLD}  ✓ Tous les tests passent ({passed}/{total}) — API prête !{RESET}")
    else:
        print(f"{YELLOW}{BOLD}  ⚠ {passed}/{total} tests passent{RESET}")
        print(f"  → Consulte backend/logs/app.log pour les détails.")
    print()


if __name__ == "__main__":
    main()