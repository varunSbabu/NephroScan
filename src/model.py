import os
import pickle
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from xgboost import XGBClassifier
from catboost import CatBoostClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from preprocessing import preprocess_data

# ── Optuna-tuned hyperparameters (Phase 5, 100 trials, 10-fold AUC objective) ──
# Source: notebooks/figures/table_tuning_summary.csv
_RF_PARAMS = {
    'n_estimators': 500, 'max_depth': 13, 'min_samples_split': 6,
    'min_samples_leaf': 4, 'max_features': 'log2', 'bootstrap': False,
}
_XGB_PARAMS = {
    'n_estimators': 500, 'max_depth': 12, 'learning_rate': 0.06459666959151401,
    'subsample': 0.5780759504758056, 'colsample_bytree': 0.4164340115579366,
    'reg_alpha': 7.091384614514681e-6, 'reg_lambda': 4.542000594752323e-7,
    'min_child_weight': 1, 'gamma': 0.14116092632599253,
    'eval_metric': 'logloss', 'verbosity': 0,
}
_CAT_PARAMS = {
    'iterations': 450, 'depth': 6, 'learning_rate': 0.1609622008593327,
    'l2_leaf_reg': 8.633510315081903, 'bagging_temperature': 0.389815560236714,
    'border_count': 107, 'verbose': 0,
}
_GB_PARAMS = {
    'n_estimators': 400, 'max_depth': 2, 'learning_rate': 0.279566426909896,
    'subsample': 0.5033903904854609, 'min_samples_leaf': 20, 'max_features': None,
}
_SVM_PARAMS = {
    'kernel': 'rbf', 'C': 233.86439256208715, 'gamma': 0.038672288491177424,
    'probability': True,
}

RANDOM_STATE = 42


def define_and_train_models(X, y):
    """
    Define and train all 9 models using Optuna-tuned hyperparameters where available.

    Parameters:
    X (array-like): Feature matrix (already imputed and scaled).
    y (array-like): Target vector.

    Returns:
    dict: A dictionary of trained model names and their instances.
    """
    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
        "SVM":                 SVC(**_SVM_PARAMS, random_state=RANDOM_STATE),
        "Decision Tree":       DecisionTreeClassifier(random_state=RANDOM_STATE),
        "Random Forest":       RandomForestClassifier(**_RF_PARAMS,
                                   random_state=RANDOM_STATE, n_jobs=-1),
        "Gradient Boosting":   GradientBoostingClassifier(**_GB_PARAMS,
                                   random_state=RANDOM_STATE),
        "XGBoost":             XGBClassifier(**_XGB_PARAMS,
                                   random_state=RANDOM_STATE, n_jobs=-1),
        "CatBoost":            CatBoostClassifier(**_CAT_PARAMS,
                                   random_state=RANDOM_STATE),
        "K-Nearest Neighbors": KNeighborsClassifier(n_neighbors=5),
        "Naive Bayes":         GaussianNB(),
    }

    trained_models = {}
    for name, model in models.items():
        print(f"Training {name}...")
        model.fit(X, y)
        trained_models[name] = model

    print("All models have been trained successfully.\n")
    return trained_models


def save_models(trained_models, models_dir="../models/"):
    """
    Save trained models to the specified directory using deployment filenames
    that match Frontend/app.py → MODEL_PATHS.

    Parameters:
    trained_models (dict): Dictionary of trained model names and instances.
    models_dir (str): Directory to save the models.

    Returns:
    None
    """
    # Deployment filename map — must match Frontend/app.py MODEL_PATHS
    DEPLOYMENT_NAMES = {
        "Logistic Regression": "lr_notebook.pkl",
        "SVM":                 "svm_tuned.pkl",
        "Decision Tree":       "dt_notebook.pkl",
        "Random Forest":       "random_forest_tuned.pkl",
        "Gradient Boosting":   "grad_boosting_tuned.pkl",
        "XGBoost":             "xgboost_tuned.pkl",
        "CatBoost":            "catboost_tuned.pkl",
        "K-Nearest Neighbors": "knn_notebook.pkl",
        "Naive Bayes":         "nb_notebook.pkl",
    }

    os.makedirs(models_dir, exist_ok=True)

    for name, model in trained_models.items():
        fname = DEPLOYMENT_NAMES.get(name, f"{name.replace(' ', '_')}.pkl")
        model_path = os.path.join(models_dir, fname)
        with open(model_path, 'wb') as model_file:
            pickle.dump(model, model_file)
        size_kb = os.path.getsize(model_path) / 1024
        print(f"  ✓ Saved {name:<22} → {fname:<35} ({size_kb:.1f} KB)")

    print("\nAll models have been saved successfully.")


