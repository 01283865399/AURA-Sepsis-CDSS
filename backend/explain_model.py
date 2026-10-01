import pandas as pd
import joblib
import shap
import matplotlib.pyplot as plt
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = Path(__file__).resolve().parent / "models"

# 1. تحميل الموديل والبيانات
print("جاري تحميل الموديل والبيانات...")
model = joblib.load(MODEL_DIR / "sepsis_xgb_model.pkl")
df = pd.read_csv(PROJECT_ROOT / "data" / "cleaned_data_1000.csv")

X = df.drop(columns=["Patient_ID", "SepsisLabel"])

# 2. إنشاء حسابات SHAP للـ Explainability
print("جاري حساب قيم SHAP وتأثير الميزات (Feature Importance)...")
explainer = shap.TreeExplainer(model)
shap_values = explainer(X.iloc[:500])  # حساب الشرح لأول 500 سجل لسرعة التنفيذ

# 3. رسم وحفظ مخطط أثر المؤشرات الحيوية الإجمالي (Summary Plot)
plt.figure(figsize=(10, 6))
shap.summary_plot(shap_values, X.iloc[:500], show=False)
plt.title("Sepsis Prediction - SHAP Feature Importance", fontsize=14)
plt.tight_layout()
plt.savefig(MODEL_DIR / "shap_summary.png", dpi=300)
plt.close()

print("\nتم إنشاء ورسم مخطط التفسير وحفظه في الصورة 'shap_summary.png' بنجاح!")