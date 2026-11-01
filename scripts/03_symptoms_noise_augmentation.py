"""
إضافة noise صناعي للـ Symptoms dataset
- Dropout: محو أعراض عشوائية (مريض بينسى يقول عرض)
- Extra symptoms: إضافة أعراض عشوائية (مريض عنده أعراض من مرض تاني)
- Mixed: خلط أعراض مرضين (مريض عنده أكثر من مرض)
- الهدف: نشوف أداء الموديل الحقيقي ونحدد نقاط ضعفه
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
import warnings

warnings.filterwarnings("ignore")


# ============================================================
# المسارات
# ============================================================
RAW_DIR = Path(__file__).parent.parent / "data" / "raw" / "symptoms"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed" / "symptoms_noisy"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 1. تحميل الداتا
# ============================================================
def load_data():
    """تحميل الداتا النظيفة من الملفات الخام"""
    print("📥 تحميل الداتا...")
    df = pd.read_csv(RAW_DIR / "Training.csv")

    # امسح العمود الفارغ لو موجود
    if "Unnamed: 133" in df.columns:
        df = df.drop(columns=["Unnamed: 133"])

    # نضّف أسماء الأعمدة
    df.columns = df.columns.str.strip()

    print(f"✅ {df.shape}")
    return df


# ============================================================
# 2. Dropout - محو أعراض عشوائية
# ============================================================
def add_dropout(X, y, dropout_rate=0.2, random_state=42):
    """
    محو أعراض عشوائية من كل صف
    dropout_rate: نسبة الأعراض اللي هتمسح من كل مريض
    """
    print(f"\n🎲 إضافة Dropout ({dropout_rate:.0%})...")
    np.random.seed(random_state)

    # ✅ نسخة قابلة للتعديل (حل مشكلة read-only)
    X_noisy = np.array(X.values, dtype=np.int8, copy=True)
    num_samples, num_features = X_noisy.shape

    for i in range(num_samples):
        # فهارس الأعراض الموجودة
        active_symptoms = np.where(X_noisy[i] == 1)[0]
        if len(active_symptoms) == 0:
            continue

        # عدد الأعراض اللي هنمسحها
        n_drop = max(1, int(len(active_symptoms) * dropout_rate))

        # اختر عشوائي
        drop_indices = np.random.choice(active_symptoms, size=n_drop, replace=False)
        X_noisy[i, drop_indices] = 0

    X_noisy = pd.DataFrame(X_noisy, columns=X.columns)
    print(f"   ✅ اتمسحت ~{dropout_rate:.0%} من الأعراض لكل مريض")
    return X_noisy, y


# ============================================================
# 3. Extra Symptoms - إضافة أعراض عشوائية
# ============================================================
def add_extra_symptoms(X, y, extra_rate=0.05, random_state=42):
    """
    إضافة أعراض عشوائية مش موجودة (مريض عنده أعراض من مرض تاني)
    extra_rate: نسبة الأعراض الزيادة لكل مريض
    """
    print(f"\n🎲 إضافة أعراض زيادة ({extra_rate:.0%})...")
    np.random.seed(random_state)

    X_noisy = np.array(X.values, dtype=np.int8, copy=True)
    num_samples, num_features = X_noisy.shape

    for i in range(num_samples):
        # عدد الأعراض الزيادة
        n_extra = max(1, int(num_features * extra_rate * 0.1))

        # فهارس الأعراض المش موجودة
        inactive = np.where(X_noisy[i] == 0)[0]
        if len(inactive) == 0:
            continue

        n_extra = min(n_extra, len(inactive))
        extra_indices = np.random.choice(inactive, size=n_extra, replace=False)
        X_noisy[i, extra_indices] = 1

    X_noisy = pd.DataFrame(X_noisy, columns=X.columns)
    print(f"   ✅ اتضافت ~{extra_rate:.0%} أعراض لكل مريض")
    return X_noisy, y


# ============================================================
# 4. Mixed Symptoms - خلط أعراض مرضين
# ============================================================
def mix_symptoms(X, y, mix_rate=0.1, random_state=42):
    """
    خلط أعراض من مرضين مختلفين (مريض عنده أكثر من مرض)
    mix_rate: نسبة الصفوف اللي هتتخلط
    """
    print(f"\n🎲 خلط أعراض مرضين ({mix_rate:.0%} من الصفوف)...")
    np.random.seed(random_state)

    X_mixed = np.array(X.values, dtype=np.int8, copy=True)
    y_mixed = np.array(y.values, copy=True)
    num_samples = len(X_mixed)

    n_mix = int(num_samples * mix_rate)
    mix_indices = np.random.choice(num_samples, size=n_mix, replace=False)

    for i in mix_indices:
        # ابحث عن مريض من مرض مختلف
        j = np.random.randint(0, num_samples)
        attempts = 0
        while y_mixed[j] == y_mixed[i] and attempts < 50:
            j = np.random.randint(0, num_samples)
            attempts += 1

        if y_mixed[j] != y_mixed[i]:
            # ادمج الأعراض (OR logic)
            X_mixed[i] = np.maximum(X_mixed[i], X_mixed[j])

    X_mixed = pd.DataFrame(X_mixed, columns=X.columns)
    print(f"   ✅ اتم خلط {n_mix} مريض")
    return X_mixed, y_mixed


# ============================================================
# 5. تقييم سريع
# ============================================================
def evaluate_model(X_train, X_test, y_train, y_test, label=""):
    """تدريب وتقييم سريع بموديل Random Forest"""
    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="weighted")

    print(f"   📊 {label:35} Acc={acc:.4f} F1={f1:.4f}")
    return acc, f1


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 75)
    print("🎲 إضافة Noise للـ Symptoms Dataset")
    print("=" * 75)

    # 1. تحميل
    df = load_data()
    X = df.drop(columns=["prognosis"])
    y = df["prognosis"]

    # 2. Split أساسي
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    print(f"\n✂️  Split:")
    print(f"   X_train: {X_train.shape}")
    print(f"   X_test:  {X_test.shape}")

    # 3. Baseline (بدون noise)
    print(f"\n{'=' * 75}")
    print("📊 تقييم بدون Noise (Baseline)")
    print(f"{'=' * 75}")
    evaluate_model(X_train, X_test, y_train, y_test, "Original")

    # 4. Dropout
    print(f"\n{'=' * 75}")
    print("📊 تقييم مع Dropout")
    print(f"{'=' * 75}")
    for rate in [0.1, 0.2, 0.3, 0.5]:
        X_train_n, y_train_n = add_dropout(X_train, y_train, dropout_rate=rate)
        X_test_n, y_test_n = add_dropout(X_test, y_test, dropout_rate=rate)
        evaluate_model(
            X_train_n, X_test_n, y_train_n, y_test_n,
            f"Dropout {rate:.0%}"
        )

    # 5. Extra Symptoms
    print(f"\n{'=' * 75}")
    print("📊 تقييم مع Extra Symptoms")
    print(f"{'=' * 75}")
    for rate in [0.05, 0.1, 0.2]:
        X_train_n, y_train_n = add_extra_symptoms(X_train, y_train, extra_rate=rate)
        X_test_n, y_test_n = add_extra_symptoms(X_test, y_test, extra_rate=rate)
        evaluate_model(
            X_train_n, X_test_n, y_train_n, y_test_n,
            f"Extra {rate:.0%}"
        )

    # 6. Mixed Symptoms
    print(f"\n{'=' * 75}")
    print("📊 تقييم مع Mixed Symptoms")
    print(f"{'=' * 75}")
    for rate in [0.1, 0.2]:
        X_train_n, y_train_n = mix_symptoms(X_train, y_train, mix_rate=rate)
        X_test_n, y_test_n = mix_symptoms(X_test, y_test, mix_rate=rate)
        evaluate_model(
            X_train_n, X_test_n, y_train_n, y_test_n,
            f"Mixed {rate:.0%}"
        )

    print(f"\n{'=' * 75}")
    print("✅ تم التقييم بنجاح!")
    print(f"{'=' * 75}\n")


if __name__ == "__main__":
    main()