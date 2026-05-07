# 🛡️ Détection d'Anomalies Réseau — UNSW-NB15

> Application interactive de détection d'intrusions réseau non supervisée,  
> construite avec **Isolation Forest**, un backend **FastAPI** et un frontend **Streamlit**.

---

## 📌 Présentation

L'objectif de ce projet est de **détecter automatiquement les connexions réseau anormales** — attaques, intrusions, comportements suspects — sans avoir besoin d'étiquettes pendant l'entraînement.

On s'appuie sur le dataset public **UNSW-NB15**, généré par l'Université de New South Wales. Il contient 175 341 connexions réseau réelles, avec un mélange de trafic normal et de différents types d'attaques.

L'approche est **non supervisée** : le modèle apprend ce qu'est un comportement "normal", puis signale tout ce qui s'en écarte comme une anomalie potentielle.

---

## ❓ Pourquoi "non supervisé" si le dataset a des labels ?

Le dataset UNSW-NB15 contient bien une colonne `label` (0 = Normal, 1 = Attaque). Mais **avoir des labels ne veut pas dire qu'on est obligé de les utiliser pour entraîner le modèle**.

```python
# Supervisé (ex : Random Forest)
model.fit(X_train, y_train)   # ← y utilisé pendant l'entraînement

# Non supervisé — notre cas
model.fit(X_train)            # ← pas de y, le modèle ne voit jamais les labels
```

Les labels servent uniquement **après coup**, pour mesurer si le modèle a eu raison. C'est comme un examen : le modèle répond sans voir le corrigé, et on compare ses réponses une fois l'évaluation terminée.

L'intérêt de l'approche non supervisée en cybersécurité : un modèle supervisé ne peut détecter que les attaques qu'il a déjà vues. Un modèle non supervisé détecte **tout ce qui est anormal**, y compris les nouvelles attaques inconnues.

---

## 🗂️ Structure du projet

```
anomaly-detection/
│
├── backend/                        # API REST FastAPI
│   ├── main.py                     # Point d'entrée, lifespan, chargement du modèle
│   ├── config.py                   # Constantes, chemins, FEATURE_NAMES
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── dataset.py              # GET /api/dataset/*
│   │   ├── metrics.py              # GET /api/metrics/*
│   │   └── prediction.py           # GET/POST /api/predict/*
│   └── utils/
│       ├── __init__.py
│       ├── exceptions.py           # DataLoadError, ModelError, APIError
│       ├── model_loader.py         # Classe BestModelLoader (Isolation Forest)
│       ├── data_loader.py          # Classe DataLoader + générateur read_csv_chunks
│       └── evaluator.py            # compute_metrics, get_pca_data
│
├── frontend/                       # Interface Streamlit
│   ├── app.py                      # Page d'accueil + shell de navigation
│   ├── config.py                   # Client API, CSS, composants UI réutilisables
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pages/
│       ├── 01_dataset.py           # Page 1 — Exploration du dataset
│       ├── 02_performance.py       # Page 2 — Métriques du modèle
│       └── 03_prediction.py        # Page 3 — Prédiction en temps réel
│
├── notebooks/                      # Exploration et prototypage
│   ├── 01_eda.ipynb                # Analyse exploratoire du dataset
│   ├── 02_preprocessing.ipynb      # Nettoyage, encodage, normalisation
│   ├── 03_feature_engineering.ipynb # Sélection des 20 features finales
│   ├── 04_isolation_forest.ipynb   # Entraînement et optimisation de l'IF
│   ├── 05_dbscan.ipynb             # Expérimentation DBSCAN
│   ├── 06_model_improvements.ipynb # Autoencoder, LOF, ensembles
│   └── 07_evaluation.ipynb         # Comparaison finale des modèles
│
├── models_saved/                   # Modèles et artefacts sauvegardés
│   ├── if_base.pkl                 # Isolation Forest (modèle déployé)
│   ├── qt_if.pkl                   # QuantileTransformer pour l'IF
│   ├── if_config.json              # Paramètres optimaux (contamination=0.40)
│   ├── lof.pkl                     # Local Outlier Factor
│   ├── autoencoder.pt              # Autoencoder PyTorch
│   └── ensemble_3models.pkl        # Config ensemble IF+LOF+AE
│
├── data/
│   ├── featured/
│   │   ├── train_featured.csv      # Données d'entraînement (175 341 lignes, 20 features)
│   │   └── test_featured.csv       # Données de test (82 332 lignes, 20 features)
│   └── reports/
│       └── model_comparison.csv    # Métriques comparatives des modèles
│
├── retrain_if.py                   # Script pour réentraîner l'Isolation Forest
├── docker-compose.yml              # Orchestration backend + frontend
└── README.md
```

---

## ⚙️ Pipeline de traitement

```
Données brutes UNSW-NB15 (CSV, 45 colonnes)
        │
        ▼
  1. EDA                  → Statistiques, distribution des classes, types d'attaques
        │
        ▼
  2. Preprocessing        → Nettoyage, encodage des catégorielles, StandardScaler
        │
        ▼
  3. Feature Engineering  → Sélection et création de 20 features pertinentes
        │                   (bytes_ratio, log1p_dbytes, pkts_total, ct_state_ttl...)
        ▼
  4. Modélisation         → Isolation Forest entraîné sur X_train (sans labels)
        │                   QuantileTransformer appliqué avant l'entraînement
        ▼
  5. Évaluation           → Comparaison avec les vrais labels
        │                   F1=0.7489 | AUC=0.8075 | Precision=0.8896
        ▼
  6. Déploiement          → API FastAPI + Interface Streamlit + Docker
```

---

## 🤖 Modèle déployé — Isolation Forest

On a testé plusieurs modèles (DBSCAN, LOF, Autoencoder, ensembles). On déploie l'**Isolation Forest** car c'est le modèle le plus stable en inférence unitaire et le plus rapide.

**Principe :** une anomalie est un point rare et différent, donc plus facile à isoler dans un arbre de décision aléatoire. Moins de coupures sont nécessaires pour isoler un point → plus ce point est suspect.

**Pipeline complet :**

```
X_train (DataFrame, 20 features)
        │
        ▼
  QuantileTransformer    → distribution uniforme par feature (stabilise l'IF)
        │
        ▼
  IsolationForest.fit()  → contamination='auto', n_estimators=200, random_state=42
        │
        ▼
  decision_function(X)   → score brut (plus élevé = plus anormal sur UNSW-NB15)
        │
        ▼
  normalize_scores()     → min-max [0, 1]
        │
        ▼
  seuil percentile(60%)  → contamination=0.40 optimale (meilleur F1)
```

**Métriques sur le test set (82 332 connexions) :**

| Métrique | Valeur | Interprétation |
|---|---|---|
| **Precision** | 0.8896 | Quand le modèle dit "anomalie", il a raison 89% du temps |
| **Recall** | 0.6467 | Il détecte 65% des vraies attaques |
| **F1-Score** | 0.7489 | Équilibre precision/recall |
| **ROC-AUC** | 0.8075 | Bonne capacité de séparation globale |

---

## 📊 Dataset — UNSW-NB15

| Propriété | Valeur |
|---|---|
| Source | Université de New South Wales (Australie) |
| Train set | 175 341 connexions (68.1% anomalies) |
| Test set | 82 332 connexions (55.1% anomalies) |
| Features originales | 45 colonnes |
| Features retenues | 20 (après feature engineering) |
| Types d'attaques | Fuzzers, DoS, Exploits, Backdoors, Reconnaissance, etc. |
| Colonne `label` | 0 = Normal, 1 = Attaque — utilisée uniquement pour l'évaluation |

**Features les plus discriminantes :**

| Feature | Trafic normal | Attaque | Interprétation |
|---|---|---|---|
| `ct_state_ttl` | ≈ 0.0 | ≈ 1.0 | État TTL de la connexion |
| `rate` | ≈ -0.025 | ≈ 0.774 | Débit en paquets/seconde |
| `sttl` | ≈ -1.0 | ≈ 0.0 | TTL source |
| `sload` | ≈ -0.009 | ≈ 0.560 | Charge source |

---

## 🚀 Lancement du projet

### Option 1 — Docker (recommandé)

```bash
git clone https://github.com/votre-repo/anomaly-detection.git
cd anomaly-detection
docker-compose up --build
```

- Frontend : http://localhost:8501  
- Backend  : http://localhost:5000  
- Swagger  : http://localhost:5000/docs

### Option 2 — Lancement local

**Backend** (Terminal 1) :

```bash
cd backend
python -m venv backend_venv

# Windows
backend_venv\Scripts\activate
# Linux / macOS
source backend_venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

**Frontend** (Terminal 2) :

```bash
cd frontend
python -m venv frontend_venv

# Windows
frontend_venv\Scripts\activate
# Linux / macOS
source frontend_venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

### Réentraîner l'Isolation Forest (si nécessaire)

Si les fichiers `if_base.pkl` ou `qt_if.pkl` sont absents :

```bash
cd anomaly-detection
python retrain_if.py
```

Le script entraîne l'IF avec les paramètres optimaux et sauvegarde les artefacts dans `models_saved/`.

---

## 🌐 Routes API

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/health` | État du serveur et du modèle |
| `GET` | `/api/dataset/info` | Dimensions, taux d'anomalies, statistiques |
| `GET` | `/api/dataset/sample` | N premières lignes du test set |
| `GET` | `/api/dataset/distributions` | Distributions des features par classe |
| `GET` | `/api/metrics/evaluate` | Métriques de l'IF sur le test set complet |
| `GET` | `/api/metrics/viz` | Données graphiques (PCA, ROC, confusion, scores) |
| `GET` | `/api/predict/info` | Informations sur le modèle déployé |
| `POST` | `/api/predict/single` | Prédiction sur une connexion réseau |

La documentation complète est disponible sur `http://localhost:5000/docs` (Swagger UI).

---

## 🖥️ Pages du frontend

| Page | Description |
|---|---|
| **Accueil** | Vue d'ensemble, métriques clés, navigation rapide |
| **Dataset** | Distribution des classes, groupes de features, histogrammes, tableau d'exemples |
| **Performance** | Métriques du modèle, courbe ROC, matrice de confusion, projection PCA |
| **Prédiction** | Formulaire de saisie, presets de scénarios, jauge de score et seuil dynamique |

---

## 📦 Dépendances principales

**Backend :**

| Bibliothèque | Version | Rôle |
|---|---|---|
| `fastapi` | 0.115.0 | Framework API REST |
| `uvicorn` | 0.30.6 | Serveur ASGI |
| `pydantic` | 2.8.2 | Validation des paramètres |
| `scikit-learn` | 1.5.1 | Isolation Forest, QuantileTransformer, métriques |
| `torch` | 2.11.0+cpu | Autoencoder PyTorch (optionnel) |
| `pandas` | 2.2.2 | Manipulation des données |
| `numpy` | 1.26.4 | Calcul vectorisé |
| `joblib` | 1.4.2 | Sauvegarde et chargement des modèles |

**Frontend :**

| Bibliothèque | Version | Rôle |
|---|---|---|
| `streamlit` | 1.36.0 | Interface web interactive |
| `plotly` | 5.22.0 | Graphiques interactifs |
| `requests` | 2.32.3 | Appels HTTP vers le backend |
| `pandas` | 2.2.2 | Traitement des données reçues |

---

## 🐳 Docker

Le fichier `docker-compose.yml` orchestre deux containers :

```
backend   → port 5000  (FastAPI + Uvicorn)
frontend  → port 8501  (Streamlit)
```

Le frontend démarre uniquement quand le backend est prêt (`depends_on: condition: service_healthy`). Les données et les modèles sont montés en volumes partagés.

---

## 🧪 Exemples de prédiction

Les valeurs sont dans l'espace normalisé du dataset (après preprocessing notebook 03).

**Connexion normale :**
```json
{
  "sbytes": 0.08,  "dbytes": 0.094, "dpkts": 0.4,   "dur": 0.417,
  "rate": -0.025,  "sload": -0.01,  "dload": 0.178,  "sttl": 0.0,
  "dttl": 0.885,   "ct_state_ttl": 0.0
}
```

**Attaque détectée :**
```json
{
  "sbytes": -0.242, "dbytes": -0.149, "dpkts": -0.2,  "dur": -0.002,
  "rate": 0.863,    "sload": 0.56,    "dload": -0.052, "sttl": 0.0,
  "dttl": -0.115,   "ct_state_ttl": 1.0
}
```

---

## 📈 Métriques d'évaluation

- **Precision** — parmi les alertes levées, combien sont de vraies attaques ?
- **Recall** — parmi toutes les attaques présentes, combien ont été détectées ?
- **F1-Score** — équilibre entre Precision et Recall
- **ROC-AUC** — capacité globale du modèle à séparer normal et anormal

---

## 👥 Auteurs

Projet réalisé dans le cadre du module **Advanced Python** — Master en Informatique.

---

## 📄 Licence

Ce projet est open-source sous licence **MIT**.  
Le dataset UNSW-NB15 est mis à disposition par l'[Australian Centre for Cyber Security](https://research.unsw.edu.au/projects/unsw-nb15-dataset).
