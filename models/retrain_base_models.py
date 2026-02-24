"""
Retrain LR, Decision Tree, KNN, Naive Bayes with the notebook preprocessing pipeline
(le_dict  KNNImputer  StandardScaler) so they are compatible with the tuned models.

Run from the project root:
    python models/retrain_base_models.py
"""

import os, sys, pickle
import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import accuracy_score, roc_auc_score

MODELS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(MODELS_DIR, '..', 'data', 'raw.csv')
RANDOM_STATE = 42

# ── 1. Load data ──────────────────────────────────────────────────────────────
df = pd.read_csv(DATA_PATH)
df = df.drop(columns=['id'], errors='ignore')
for col in df.select_dtypes(include='object').columns:
    df[col] = df[col].str.strip()

df['classification'] = df['classification'].str.lower().str.replace(' ', '')
y   = (df['classification'] == 'ckd').astype(int).values
X_raw = df.drop(columns=['classification'])

FEATURE_NAMES    = X_raw.columns.tolist()   # 24 features
categorical_cols = X_raw.select_dtypes(include='object').columns.tolist()
print(f'Features ({len(FEATURE_NAMES)}): {FEATURE_NAMES}')
print(f'Categorical ({len(categorical_cols)}): {categorical_cols}')

# ── 2. LabelEncode ────────────────────────────────────────────────────────────
le_path = os.path.join(MODELS_DIR, 'le_dict.pkl')
if os.path.exists(le_path):
    with open(le_path, 'rb') as f:
        le_dict = pickle.load(f)
    print('Loaded existing le_dict.pkl')
else:
    le_dict = {}
    for col in categorical_cols:
        le = LabelEncoder()
        le.fit(X_raw[col].dropna())
        le_dict[col] = le
    with open(le_path, 'wb') as f:
        pickle.dump(le_dict, f)
    print('Created and saved le_dict.pkl')

X_enc = X_raw.copy()
for col in categorical_cols:
    le = le_dict[col]
    X_enc[col] = X_enc[col].apply(lambda v: le.transform([v])[0] if pd.notna(v) else np.nan)

# ── 3. KNN Impute ─────────────────────────────────────────────────────────────
imp_path = os.path.join(MODELS_DIR, 'knn_imputer.pkl')
if os.path.exists(imp_path):
    with open(imp_path, 'rb') as f:
        knn_imp = pickle.load(f)
    X_imp = knn_imp.transform(X_enc.values.astype(float))
    print('Loaded existing knn_imputer.pkl')
else:
    knn_imp = KNNImputer(n_neighbors=5)
    X_imp = knn_imp.fit_transform(X_enc.values.astype(float))
    with open(imp_path, 'wb') as f:
        pickle.dump(knn_imp, f)
    print('Created and saved knn_imputer.pkl')

# ── 4. Scale ──────────────────────────────────────────────────────────────────
scaler_path = os.path.join(MODELS_DIR, 'scaler.pkl')
if os.path.exists(scaler_path):
    with open(scaler_path, 'rb') as f:
        scaler = pickle.load(f)
    X_scaled = scaler.transform(X_imp)
    print('Loaded existing scaler.pkl')
else:
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imp)
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
    print('Created and saved scaler.pkl')

# ── 5. Train & save base models ───────────────────────────────────────────────
BASE_MODELS = {
    'lr_notebook':  LogisticRegression(max_iter=1000, C=1.0, random_state=RANDOM_STATE),
    'dt_notebook':  DecisionTreeClassifier(max_depth=8, random_state=RANDOM_STATE),
    'knn_notebook': KNeighborsClassifier(n_neighbors=7),
    'nb_notebook':  GaussianNB(),
}

print('\nTraining base models on notebook pipeline data...')
for name, clf in BASE_MODELS.items():
    clf.fit(X_scaled, y)
    preds = clf.predict(X_scaled)
    probs = clf.predict_proba(X_scaled)[:, 1]
    acc   = accuracy_score(y, preds)
    auc   = roc_auc_score(y, probs)
    path  = os.path.join(MODELS_DIR, f'{name}.pkl')
    with open(path, 'wb') as f:
        pickle.dump(clf, f)
    print(f'  {name:20s}  Acc={acc:.4f}  AUC={auc:.4f}  → saved {name}.pkl')

print('\n✓ All base models saved. Feature order saved for reference.')

# Save feature metadata for the app
meta = {
    'feature_names':    FEATURE_NAMES,
    'categorical_cols': categorical_cols,
}
with open(os.path.join(MODELS_DIR, 'feature_meta.pkl'), 'wb') as f:
    pickle.dump(meta, f)
print('✓ feature_meta.pkl saved')
