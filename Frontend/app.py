from flask import Flask, request, jsonify, send_from_directory, send_file, session
import pickle
import sys
import json as _json
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import logging
import os
import warnings
import xgboost as xgb
import shap
from functools import wraps

# Ensure both Frontend/ (for database.py) and src/ are importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(BASE_DIR, '..', 'src')
for _p in (BASE_DIR, os.path.abspath(_SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, 'static'),
    static_url_path='/static'
)
app.secret_key = os.environ.get('SECRET_KEY', 'nephroscan-secret-2026')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths to the pretrained models — resolved relative to this file's location
#   so the app works regardless of which directory it's launched from.
_MODELS_DIR = os.path.join(BASE_DIR, '..', 'models')

# Phase 5 tuned models (Optuna-optimised) + notebook-pipeline retrained base models
MODEL_PATHS = {
    "Logistic Regression": os.path.join(_MODELS_DIR, 'lr_notebook.pkl'),
    "SVM":                 os.path.join(_MODELS_DIR, 'svm_tuned.pkl'),
    "Decision Tree":       os.path.join(_MODELS_DIR, 'dt_notebook.pkl'),
    "Random Forest":       os.path.join(_MODELS_DIR, 'random_forest_tuned.pkl'),
    "Gradient Boosting":   os.path.join(_MODELS_DIR, 'grad_boosting_tuned.pkl'),
    "XGBoost":             os.path.join(_MODELS_DIR, 'xgboost_tuned.pkl'),
    "CatBoost":            os.path.join(_MODELS_DIR, 'catboost_tuned.pkl'),
    "K-Nearest Neighbors": os.path.join(_MODELS_DIR, 'knn_notebook.pkl'),
    "Naive Bayes":         os.path.join(_MODELS_DIR, 'nb_notebook.pkl'),
}


# Initialize dictionary to store models (single shared pipeline now)
models = {}

def load_models():
    """Load all models from files (all use the shared notebook pipeline)."""
    try:
        for model_name, path in MODEL_PATHS.items():
            if os.path.exists(path):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=UserWarning)
                    with open(path, 'rb') as file:
                        models[model_name] = pickle.load(file)
                logger.info(f"Loaded {model_name} from {os.path.basename(path)}")
            else:
                logger.warning(f"Model file not found: {path}")
    except Exception as e:
        logger.error(f"Error loading models: {str(e)}")
        raise
    # Load the shared notebook preprocessing pipeline
    _load_notebook_pipeline()

# All 24 feature names in the exact notebook CSV column order
ALL_FEATURES = [
    'age', 'bp', 'sg', 'al', 'su', 'rbc', 'pc', 'pcc', 'ba', 'bgr',
    'bu', 'sc', 'sod', 'pot', 'hemo', 'pcv', 'wc', 'rc', 'htn',
    'dm', 'cad', 'appet', 'pe', 'ane'
]
# Categorical features (encoded by LabelEncoder during training)
CATEGORICAL_FEATURES = ['rbc', 'pc', 'pcc', 'ba', 'pcv', 'wc', 'rc',
                         'htn', 'dm', 'cad', 'appet', 'pe', 'ane']
NUMERICAL_FEATURES   = [f for f in ALL_FEATURES if f not in CATEGORICAL_FEATURES]

# Shared notebook preprocessing pipeline — loaded once at startup
_le_dict     = {}   # {col: LabelEncoder}
_knn_imputer = None
_nb_scaler   = None

def _load_notebook_pipeline():
    """Load le_dict, knn_imputer, and scaler from models/."""
    global _le_dict, _knn_imputer, _nb_scaler

    le_path  = os.path.join(_MODELS_DIR, 'le_dict.pkl')
    imp_path = os.path.join(_MODELS_DIR, 'knn_imputer.pkl')
    sc_path  = os.path.join(_MODELS_DIR, 'scaler.pkl')

    if os.path.exists(le_path):
        with open(le_path, 'rb') as f:
            _le_dict = pickle.load(f)
        logger.info(f"le_dict loaded ({len(_le_dict)} categorical encoders)")
    else:
        logger.warning("le_dict.pkl not found — categorical encoding will be numeric fallback")

    if os.path.exists(imp_path):
        with open(imp_path, 'rb') as f:
            _knn_imputer = pickle.load(f)
        logger.info("knn_imputer loaded (24 features)")
    else:
        logger.warning("knn_imputer.pkl not found")

    if os.path.exists(sc_path):
        with open(sc_path, 'rb') as f:
            _nb_scaler = pickle.load(f)
        logger.info("scaler loaded (24 features)")
    else:
        logger.warning("scaler.pkl not found")

def preprocess_features(form_data):
    """
    Transform raw form/JSON data into the 24-feature scaled vector the models expect.

    Pipeline (matches notebook training exactly):
      1. Build raw row in CSV column order (24 features)
      2. Apply LabelEncoder for each categorical column via _le_dict
      3. Apply KNNImputer for any missing values
      4. Apply StandardScaler
    """
    try:
        raw_row = []
        for feat in ALL_FEATURES:
            value = form_data.get(feat)

            if feat in CATEGORICAL_FEATURES and feat in _le_dict:
                # ── Categorical: use LabelEncoder fitted on training data ──
                v = str(value).strip().lower() if value is not None else ''
                le = _le_dict[feat]
                # Case-insensitive match against known classes
                classes_lower = {c.lower(): c for c in le.classes_}
                canonical = classes_lower.get(v)
                if canonical is not None:
                    encoded = int(le.transform([canonical])[0])
                else:
                    # Fallback: nearest class by string distance
                    # Common aliases
                    alias_map = {
                        'yes': ['yes', 'y', '1', 'true'],
                        'no':  ['no',  'n', '0', 'false'],
                        'normal': ['normal', 'norm'],
                        'abnormal': ['abnormal', 'abn'],
                        'present': ['present', 'yes', '1'],
                        'notpresent': ['notpresent', 'not present', 'no', '0'],
                        'good': ['good', 'yes'],
                        'poor': ['poor', 'no'],
                    }
                    found = False
                    for cls, aliases in alias_map.items():
                        if v in aliases and cls in classes_lower:
                            encoded = int(le.transform([classes_lower[cls]])[0])
                            found = True
                            break
                    if not found:
                        encoded = 0  # default to first class
                raw_row.append(float(encoded))

            else:
                # ── Numerical: use float directly, NaN for missing ──
                if value is None or str(value).strip() == '':
                    raw_row.append(np.nan)
                else:
                    try:
                        raw_row.append(float(value))
                    except (ValueError, TypeError):
                        raw_row.append(np.nan)

        X = np.array(raw_row).reshape(1, -1)

        # Apply KNN imputation for any NaN values
        if _knn_imputer is not None and np.isnan(X).any():
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                X = _knn_imputer.transform(X)

        # Apply StandardScaler
        if _nb_scaler is not None:
            X = _nb_scaler.transform(X)

        return X
    except Exception as e:
        logger.error(f"Error in preprocessing features: {str(e)}")
        raise

@app.route('/api/predict', methods=['POST'])
def api_predict():
    """API endpoint for predictions"""
    try:
        features = preprocess_features(request.json)
        predictions = {}
        
        for model_name, model in models.items():
            # All models share the same notebook-pipeline scaled features
            prediction = None
            confidence = None

            try:
                prediction = int(model.predict(features)[0])
                proba = model.predict_proba(features)[0]
                confidence = round(float(max(proba)) * 100, 2)
            except Exception as exc:
                logger.warning(f"{model_name} predict failed: {exc}")
                prediction = 0
                confidence = None

            predictions[model_name] = {
                'prediction': int(prediction),
                'confidence': confidence,
                'label': "CKD" if prediction == 1 else "Not CKD"
            }

        # ── Ensemble consensus ────────────────────────────────────────────
        _NAME_MAP = {
            "Logistic Regression": "logistic_regression",
            "SVM":                 "svm",
            "Decision Tree":       "decision_tree",
            "Random Forest":       "random_forest",
            "Gradient Boosting":   "gradient_boosting",
            "XGBoost":             "xgboost",
            "CatBoost":            "catboost",
            "K-Nearest Neighbors": "knn",
            "Naive Bayes":         "naive_bayes",
        }
        ckd_votes = sum(1 for p in predictions.values() if p['prediction'] == 1)
        total     = len(predictions)
        ensemble_ckd = ckd_votes > total / 2
        confs = [p['confidence'] for p in predictions.values() if p['confidence'] is not None]
        avg_conf = sum(confs) / len(confs) if confs else 50.0

        # JS-ready model_results: snake_case keys, 'ckd'/'no_ckd', confidence 0-1
        model_results = {
            _NAME_MAP.get(name, name.lower().replace(' ', '_')): {
                'prediction': 'ckd' if p['prediction'] == 1 else 'no_ckd',
                'confidence': round((p['confidence'] or 0) / 100, 4),
            }
            for name, p in predictions.items()
        }

        return jsonify({
            'status':             'success',
            'predictions':        predictions,
            'model_results':      model_results,
            'ensemble_result':    'ckd' if ensemble_ckd else 'no_ckd',
            'ensemble_confidence': round(avg_conf / 100, 4),
            'models_agree':       ckd_votes if ensemble_ckd else (total - ckd_votes),
        })
        
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/explain', methods=['POST'])
def api_explain():
    """Return SHAP feature-importance values for each model."""
    try:
        features = preprocess_features(request.json)
        explanations = {}

        # Models that support TreeExplainer (fast, exact)
        TREE_MODELS   = {"Random Forest", "Gradient Boosting", "Decision Tree",
                         "CatBoost", "XGBoost"}
        # Models that support LinearExplainer
        LINEAR_MODELS = {"Logistic Regression"}
        # KernelExplainer for the rest
        KERNEL_MODELS = {"SVM", "K-Nearest Neighbors", "Naive Bayes"}

        for model_name, model in models.items():
            try:
                X = features  # all models share the same 24-feature scaled vector

                if model_name in TREE_MODELS:
                    explainer = shap.TreeExplainer(model)
                    sv = explainer.shap_values(X)

                elif model_name in LINEAR_MODELS:
                    explainer = shap.LinearExplainer(model, X)
                    sv = explainer.shap_values(X)

                elif model_name in KERNEL_MODELS:
                    background = np.zeros((1, X.shape[1]))
                    def predict_fn(x):
                        try:
                            return model.predict_proba(x)
                        except Exception:
                            preds = model.predict(x)
                            return np.column_stack([1 - preds, preds])
                    explainer = shap.KernelExplainer(predict_fn, background)
                    sv = explainer.shap_values(X, nsamples=100)

                else:
                    continue

                # ── Normalise SHAP output to flat 1-D array (n_features,) ──
                sv_arr = np.array(sv)
                if isinstance(sv, list):
                    vals = np.array(sv[1]).flatten()
                elif sv_arr.ndim == 3:
                    vals = sv_arr[0, :, 1]
                elif sv_arr.ndim == 2:
                    vals = sv_arr[0]
                else:
                    vals = sv_arr.flatten()

                vals = np.array(vals).flatten()[:len(ALL_FEATURES)]

                shap_dict = {
                    ALL_FEATURES[i]: round(float(vals[i]), 5)
                    for i in range(len(vals))
                }
                # Sort by absolute magnitude descending
                explanations[model_name] = dict(
                    sorted(shap_dict.items(), key=lambda x: abs(x[1]), reverse=True)
                )
            except Exception as exc:
                logger.warning(f"SHAP failed for {model_name}: {exc}")
                explanations[model_name] = {"error": str(exc)}

        return jsonify({"status": "success", "explanations": explanations})

    except Exception as e:
        logger.error(f"Explain API error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.errorhandler(404)
def not_found_error(error):
    # Return JSON only for /api/ requests; serve SPA for all other paths
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    idx = os.path.join(BASE_DIR, 'static', 'index.html')
    if os.path.exists(idx):
        return send_file(idx)
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Serve images from the local images directory without changing folder structure
@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'images'), filename)

# ── SPA entry point ──────────────────────────────────────────────────────────
@app.route('/')
def spa_root():
    idx = os.path.join(BASE_DIR, 'static', 'index.html')
    logger.info(f"Serving SPA from: {idx}  exists={os.path.exists(idx)}")
    return send_file(idx)

# ── Auth ─────────────────────────────────────────────────────────────────────
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True) or {}
    from database import authenticate_user
    user = authenticate_user(data.get('username', ''), data.get('password', ''))
    if user:
        session['user'] = user
        safe = {k: user[k] for k in ('username', 'full_name', 'role', 'email') if k in user}
        return jsonify({'status': 'success', 'user': safe})
    return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/api/auth/me')
def api_me():
    if 'user' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    u = session['user']
    safe = {k: u[k] for k in ('username', 'full_name', 'role', 'email') if k in u}
    return jsonify({'status': 'success', 'user': safe})

# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route('/api/dashboard/stats')
def api_dashboard_stats():
    if 'user' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    from database import get_summary_stats
    return jsonify({'status': 'success', 'stats': get_summary_stats()})

# ── Patients ──────────────────────────────────────────────────────────────────
@app.route('/api/patients', methods=['GET', 'POST'])
def api_patients():
    if 'user' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    from database import get_all_patients, save_patient
    if request.method == 'GET':
        return jsonify({'status': 'success', 'patients': get_all_patients()})
    data = request.get_json(force=True) or {}
    ok, msg = save_patient(data, session['user']['username'])
    return jsonify({'status': 'success' if ok else 'error', 'message': msg})

@app.route('/api/patients/<patient_id>', methods=['GET', 'PUT', 'DELETE'])
def api_patient(patient_id):
    if 'user' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    from database import get_patient, update_patient, delete_patient
    if request.method == 'GET':
        p = get_patient(patient_id)
        if p:
            return jsonify({'status': 'success', 'patient': p})
        return jsonify({'status': 'error', 'message': 'Patient not found'}), 404
    if request.method == 'PUT':
        ok, msg = update_patient(patient_id, request.get_json(force=True) or {})
        return jsonify({'status': 'success' if ok else 'error', 'message': msg})
    ok, msg = delete_patient(patient_id)
    return jsonify({'status': 'success' if ok else 'error', 'message': msg})

@app.route('/api/patients/<patient_id>/history')
def api_patient_history(patient_id):
    if 'user' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    from database import get_patient_predictions
    return jsonify({'status': 'success', 'history': get_patient_predictions(patient_id)})

# ── Users (admin) ─────────────────────────────────────────────────────────────
def _require_admin():
    if session.get('user', {}).get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Admin only'}), 403
    return None

@app.route('/api/users', methods=['GET', 'POST'])
def api_users():
    err = _require_admin()
    if err:
        return err
    from database import get_all_users, add_user
    if request.method == 'GET':
        return jsonify({'status': 'success', 'users': get_all_users()})
    d = request.get_json(force=True) or {}
    ok, msg = add_user(d.get('username', ''), d.get('password', ''), d.get('full_name', ''), d.get('role', 'doctor'), d.get('email', ''))
    return jsonify({'status': 'success' if ok else 'error', 'message': msg})

@app.route('/api/users/<username>', methods=['PUT', 'DELETE'])
def api_user(username):
    err = _require_admin()
    if err:
        return err
    from database import update_user, delete_user
    if request.method == 'PUT':
        d = request.get_json(force=True) or {}
        ok, msg = update_user(username, d.get('full_name', ''), d.get('role', 'doctor'), d.get('email', ''))
        return jsonify({'status': 'success' if ok else 'error', 'message': msg})
    ok, msg = delete_user(username)
    return jsonify({'status': 'success' if ok else 'error', 'message': msg})

# ── Account ───────────────────────────────────────────────────────────────────
@app.route('/api/account/change-password', methods=['POST'])
def api_change_password():
    if 'user' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    from database import change_password
    d = request.get_json(force=True) or {}
    ok, msg = change_password(session['user']['username'], d.get('old_password', ''), d.get('new_password', ''))
    return jsonify({'status': 'success' if ok else 'error', 'message': msg})

# Auto-load models when imported by a production server (e.g. gunicorn).
if not models:
    try:
        load_models()
    except Exception as _e:
        logger.error(f"Auto load_models() failed: {_e}")

if __name__ == '__main__':
    load_models()
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0' if os.environ.get('RENDER') else '127.0.0.1'
    app.run(host=host, port=port, debug=False, use_reloader=False)






