"""
تدريب على Final_Augmented (246K صف، 773 مرض)
- فلترة الأمراض النادرة
- Class weights
- LightGBM (أو XGBoost)
"""

import pandas as pd
import numpy as np
import joblib
import time
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.utils.class_weight import compute_class_weight
import warnings
warnings.filterwarnings("ignore")

# المسارات
DATA_DIR = Path("D:/pri/project2028/data/raw/symptoms")
PROCESSED_DIR = Path("D:/pri/project2028/data/processed/symptoms_big")
MODELS_DIR = Path("D:/pri/project2028/models/symptoms_big")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

BIG_FILE = DATA_DIR / "Final_Augmented_dataset_Diseases_and_Symptoms.csv"

# الحد الأدنى لعدد الصفوف لكل مرض
MIN_SAMPLES_PER_CLASS = 50


def load_big_data():
    """تحميل الداتا الكبيرة"""
    print("📥 تحميل الداتا (ممكن ياخد 30-60 ثانية)...")
    t0 = time.time()
    df = pd.read_csv(BIG_FILE)
    print(f"✅ اتحملت في {time.time()-t0:.1f}s")
    print(f"   الشكل: {df.shape[0]:,} صف × {df.shape[1]} عمود")
    return df


def clean_columns(df):
    """تنظيف أسماء الأعمدة"""
    print("\n🧹 تنظيف أسماء الأعمدة...")
    df.columns = (
        df.columns
        .str.strip()
        .str.replace(r'\s+', '_', regex=True)
        .str.replace(r'_+', '_', regex=True)
        .str.replace(r'[^\w_]', '', regex=True)
    )
    print(f"   ✅ اتنضفوا {len(df.columns)} عمود")
    return df


def filter_rare_diseases(df, target_col="diseases", min_samples=50):
    """شيل الأمراض النادرة"""
    print(f"\n🔍 فلترة الأمراض النادرة (< {min_samples} صف)...")
    
    original_classes = df[target_col].nunique()
    original_rows = len(df)
    
    # احسب توزيع الأمراض
    vc = df[target_col].value_counts()
    
    # الأمراض اللي عندها صفوف كفاية
    valid_diseases = vc[vc >= min_samples].index.tolist()
    
    # فلتر الداتا
    df_filtered = df[df[target_col].isin(valid_diseases)].copy()
    
    # النتائج
    new_classes = df_filtered[target_col].nunique()
    new_rows = len(df_filtered)
    
    print(f"   قبل:  {original_classes} مرض، {original_rows:,} صف")
    print(f"   بعد:  {new_classes} مرض، {new_rows:,} صف")
    print(f"   ✂️  اتمسحوا: {original_classes - new_classes} مرض، {original_rows - new_rows:,} صف")
    
    # التوازن الجديد
    vc_new = df_filtered[target_col].value_counts()
    imbalance = vc_new.max() / vc_new.min()
    print(f"   ⚖️  التوازن الجديد: {imbalance:.2f}x (كان {vc.max()/vc.min():.2f}x)")
    
    return df_filtered


def explore_target(df, target_col="diseases"):
    """استكشاف التصنيف"""
    print(f"\n🎯 استكشاف '{target_col}':")
    
    vc = df[target_col].value_counts()
    print(f"   عدد الأمراض: {len(vc)}")
    print(f"   إجمالي الصفوف: {len(df):,}")
    
    print(f"\n   أعلى 10:")
    for val, count in vc.head(10).items():
        pct = count / len(df) * 100
        print(f"      {str(val)[:40]:40} → {count:>7,} ({pct:5.1f}%)")
    
    print(f"\n   أقل 10:")
    for val, count in vc.tail(10).items():
        pct = count / len(df) * 100
        print(f"      {str(val)[:40]:40} → {count:>7,} ({pct:5.1f}%)")
    
    imbalance = vc.max() / vc.min()
    print(f"\n   ⚖️  نسبة عدم التوازن: {imbalance:.2f}x")
    
    return vc


def prepare_data(df, target_col="diseases"):
    """تحضير X, y"""
    print("\n🔧 تحضير البيانات...")
    
    X = df.drop(columns=[target_col])
    y = df[target_col]
    
    print(f"   ✅ X: {X.shape}")
    print(f"   ✅ y: {y.shape}")
    
    return X, y


def encode_target(y):
    """تحويل الأمراض لأرقام"""
    print("\n🔢 Encoding للـ target...")
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    print(f"   ✅ {len(le.classes_)} فئة")
    return y_encoded, le


def split_data(X, y, test_size=0.2, random_state=42):
    """تقسيم stratified (آمن)"""
    print(f"\n✂️  تقسيم ({1-test_size:.0%} train / {test_size:.0%} test)...")
    
    # ✅ دلوقتي آمن لأن مفيش أمراض بـ صف واحد
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    
    print(f"   ✅ X_train: {X_train.shape}")
    print(f"   ✅ X_test:  {X_test.shape}")
    return X_train, X_test, y_train, y_test


def train_and_evaluate(name, model, X_train, X_test, y_train, y_test):
    """تدريب وتقييم"""
    print(f"\n{'='*75}")
    print(f"🚀 {name}")
    print(f"{'='*75}")
    
    print("   ⏳ تدريب...")
    t0 = time.time()
    model.fit(X_train, y_train)
    train_time = time.time() - t0
    
    print("   🔮 تنبؤ...")
    t0 = time.time()
    y_pred = model.predict(X_test)
    predict_time = time.time() - t0
    
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    rec = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)
    
    print(f"\n   📊 النتائج:")
    print(f"      Accuracy:  {acc:.4f} ({acc*100:.2f}%)")
    print(f"      Precision: {prec:.4f}")
    print(f"      Recall:    {rec:.4f}")
    print(f"      F1-Score:  {f1:.4f}")
    print(f"   ⏱️  تدريب: {train_time:.1f}s")
    print(f"   ⏱️  تنبؤ:  {predict_time:.2f}s")
    
    return {
        "name": name, "model": model, "accuracy": acc,
        "precision": prec, "recall": rec, "f1": f1,
        "train_time": train_time, "predict_time": predict_time,
    }


def compare_models(results):
    """مقارنة"""
    print(f"\n{'='*75}")
    print("📊 مقارنة الموديلات")
    print(f"{'='*75}\n")
    
    results_sorted = sorted(results, key=lambda x: x["f1"], reverse=True)
    
    print(f"   {'Model':<22} {'Accuracy':>10} {'F1':>10} {'Time':>10}")
    print(f"   {'-'*22} {'-'*10} {'-'*10} {'-'*10}")
    
    for r in results_sorted:
        print(
            f"   {r['name']:<22} "
            f"{r['accuracy']:>10.4f} "
            f"{r['f1']:>10.4f} "
            f"{r['train_time']:>9.1f}s"
        )
    
    best = results_sorted[0]
    print(f"\n   🏆 الأفضل: {best['name']} (F1={best['f1']:.4f})")
    return best


def save_best(best, le):
    """حفظ أفضل موديل"""
    print(f"\n💾 حفظ أفضل موديل...")
    
    joblib.dump(best["model"], MODELS_DIR / "best_model.pkl")
    joblib.dump(le, MODELS_DIR / "label_encoder.pkl")
    
    import json
    metadata = {
        "model_name": best["name"],
        "accuracy": float(best["accuracy"]),
        "precision": float(best["precision"]),
        "recall": float(best["recall"]),
        "f1": float(best["f1"]),
        "num_classes": len(le.classes_),
        "classes": [str(c) for c in le.classes_],
        "min_samples_per_class": MIN_SAMPLES_PER_CLASS,
    }
    with open(MODELS_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ best_model.pkl")
    print(f"   ✅ label_encoder.pkl")
    print(f"   ✅ metadata.json")


def main():
    print("="*75)
    print("🎯 تدريب على Final_Augmented (246K صف)")
    print("="*75)
    
    # 1. تحميل
    df = load_big_data()
    
    # 2. تنظيف
    df = clean_columns(df)
    
    # 3. فلترة الأمراض النادرة
    df = filter_rare_diseases(df, target_col="diseases", min_samples=MIN_SAMPLES_PER_CLASS)
    
    # 4. استكشاف
    explore_target(df, target_col="diseases")
    
    # 5. تحضير
    X, y = prepare_data(df, target_col="diseases")
    
    # 6. Encoding
    y_encoded, le = encode_target(y)
    
    # 7. Split
    X_train, X_test, y_train, y_test = split_data(X, y_encoded)
    
    # 8. Class weights
    print(f"\n⚖️  حساب Class Weights...")
    class_weights = compute_class_weight(
        'balanced',
        classes=np.unique(y_train),
        y=y_train,
    )
    class_weight_dict = dict(enumerate(class_weights))
    print(f"   ✅ اتحسبت لـ {len(class_weights)} فئة")
    
    # 9. الموديلات
    models = {}
    
    # LightGBM (الأسرع)
    try:
        from lightgbm import LGBMClassifier
        models["LightGBM"] = LGBMClassifier(
            n_estimators=200,
            max_depth=8,
            learning_rate=0.1,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
    except ImportError:
        print("   ⚠️  LightGBM مش متسطب")
    
    # XGBoost
    try:
        from xgboost import XGBClassifier
        models["XGBoost"] = XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            n_jobs=-1,
            tree_method='hist',
            use_label_encoder=False,
            eval_metric='mlogloss',
        )
    except ImportError:
        print("   ⚠️  XGBoost مش متسطب")
    
    # Random Forest
    from sklearn.ensemble import RandomForestClassifier
    models["Random Forest"] = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1,
    )
    
    # 10. تدريب
    results = []
    for name, model in models.items():
        r = train_and_evaluate(name, model, X_train, X_test, y_train, y_test)
        results.append(r)
    
    # 11. مقارنة
    best = compare_models(results)
    
    # 12. حفظ
    save_best(best, le)
    
    print(f"\n{'='*75}")
    print("✅ تم!")
    print(f"{'='*75}\n")


if __name__ == "__main__":
    main()