
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "raw"


def inspect_dataset(name: str, path: Path):
    """يفحص dataset واحد ويعرض ملخص كامل"""
    print(f"\n{'='*75}")
    print(f"📊 {name}")
    print(f"📁 {path.name}")
    print(f"{'='*75}")
    
    if not path.exists():
        print(f"❌ الملف مش موجود!")
        return
    
    try:
        df = pd.read_csv(path)
        
        # المعلومات الأساسية
        print(f"✅ الشكل: {df.shape[0]:,} صف × {df.shape[1]} عمود")
        print(f"💾 الحجم: {path.stat().st_size / 1024:.1f} KB")
        
        # الأعمدة
        print(f"\n📋 الأعمدة ({len(df.columns)}):")
        cols = list(df.columns)
        for i in range(0, len(cols), 5):
            print("   " + " | ".join(str(c)[:22] for c in cols[i:i+5]))
        
        # القيم الفارغة
        missing = df.isnull().sum()
        missing = missing[missing > 0]
        if len(missing) > 0:
            print(f"\n⚠️  قيم فارغة ({len(missing)} عمود):")
            for col, count in missing.head(5).items():
                print(f"   {col[:30]:30} → {count:,} ({count/len(df)*100:.1f}%)")
        else:
            print(f"\n✅ مفيش قيم فارغة")
        
        # أنواع البيانات
        dtypes = df.dtypes.value_counts()
        print(f"\n🔢 أنواع البيانات: {dict(dtypes)}")
        
        # التصنيف
        target_keywords = ["prognosis", "num", "classification", "outcome", 
                          "target", "diagnosis", "class", "label", "diabetes"]
        for col in df.columns:
            if col.lower() in [t.lower() for t in target_keywords]:
                print(f"\n🎯 التوزيع في '{col}':")
                vc = df[col].value_counts()
                if len(vc) <= 10:
                    for val, count in vc.items():
                        pct = count / len(df) * 100
                        bar = "█" * int(pct / 2)
                        print(f"   {str(val)[:20]:20} │ {count:6,} ({pct:5.1f}%) {bar}")
                else:
                    print(f"   عدد الفئات: {len(vc)}")
                break
        
        # إحصائيات الأعمدة الرقمية
        numeric_cols = df.select_dtypes(include=['number']).columns
        if 0 < len(numeric_cols) <= 15:
            print(f"\n📈 إحصائيات الأعمدة الرقمية:")
            print(df[numeric_cols].describe().round(2).to_string())
        
    except Exception as e:
        print(f"❌ خطأ: {e}")


def main():
    print("\n" + "="*75)
    print("🔍 فحص شامل لكل datasets المشروع")
    print("="*75)
    
    datasets = {
        "Symptoms - Training": DATA_DIR / "symptoms" / "Training.csv",
        "Symptoms - Testing": DATA_DIR / "symptoms" / "Testing.csv",
        "Symptoms - Dataset (dhivyesh)": DATA_DIR / "symptoms" / "dataset.csv",
        "Symptoms - Description": DATA_DIR / "symptoms" / "symptom_Description.csv",
        "Symptoms - Precaution": DATA_DIR / "symptoms" / "symptom_precaution.csv",
        "Symptoms - Severity": DATA_DIR / "symptoms" / "Symptom-severity.csv",
        "Heart - UCI": DATA_DIR / "heart" / "heart_disease_uci.csv",
        "Kidney": DATA_DIR / "kidney" / "kidney_disease.csv",
        "Diabetes": DATA_DIR / "diabetes" / "diabetes_prediction_dataset.csv",
    }
    
    for name, path in datasets.items():
        inspect_dataset(name, path)
    
    print(f"\n{'='*75}")
    print("✅ تم الفحص بنجاح")
    print(f"{'='*75}\n")


if __name__ == "__main__":
    main()