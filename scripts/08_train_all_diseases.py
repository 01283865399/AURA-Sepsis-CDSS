"""
تدريب على كل الأمراض (527)
مع قياس Top-1 و Top-5 accuracy
"""

import pandas as pd
import numpy as np
import joblib
import time
import json
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score, top_k_accuracy_score
import warnings
warnings.filterwarnings("ignore")

DATA_DIR = Path("D:/pri/project2028/data/raw/symptoms")
MODELS_DIR = Path("D:/pri/project2028/models/symptoms_all")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

BIG_FILE = DATA_DIR / "Final_Augmented_dataset_Diseases_and_Symptoms.csv"

MIN_SAMPLES = 50  # أقل عدد صفوف لكل مرض


def load_and_clean():
    print("📥 تحميل الداتا...")
    df = pd.read_csv(BIG_FILE)
    print(f"✅ {df.shape[0]:,} صف × {df.shape[1]} عمود")
    
    # تنظيف أسماء الأعمدة
    df.columns = (
        df.columns.str.strip()
        .str.replace(r'\s+', '_', regex=True)
        .str.replace(r'_+', '_', regex=True)
        .str.replace(r'[^\w_]', '', regex=True)
    )
    return df


def filter_rare(df, min_samples=50):
    print(f"\n🔍 فلترة الأمراض النادرة (< {min_samples})...")
    
    vc = df["diseases"].value_counts()
    valid = vc[vc >= min_samples].index
    
    df_filtered = df[df["diseases"].isin(valid)].copy()
    
    print(f"   قبل: {df['diseases'].nunique()} مرض، {len(df):,} صف")
    print(f"   بعد: {df_filtered['diseases'].nunique()} مرض، {len(df_filtered):,} صف")
    
    return df_filtered


def prepare(df):
    X = df.drop(columns=["diseases"])
    y = df["diseases"]
    
    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    
    print(f"\n✅ X: {X.shape}")
    print(f"✅ {len(le.classes_)} فئة")
    
    return X, y_enc, le


def main():
    print("="*75)
    print(f"🎯 تدريب على كل الأمراض (min {MIN_SAMPLES} صف)")
    print("="*75)
    
    # 1. تحميل
    df = load_and_clean()
    
    # 2. فلترة
    df = filter_rare(df, MIN_SAMPLES)
    
    # 3. تحضير
    X, y, le = prepare(df)
    
    # 4. Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"\n✂️  X_train: {X_train.shape}")
    print(f"✂️  X_test:  {X_test.shape}")
    
    # 5. موديل
    print(f"\n{'='*75}")
    print("🚀 LightGBM")
    print(f"{'='*75}")
    
    from lightgbm import LGBMClassifier
    
    model = LGBMClassifier(
        n_estimators=300,
        max_depth=12,
        learning_rate=0.1,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    
    print("   ⏳ تدريب...")
    t0 = time.time()
    model.fit(X_train, y_train)
    train_time = time.time() - t0
    
    print("   🔮 تنبؤ...")
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    
    # 6. تقييم
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)
    
    # Top-K accuracy
    top3 = top_k_accuracy_score(y_test, y_proba, k=3)
    top5 = top_k_accuracy_score(y_test, y_proba, k=5)
    top10 = top_k_accuracy_score(y_test, y_proba, k=10)
    
    print(f"\n   📊 النتائج:")
    print(f"   ┌──────────────────────────────────┐")
    print(f"   │ Top-1 Accuracy:  {acc:>6.4f} ({acc*100:>5.2f}%) │")
    print(f"   │ Top-3 Accuracy:  {top3:>6.4f} ({top3*100:>5.2f}%) │")
    print(f"   │ Top-5 Accuracy:  {top5:>6.4f} ({top5*100:>5.2f}%) │")
    print(f"   │ Top-10 Accuracy: {top10:>6.4f} ({top10*100:>5.2f}%) │")
    print(f"   │ F1-Score:        {f1:>6.4f}           │")
    print(f"   └──────────────────────────────────┘")
    print(f"   ⏱️  تدريب: {train_time:.1f}s")
    
    # 7. حفظ
    print(f"\n💾 حفظ...")
    joblib.dump(model, MODELS_DIR / "best_model.pkl")
    joblib.dump(le, MODELS_DIR / "label_encoder.pkl")
    
    metadata = {
        "model_name": "LightGBM",
        "top1_accuracy": float(acc),
        "top3_accuracy": float(top3),
        "top5_accuracy": float(top5),
        "top10_accuracy": float(top10),
        "f1_score": float(f1),
        "num_classes": len(le.classes_),
        "min_samples": MIN_SAMPLES,
        "classes": [str(c) for c in le.classes_],
    }
    with open(MODELS_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ best_model.pkl")
    print(f"   ✅ label_encoder.pkl")
    print(f"   ✅ metadata.json")
    
    print(f"\n{'='*75}")
    print("✅ تم!")
    print(f"{'='*75}\n")


if __name__ == "__main__":
    main()