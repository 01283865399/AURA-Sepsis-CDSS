"""
تدريب ومقارنة موديلات Symptoms Dataset
- Random Forest
- XGBoost
- Logistic Regression
- SVM
"""

import pandas as pd
import numpy as np
import joblib
import time
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
)
import warnings
warnings.filterwarnings("ignore")

# ============================================================
# المسارات
# ============================================================
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed" / "symptoms"
MODELS_DIR = Path(__file__).parent.parent / "models" / "symptoms"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 1. تحميل الداتا المعالجة
# ============================================================
def load_processed_data():
    """تحميل X_train, X_test, y_train, y_test"""
    print("📥 تحميل الداتا المعالجة...")

    X_train = pd.read_csv(PROCESSED_DIR / "X_train.csv")
    X_test = pd.read_csv(PROCESSED_DIR / "X_test.csv")
    y_train = pd.read_csv(PROCESSED_DIR / "y_train.csv").values.ravel()
    y_test = pd.read_csv(PROCESSED_DIR / "y_test.csv").values.ravel()
    le = joblib.load(PROCESSED_DIR / "label_encoder.pkl")

    print(f"   ✅ X_train: {X_train.shape}")
    print(f"   ✅ X_test:  {X_test.shape}")
    print(f"   ✅ y_train: {y_train.shape}")
    print(f"   ✅ y_test:  {y_test.shape}")

    return X_train, X_test, y_train, y_test, le


# ============================================================
# 2. تعريف الموديلات
# ============================================================
def get_models():
    """إرجاع dict بكل الموديلات"""
    models = {
        "Random Forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=None,
            min_samples_split=2,
            min_samples_leaf=1,
            random_state=42,
            n_jobs=-1,
        ),
        "Logistic Regression": LogisticRegression(
            max_iter=2000,
            random_state=42,
            n_jobs=-1,
        ),
        "SVM": SVC(
            kernel="rbf",
            C=10,
            gamma="scale",
            probability=True,
            random_state=42,
        ),
    }

    # XGBoost (لو متسطب)
    try:
        from xgboost import XGBClassifier
        models["XGBoost"] = XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            n_jobs=-1,
            eval_metric="mlogloss",
            use_label_encoder=False,
        )
    except ImportError:
        print("   ⚠️  XGBoost مش متسطب — هيتم تخطيه")

    return models


# ============================================================
# 3. تدريب وتقييم موديل
# ============================================================
def train_and_evaluate(name, model, X_train, X_test, y_train, y_test):
    """تدريب موديل وتقييمه"""
    print(f"\n{'=' * 75}")
    print(f"🚀 {name}")
    print(f"{'=' * 75}")

    # تدريب
    print("   ⏳ تدريب...")
    start_time = time.time()
    model.fit(X_train, y_train)
    train_time = time.time() - start_time

    # تنبؤ
    print("   🔮 تنبؤ...")
    start_time = time.time()
    y_pred = model.predict(X_test)
    predict_time = time.time() - start_time

    # التقييم
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    # النتائج
    print(f"\n   📊 النتائج:")
    print(f"   ┌─────────────────────────────────┐")
    print(f"   │ Accuracy:  {accuracy:>6.4f} ({accuracy * 100:>5.2f}%)  │")
    print(f"   │ Precision: {precision:>6.4f}             │")
    print(f"   │ Recall:    {recall:>6.4f}             │")
    print(f"   │ F1-Score:  {f1:>6.4f}             │")
    print(f"   └─────────────────────────────────┘")
    print(f"   ⏱️  زمن التدريب: {train_time:.2f}s")
    print(f"   ⏱️  زمن التنبؤ: {predict_time:.4f}s")

    return {
        "name": name,
        "model": model,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "train_time": train_time,
        "predict_time": predict_time,
        "y_pred": y_pred,
    }


# ============================================================
# 4. مقارنة كل الموديلات
# ============================================================
def compare_models(results):
    """مقارنة النتائج"""
    print(f"\n{'=' * 75}")
    print("📊 مقارنة الموديلات")
    print(f"{'=' * 75}\n")

    # ترتيب حسب F1
    results_sorted = sorted(results, key=lambda x: x["f1"], reverse=True)

    # جدول
    print(f"   {'Model':<22} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print(f"   {'-' * 22} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 10}")

    for r in results_sorted:
        print(
            f"   {r['name']:<22} "
            f"{r['accuracy']:>10.4f} "
            f"{r['precision']:>10.4f} "
            f"{r['recall']:>10.4f} "
            f"{r['f1']:>10.4f}"
        )

    # الأفضل
    best = results_sorted[0]
    print(f"\n   🏆 الأفضل: {best['name']} (F1={best['f1']:.4f})")

    return best


# ============================================================
# 5. حفظ أفضل موديل
# ============================================================
def save_best_model(best_result, le):
    """حفظ أفضل موديل"""
    print(f"\n💾 حفظ أفضل موديل...")

    model_path = MODELS_DIR / "best_symptoms_model.pkl"
    joblib.dump(best_result["model"], model_path)
    print(f"   ✅ {model_path}")

    # حفظ الـ LabelEncoder كمان
    le_path = MODELS_DIR / "label_encoder.pkl"
    joblib.dump(le, le_path)
    print(f"   ✅ {le_path}")

    # حفظ metadata
    metadata = {
        "model_name": best_result["name"],
        "accuracy": best_result["accuracy"],
        "precision": best_result["precision"],
        "recall": best_result["recall"],
        "f1": best_result["f1"],
        "num_classes": len(le.classes_),
        "classes": list(le.classes_),
        "num_features": 132,
    }

    import json
    metadata_path = MODELS_DIR / "model_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"   ✅ {metadata_path}")


# ============================================================
# 6. تحليل مفصّل لأفضل موديل
# ============================================================
def detailed_analysis(best_result, y_test, le):
    """تحليل مفصّل لأفضل موديل"""
    print(f"\n{'=' * 75}")
    print(f"🔍 تحليل مفصّل: {best_result['name']}")
    print(f"{'=' * 75}\n")

    y_pred = best_result["y_pred"]

    # Classification Report
    print("📋 Classification Report (أعلى 15 فئة):\n")
    report = classification_report(
        y_test,
        y_pred,
        target_names=le.classes_,
        output_dict=True,
        zero_division=0,
    )

    print(f"   {'Disease':<40} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print(f"   {'-' * 40} {'-' * 10} {'-' * 10} {'-' * 10}")

    # ترتيب حسب F1
    classes_sorted = sorted(
        [(name, metrics) for name, metrics in report.items()
         if isinstance(metrics, dict)],
        key=lambda x: x[1]["f1-score"],
        reverse=True,
    )

    for name, metrics in classes_sorted[:15]:
        if len(name) > 38:
            name = name[:35] + "..."
        print(
            f"   {name:<40} "
            f"{metrics['precision']:>10.3f} "
            f"{metrics['recall']:>10.3f} "
            f"{metrics['f1-score']:>10.3f}"
        )

    # أضعف الفئات
    print(f"\n   ⚠️  أضعف 5 فئات:\n")
    for name, metrics in classes_sorted[-5:]:
        if len(name) > 38:
            name = name[:35] + "..."
        print(
            f"   {name:<40} "
            f"{metrics['precision']:>10.3f} "
            f"{metrics['recall']:>10.3f} "
            f"{metrics['f1-score']:>10.3f}"
        )


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 75)
    print("🎯 تدريب ومقارنة موديلات Symptoms")
    print("=" * 75)

    # 1. تحميل
    X_train, X_test, y_train, y_test, le = load_processed_data()

    # 2. الموديلات
    models = get_models()
    print(f"\n📋 عدد الموديلات: {len(models)}")

    # 3. تدريب كل موديل
    results = []
    for name, model in models.items():
        result = train_and_evaluate(name, model, X_train, X_test, y_train, y_test)
        results.append(result)

    # 4. مقارنة
    best = compare_models(results)

    # 5. حفظ
    save_best_model(best, le)

    # 6. تحليل مفصّل
    detailed_analysis(best, y_test, le)

    print(f"\n{'=' * 75}")
    print("✅ تم التدريب بنجاح!")
    print(f"{'=' * 75}\n")


if __name__ == "__main__":
    main()