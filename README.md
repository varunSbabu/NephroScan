# CKD Detection System

## Overview
The **Chronic Kidney Disease (CKD) Detection System** is a machine learning-based project that predicts CKD using medical data. This system now features a **professional clinical-themed Streamlit frontend** for healthcare providers, integrated with a Flask API backend.

## Features
- 🏥 **Professional Clinical Interface** - Modern healthcare-themed UI
- 🔐 **Secure Login System** - Authentication for healthcare providers
- 📋 **Patient Management** - Comprehensive patient registration
- 🔬 **24 Clinical Parameters** - Complete medical data input
- 🤖 **9 ML Models** - Ensemble prediction for accuracy
- 📊 **Detailed Results** - Confidence scores and recommendations

## Installation and Setup
Follow these steps to install and run the CKD Detection System.

### Requirements
- **Operating System:** Windows (Linux is not supported)
- **Python:** Python 3.8 or higher

### 1. Clone the Repository
First, clone the repository to your local machine:

```bash
git clone https://github.com/Salahuddin-quadri/CKD.git
cd CKD
```

### 2. Set Up a Virtual Environment
It is recommended to create a virtual environment to manage dependencies:

```bash
python -m venv ckdenv
```

Activate the virtual environment:

```bash
ckdenv\Scripts\activate
```

### 3. Install Dependencies
Use `pip` to install the required packages:

```bash
pip install -r requirements.txt
```

### 4. Run the Application

#### **Option A: Quick Start (Recommended)**
Use the provided startup script:

```bash
run_app.bat
```

Or using Python:
```bash
python run_app.py
```

#### **Option B: Manual Startup**

**Step 1:** Start the Flask API server:
```bash
cd Frontend
python app.py
```

**Step 2:** In a new terminal, start Streamlit:
```bash
cd Frontend
streamlit run streamlit_app.py
```

### 5. Access the Application

- **Streamlit UI:** http://127.0.0.1:8501
- **Flask API:** http://127.0.0.1:5000

### Login Credentials (Demo)
| Username | Password |
|----------|----------|
| admin | admin123 |
| doctor | doctor123 |
| nurse | nurse123 |

## Application Workflow

1. **Login** - Authenticate as a healthcare provider
2. **Patient Registration** - Enter patient demographics
3. **Medical Parameters** - Input clinical test results
4. **Prediction Results** - View CKD risk assessment

## Clinical Parameters

### Numerical Parameters
- Age, Blood Pressure, Blood Glucose, Blood Urea
- Serum Creatinine, Sodium, Potassium, Hemoglobin
- Packed Cell Volume, WBC Count, RBC Count

### Categorical Parameters
- Specific Gravity, Albumin, Sugar
- RBC (urine), Pus Cells, Pus Cell Clumps, Bacteria
- Hypertension, Diabetes, CAD, Appetite
- Pedal Edema, Anemia

## Machine Learning Models

The system uses an ensemble of 9 models:
- Logistic Regression
- Support Vector Machine (SVM)
- Decision Tree
- Random Forest
- Gradient Boosting
- XGBoost
- CatBoost
- K-Nearest Neighbors
- Naive Bayes

## Project Structure

```
CKD/
├── Frontend/
│   ├── app.py              # Flask API backend
│   ├── streamlit_app.py    # Streamlit frontend (NEW)
│   ├── Static/             # CSS files
│   ├── Templates/          # HTML templates (legacy)
│   └── images/             # Image assets
├── models/                 # Trained ML models
├── data/                   # Dataset
├── src/                    # Source code
├── notebooks/              # Jupyter notebooks
├── run_app.bat            # Windows startup script
├── run_app.py             # Python startup script
└── requirements.txt       # Dependencies
```

## Additional Notes
- Ensure that the necessary datasets are available in the `data/` directory.
- If the project requires pre-trained models, check the `models/` directory or train new models as needed.
- Modify configuration settings if required before running the application.

## Disclaimer
⚠️ This system is intended for clinical decision support only. Always consult qualified medical professionals for diagnosis and treatment decisions.

## Contributing
Contributions are welcome! Feel free to open an issue or submit a pull request.

## License

This project is licensed under the Apache-2.0 License.


