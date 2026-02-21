from flask import Flask, request, jsonify, send_from_directory
import pickle
import sys
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import logging
import os
import warnings
import xgboost as xgb
import shap

# Add src/ to path so pickled CustomCategoricalEncoder can be unpickled
_SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC_DIR))

# Ensure Flask finds case-sensitive template/static directories on Linux
BASE_DIR = os.path.dirname(__file__)
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'Templates'),
    static_folder=os.path.join(BASE_DIR, 'Static')
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths to the pretrained models — resolved relative to this file's location
#   so the app works regardless of which directory it's launched from.
_MODELS_DIR = os.path.join(BASE_DIR, '..', 'models')

MODEL_PATHS = {
    "Logistic Regression": os.path.join(_MODELS_DIR, 'Logistic_Regression.pkl'),
    "SVM":                 os.path.join(_MODELS_DIR, 'SVM.pkl'),
    "Decision Tree":       os.path.join(_MODELS_DIR, 'Decision_Tree.pkl'),
    "Random Forest":       os.path.join(_MODELS_DIR, 'Random_Forest.pkl'),
    "Gradient Boosting":   os.path.join(_MODELS_DIR, 'Gradient_Boosting.pkl'),
    "XGBoost":             os.path.join(_MODELS_DIR, 'XGBoost.pkl'),
    "CatBoost":            os.path.join(_MODELS_DIR, 'CatBoost.pkl'),
    "K-Nearest Neighbors": os.path.join(_MODELS_DIR, 'K-Nearest_Neighbors.pkl'),
    "Naive Bayes":         os.path.join(_MODELS_DIR, 'Naive_Bayes.pkl'),
}


# Initialize dictionaries to store models and scalers
models = {}
scalers = {}

def load_models():
    """Load all models and scalers from files"""
    try:
        for model_name, path in MODEL_PATHS.items():
            if os.path.exists(path):
                if model_name == "XGBoost":
                    # Prefer a native saved model to avoid warnings
                    native_path = path.rsplit('.', 1)[0] + '.json'
                    if os.path.exists(native_path):
                        booster = xgb.Booster()
                        booster.load_model(native_path)
                        models[model_name] = booster
                    else:
                        # One-time conversion: load pickle (suppress warning), export to native, then keep booster in memory
                        try:
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore", category=UserWarning)
                                with open(path, 'rb') as file:
                                    loaded = pickle.load(file)
                            # Get Booster regardless of wrapper type
                            if isinstance(loaded, xgb.Booster):
                                booster = loaded
                            else:
                                booster = loaded.get_booster()
                            # Save native format for future runs
                            booster.save_model(native_path)
                            models[model_name] = booster
                        except Exception:
                            # As a last resort, attempt to load as Booster path (unlikely for .pkl)
                            booster = xgb.Booster()
                            booster.load_model(path)
                            models[model_name] = booster
                else:
                    with open(path, 'rb') as file:
                        models[model_name] = pickle.load(file)
                
                # Load corresponding scaler if it exists
                scaler_path = os.path.join(_MODELS_DIR, f'scaler_{model_name.lower().replace(" ", "_")}.pkl')
                if os.path.exists(scaler_path):
                    with open(scaler_path, 'rb') as file:
                        scalers[model_name] = pickle.load(file)
                
                logger.info(f"Successfully loaded {model_name}")
            else:
                logger.warning(f"Model file not found: {path}")
    except Exception as e:
        logger.error(f"Error loading models: {str(e)}")
        raise
    # Load the fitted preprocessor (needed for correct inference)
    _load_preprocessor()

# All raw feature names (CSV column order — used only to build the input DataFrame)
ALL_FEATURES = [
    'age', 'bp', 'sg', 'al', 'su', 'rbc', 'pc', 'pcc', 'ba', 'bgr',
    'bu', 'sc', 'sod', 'pot', 'hemo', 'pcv', 'wc', 'rc', 'htn',
    'dm', 'cad', 'appet', 'pe', 'ane'
]
# Numerical features used by ColumnTransformer (for SHAP labelling)
NUMERICAL_FEATURES   = ['age', 'bp', 'sg', 'al', 'su', 'bgr', 'bu', 'sc',
                         'sod', 'pot', 'hemo']
CATEGORICAL_FEATURES = ['rbc', 'pc', 'pcc', 'ba', 'pcv', 'wc', 'rc',
                         'htn', 'dm', 'cad', 'appet', 'pe', 'ane']

# Fitted preprocessor (ColumnTransformer) — loaded once at startup
_preprocessor      = None
_preprocessor_meta = None
_category_maps     = {}   # {col: {str_value: int_code}} for pcv/wc/rc

def _load_preprocessor():
    global _preprocessor, _preprocessor_meta, _category_maps
    prep_path = os.path.join(_MODELS_DIR, 'preprocessor.pkl')
    if os.path.exists(prep_path):
        with open(prep_path, 'rb') as f:
            obj = pickle.load(f)
        _preprocessor      = obj['preprocessor']
        _preprocessor_meta = obj
        logger.info("Preprocessor loaded from models/preprocessor.pkl")
    else:
        logger.warning("preprocessor.pkl not found — falling back to manual encoding")

    cat_map_path = os.path.join(_MODELS_DIR, 'category_maps.pkl')
    if os.path.exists(cat_map_path):
        with open(cat_map_path, 'rb') as f:
            _category_maps = pickle.load(f)
        logger.info("Category maps loaded for pcv/wc/rc")

def preprocess_features(form_data):
    """
    Transform raw form/JSON data into the feature vector the models expect.

    Column order produced by the training ColumnTransformer:
      Numerical (11): age, bp, sg, al, su, bgr, bu, sc, sod, pot, hemo
      Categorical (13): rbc, pc, pcc, ba, pcv, wc, rc, htn, dm, cad, appet, pe, ane

    pcv/wc/rc were read as object dtype during training and encoded with
    astype('category').cat.codes — their codes depended on ALL training values.
    We use the saved _category_maps to reproduce those exact codes.
    """
    try:
        # ── 1. Numerical features ────────────────────────────────────────────
        num_vals = []
        for feat in NUMERICAL_FEATURES:
            value = form_data.get(feat)
            if value is None:
                raise ValueError(f"Missing feature: {feat}")
            num_vals.append(float(value))

        # ── 2. Categorical features ──────────────────────────────────────────
        cat_vals = []
        for feat in CATEGORICAL_FEATURES:
            value = form_data.get(feat)
            if value is None:
                raise ValueError(f"Missing feature: {feat}")
            v = str(value).strip()

            if feat in ('pcv', 'wc', 'rc'):
                # These were category-coded from string values during training
                code = _category_maps.get(feat, {}).get(v)
                if code is None:
                    # Try without decimal for floats like '5.0' vs '5'
                    alt = v.split('.')[0] if '.' in v else v + '.0'
                    code = _category_maps.get(feat, {}).get(alt, 0)
                cat_vals.append(float(code))
            elif feat in ('rbc', 'pc'):
                cat_vals.append(1.0 if v.lower() == 'normal' else 0.0)
            elif feat in ('pcc', 'ba'):
                cat_vals.append(1.0 if v.lower() == 'present' else 0.0)
            elif feat == 'appet':
                cat_vals.append(1.0 if v.lower() == 'good' else 0.0)
            else:  # htn, dm, cad, pe, ane
                cat_vals.append(1.0 if v.lower() == 'yes' else 0.0)

        return np.array(num_vals + cat_vals).reshape(1, -1)
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
            if model_name in scalers:
                scaled_features = scalers[model_name].transform(features)
            else:
                scaled_features = features

            prediction = None
            confidence = None

            if model_name == "XGBoost":
                try:
                    if isinstance(model, xgb.Booster):
                        dmatrix = xgb.DMatrix(scaled_features)
                        prob = float(model.predict(dmatrix)[0])
                        prediction = int(prob >= 0.5)
                        confidence = round(max(prob, 1 - prob) * 100, 2)
                    else:
                        prediction = int(model.predict(scaled_features)[0])
                        try:
                            proba = model.predict_proba(scaled_features)[0]
                            confidence = round(float(max(proba)) * 100, 2)
                        except Exception:
                            confidence = None
                except Exception:
                    prediction = int(model.predict(scaled_features)[0])
                    try:
                        proba = model.predict_proba(scaled_features)[0]
                        confidence = round(float(max(proba)) * 100, 2)
                    except Exception:
                        confidence = None
            else:
                prediction = int(model.predict(scaled_features)[0])
                try:
                    proba = model.predict_proba(scaled_features)[0]
                    confidence = round(float(max(proba)) * 100, 2)
                except Exception:
                    confidence = None

            predictions[model_name] = {
                'prediction': int(prediction),
                'confidence': confidence,
                'label': "CKD" if prediction == 1 else "Not CKD"
            }
        
        return jsonify({
            'status': 'success',
            'predictions': predictions
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
        TREE_MODELS  = {"Random Forest", "Gradient Boosting", "Decision Tree", "CatBoost"}
        # Models that support LinearExplainer
        LINEAR_MODELS = {"Logistic Regression"}
        # Universal KernelExplainer for remainder (slower)
        KERNEL_MODELS = {"SVM", "K-Nearest Neighbors", "Naive Bayes"}

        for model_name, model in models.items():
            try:
                X = scalers[model_name].transform(features) if model_name in scalers else features

                if model_name in TREE_MODELS:
                    explainer = shap.TreeExplainer(model)
                    sv = explainer.shap_values(X)

                elif model_name == "XGBoost":
                    explainer = shap.TreeExplainer(model)
                    sv = explainer.shap_values(X)

                elif model_name in LINEAR_MODELS:
                    explainer = shap.LinearExplainer(model, X)
                    sv = explainer.shap_values(X)

                elif model_name in KERNEL_MODELS:
                    background = np.zeros((1, features.shape[1]))
                    if model_name in scalers:
                        background = scalers[model_name].transform(background)
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

                # ── Normalise SHAP output to a flat 1-D array (n_features,) ──
                # SHAP returns different shapes depending on version/model:
                #   list of 2 arrays (n_samples, n_features)  → binary, take class-1
                #   ndarray (n_samples, n_features, 2)        → newer SHAP, take [...,1]
                #   ndarray (n_samples, n_features)           → single output
                sv_arr = np.array(sv)
                if isinstance(sv, list):
                    # list[0]=class0, list[1]=class1  — each shape (n_samples, n_features)
                    vals = np.array(sv[1]).flatten()
                elif sv_arr.ndim == 3:
                    # shape (n_samples, n_features, n_classes) — take class-1
                    vals = sv_arr[0, :, 1]
                elif sv_arr.ndim == 2:
                    # shape (n_samples, n_features)
                    vals = sv_arr[0]
                else:
                    vals = sv_arr.flatten()

                # Safety: flatten to 1-D and trim/pad to expected feature count
                vals = np.array(vals).flatten()
                n_feat = len(NUMERICAL_FEATURES) + len(CATEGORICAL_FEATURES)
                vals = vals[:n_feat]

                shap_dict = {
                    (NUMERICAL_FEATURES + CATEGORICAL_FEATURES)[i]: round(float(vals[i]), 5)
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
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500

# Serve images from the local images directory without changing folder structure
@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'images'), filename)

# Auto-load models when imported by a production server (e.g. gunicorn).
# The `if not models` guard prevents double-loading in local dev where
# _start_flask_backend() already calls load_models() explicitly.
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






