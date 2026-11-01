"""
تنظيف وتحضير Symptoms dataset للتدريب
⚠️  ملاحظة مهمة: الداتا دي فيها صفوف متشابهة طبيعياً (كل مرض ~120 حالة)
    متستخدمش drop_duplicates() هنا
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib


# ============================================================
# المسارات
# ============================================================
RAW_DIR = Path(__file__).parent.parent / "data" / "raw" / "symptoms"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed" / "symptoms"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 1. تحميل الداتا
# ============================================================
def load_data():
    """تحميل الداتا من الملفات الخام"""
    print("📥 تحميل الداتا...")
    train = pd.read_csv(RAW_DIR / "Training.csv")
    print(f"✅ Training: {train.shape}")
    return train


# ============================================================
# 2. تنظيف الداتا
# ============================================================
def clean_data(df):
    """تنظيف الداتا (بدون مسح الصفوف المتشابهة)"""
    print("\n🧹 تنظيف الداتا...")
    original_shape = df.shape

    # 2.1 امسح العمود الفارغ
    if "Unnamed: 133" in df.columns:
        df = df.drop(columns=["Unnamed: 133"])
        print("   ✅ اتمسح 'Unnamed: 133'")

    # 2.2 شيل المسافات من أسماء الأعمدة
    df.columns = df.columns.str.strip()
    print("   ✅ اتنضفت أسماء الأعمدة")

    # 2.3 ملاحظة: فيه صفوف متشابهة طبيعياً — مش هنمسحها
    duplicates = df.duplicated().sum()
    print(f"   ℹ️  فيه {duplicates} صف متشابه (طبيعي - مش هنمسحهم)")

    # 2.4 شيل المسافات من القيم النصية
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].str.strip()
    print("   ✅ اتنضفت القيم النصية")

    print(f"   📊 {original_shape} → {df.shape}")
    return df


# ============================================================
# 3. استكشاف الـ Target
# ============================================================
def explore_target(df):
    """استكشاف توزيع الأمراض في العمود prognosis"""
    print("\n🎯 استكشاف الـ Target (prognosis):")
    print(f"   عدد الأمراض: {df['prognosis'].nunique()}")

    vc = df["prognosis"].value_counts()

    print("\n   أعلى 5:")
    for disease, count in vc.head(5).items():
        print(f"      {disease:40} → {count}")

    print("\n   أقل 5:")
    for disease, count in vc.tail(5).items():
        print(f"      {disease:40} → {count}")

    imbalance_ratio = vc.max() / vc.min()
    print(f"\n   ⚖️  نسبة عدم التوازن: {imbalance_ratio:.2f}x")
    print(f"   📊 مجموع الصفوف: {len(df)}")

    return vc


# ============================================================
# 4. تحضير الـ Features
# ============================================================
def prepare_features(df):
    """فصل الـ features (X) عن الـ target (y)"""
    print("\n🔧 تحضير الـ features...")

    X = df.drop(columns=["prognosis"])
    y = df["prognosis"]

    print(f"   ✅ X: {X.shape}")
    print(f"   ✅ y: {y.shape}")

    # التحقق إن كل الأعراض binary (0/1)
    non_binary = []
    for col in X.columns:
        unique_vals = X[col].unique()
        if not set(unique_vals).issubset({0, 1}):
            non_binary.append((col, unique_vals))

    if non_binary:
        print("   ⚠️  أعمدة مش binary:")
        for col, vals in non_binary[:5]:
            print(f"      {col}: {vals[:5]}")
    else:
        print("   ✅ كل الأعراض binary (0/1)")

    return X, y


# ============================================================
# 5. Encoding للـ Target
# ============================================================
def encode_target(y):
    """تحويل أسماء الأمراض لأرقام (0 إلى 40)"""
    print("\n🔢 Encoding للـ target...")

    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    print(f"   ✅ عدد الفئات: {len(le.classes_)}")

    return y_encoded, le


# ============================================================
# 6. تقسيم الداتا
# ============================================================
def split_data(X, y, test_size=0.2, random_state=42):
    """تقسيم الداتا إلى train و test مع الحفاظ على التوازن"""
    print(f"\n✂️  تقسيم الداتا ({1 - test_size:.0%} train / {test_size:.0%} test)...")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,  # مهم جداً للحفاظ على توزيع الأمراض
    )

    print(f"   ✅ X_train: {X_train.shape}")
    print(f"   ✅ X_test:  {X_test.shape}")
    print(f"   ✅ y_train: {y_train.shape}")
    print(f"   ✅ y_test:  {y_test.shape}")

    return X_train, X_test, y_train, y_test


# ============================================================
# 7. حفظ الداتا المعالجة
# ============================================================
def save_processed(X_train, X_test, y_train, y_test, le):
    """حفظ الداتا المعالجة والـ LabelEncoder"""
    print(f"\n💾 حفظ الداتا في {PROCESSED_DIR}...")

    X_train.to_csv(PROCESSED_DIR / "X_train.csv", index=False)
    X_test.to_csv(PROCESSED_DIR / "X_test.csv", index=False)
    pd.Series(y_train, name="prognosis").to_csv(
        PROCESSED_DIR / "y_train.csv", index=False
    )
    pd.Series(y_test, name="prognosis").to_csv(
        PROCESSED_DIR / "y_test.csv", index=False
    )

    joblib.dump(le, PROCESSED_DIR / "label_encoder.pkl")

    print("   ✅ X_train.csv")
    print("   ✅ X_test.csv")
    print("   ✅ y_train.csv")
    print("   ✅ y_test.csv")
    print("   ✅ label_encoder.pkl")


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 75)
    print("🧹 تنظيف وتحضير Symptoms Dataset")
    print("=" * 75)

    # 1. تحميل
    df = load_data()

    # 2. تنظيف
    df = clean_data(df)

    # 3. استكشاف
    explore_target(df)

    # 4. تحضير features
    X, y = prepare_features(df)

    # 5. Encoding
    y_encoded, le = encode_target(y)

    # 6. Split
    X_train, X_test, y_train, y_test = split_data(X, y_encoded)

    # 7. حفظ
    save_processed(X_train, X_test, y_train, y_test, le)

    print(f"\n{'=' * 75}")
    print("✅ تم التحضير بنجاح!")
    print(f"{'=' * 75}\n")


if __name__ == "__main__":
    main()