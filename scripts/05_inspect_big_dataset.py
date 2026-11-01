"""
فحص الملف الجديد الكبير (186 MB)
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path("D:/pri/project2028/data/raw/symptoms")
FILE = DATA_DIR / "Final_Augmented_dataset_Diseases_and_Symptoms.csv"

print("="*75)
print("🔍 فحص الملف الجديد الكبير")
print("="*75)

print(f"\n📁 {FILE.name}")
print(f"💾 الحجم: {FILE.stat().st_size/1024/1024:.1f} MB")

# اقرأ أول 10000 صف بس (سرعة)
print(f"\n⏳ بنقرأ أول 10,000 صف...")
df_sample = pd.read_csv(FILE, nrows=10000)

print(f"\n✅ الشكل (أول 10000 صف): {df_sample.shape[0]:,} صف × {df_sample.shape[1]} عمود")

# الأعمدة
print(f"\n📋 الأعمدة ({len(df_sample.columns)}):")
cols = list(df_sample.columns)
for i in range(0, len(cols), 4):
    print("   " + " | ".join(str(c)[:25] for c in cols[i:i+4]))

# القيم الفارغة
missing = df_sample.isnull().sum()
missing = missing[missing > 0]
if len(missing) > 0:
    print(f"\n⚠️  قيم فارغة في أول 10000 صف ({len(missing)} عمود):")
    for col, count in missing.head(5).items():
        print(f"   {col[:40]:40} → {count:,}")
else:
    print(f"\n✅ مفيش قيم فارغة في أول 10000 صف")

# التصنيف
target_cols = [c for c in df_sample.columns if "disease" in c.lower() or "prognosis" in c.lower()]
if target_cols:
    target = target_cols[0]
    print(f"\n🎯 التصنيف '{target}' (في أول 10000 صف):")
    vc = df_sample[target].value_counts()
    print(f"   عدد الفئات: {len(vc)}")
    print(f"\n   أعلى 10:")
    for val, count in vc.head(10).items():
        print(f"      {str(val)[:50]:50} → {count:,}")

# أول 3 صفوف
print(f"\n👀 أول 3 صفوف:")
print(df_sample.head(3).to_string(max_cols=8))

# عدّ الصفوف كلها (سريع بس ممكن ياخد وقت)
print(f"\n⏳ بنعدّ كل الصفوف...")
with open(FILE, 'r', encoding='utf-8', errors='ignore') as f:
    total_rows = sum(1 for _ in f) - 1  # -1 للـ header

print(f"\n✅ إجمالي الصفوف: {total_rows:,}")

print(f"\n{'='*75}")
print("✅ تم الفحص!")
print(f"{'='*75}\n")