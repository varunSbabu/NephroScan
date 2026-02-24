# NephroScan — CKD Detection System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue?logo=python" />
  <img src="https://img.shields.io/badge/Flask-2.3%2B-lightgrey?logo=flask" />
  <img src="https://img.shields.io/badge/ML%20Models-9%20Ensemble-brightgreen" />
  <img src="https://img.shields.io/badge/License-Apache%202.0-orange" />
</p>

## Overview

**NephroScan** is a clinical decision-support system for early detection of **Chronic Kidney Disease (CKD)**. It features a modern single-page web application (SPA) built with Flask, driven by an ensemble of **9 tuned machine learning models** and enhanced with **SHAP explainability** so clinicians can understand exactly why a prediction was made.

---

## Features

| Feature | Details |
|--------|---------|
| 🏥 **Clinical SPA** | Responsive dark-themed web interface for healthcare providers |
| 🔐 **Role-based Login** | Admin, Doctor, Nurse roles with profile avatars |
| 🔬 **24 Clinical Parameters** | Full input wizard covering numerical & categorical lab values |
| 🤖 **9 ML Models** | Ensemble of tuned classifiers with per-model confidence scores |
| 📊 **SHAP XAI Dashboard** | 5 interactive Plotly charts explaining each prediction |
| 🩺 **KDIGO eGFR Staging** | Automatic CKD stage (G1–G5) from serum creatinine + age |
| 🎯 **Risk-o-Meter** | Five-zone clinical confidence gauge |
| ⚖️ **Risk vs Protective Balance** | Donut chart of SHAP risk/protective weight |
| 📈 **Clinical Range Comparison** | Patient values vs normal reference ranges |

---

## Tech Stack

- **Backend:** Python 3.8+, Flask 2.3+
- **ML:** scikit-learn, XGBoost, CatBoost, SHAP
- **Frontend:** Vanilla JS, CSS3, Plotly.js (no frameworks)
- **Models:** 9 pre-trained `.pkl` / `.json` files in `/models`

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/varunSbabu/NephroScan.git
cd NephroScan
```

### 2. Create & activate a virtual environment

```bash
python -m venv ckdenv

# Windows
ckdenv\Scripts\activate

# macOS / Linux
source ckdenv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the application

```bash
cd Frontend
python app.py
```

### 5. Open in your browser

```
http://127.0.0.1:5000
```

---

## Application Workflow

```
Login → Patient Registration → Enter 24 Clinical Parameters
      → Ensemble Prediction → SHAP XAI Dashboard → KDIGO eGFR Stage
```

1. **Login** — Authenticate with your role (admin / doctor / nurse)
2. **Patient Info** — Enter patient name, age, sex
3. **Clinical Parameters** — Fill the 3-step input wizard
4. **Run Analysis** — All 9 models run simultaneously
5. **Results** — View verdict, per-model breakdown, and full SHAP analysis

---

## Clinical Parameters

### Numerical (11)
Age, Blood Pressure, Blood Glucose, Blood Urea, Serum Creatinine,
Sodium, Potassium, Haemoglobin, Packed Cell Volume, WBC Count, RBC Count

### Categorical (13)
Specific Gravity, Albumin, Sugar, RBC (urine), Pus Cells,
Pus Cell Clumps, Bacteria, Hypertension, Diabetes, CAD,
Appetite, Pedal Oedema, Anaemia

---

## Machine Learning Models

| # | Model | Type |
|---|-------|------|
| 1 | Logistic Regression | Linear |
| 2 | Support Vector Machine | Kernel |
| 3 | K-Nearest Neighbours | Instance |
| 4 | Naive Bayes | Probabilistic |
| 5 | Decision Tree | Tree |
| 6 | Random Forest | Ensemble |
| 7 | Gradient Boosting | Boosting |
| 8 | XGBoost | Boosting |
| 9 | CatBoost | Boosting |

Predictions are combined via **majority-vote ensemble** with individual confidence scores displayed for each model.

---

## Project Structure

```
NephroScan/
├── Frontend/
│   ├── app.py              # Flask API backend & routes
│   ├── static/
│   │   ├── index.html      # Single-page application
│   │   ├── style.css       # Dark clinical theme
│   │   └── app.js          # SPA logic, Plotly charts, SHAP
│   ├── images/             # Avatar & branding assets
│   └── Templates/          # Legacy HTML (not used by SPA)
├── models/                 # Pre-trained .pkl / .json model files
├── data/
│   └── raw.csv             # UCI CKD dataset
├── src/
│   ├── model.py            # Training pipeline
│   └── preprocessing.py   # Feature engineering
├── notebooks/              # EDA, feature selection, tuning, XAI
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container deployment
└── README.md
```

---

## SHAP XAI Dashboard

After every prediction, **5 interactive charts** are generated:

1. **Feature Impact** — Horizontal bar chart of top SHAP values per feature
2. **Cumulative SHAP** — Waterfall-style cumulative risk build-up
3. **Risk vs Protective Balance** — Donut chart of risk/protective SHAP weight
4. **Risk-o-Meter** — Semicircle gauge mapped to five clinical zones
5. **Clinical Normal Ranges** — Deviation bars vs reference range midpoints

---

## Disclaimer

> ⚠️ NephroScan is intended as a **clinical decision-support tool only**.  
> It does not replace professional medical diagnosis.  
> Always consult a qualified nephrologist or physician for clinical decisions.

---

## License

This project is licensed under the **Apache 2.0 License** — see [LICENSE](LICENSE) for details.
