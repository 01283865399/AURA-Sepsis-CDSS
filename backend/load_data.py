import os
import glob
from pathlib import Path
import pandas as pd

def load_physionet_data(data_dir, limit=1000):
    """
    قراءة ملفات psv الموزعة للمرضى وتجميعها في DataFrame واحد
    """
    # البحث عن ملفات psv داخل مجلد data
    all_files = glob.glob(os.path.join(data_dir, "**", "*.psv"), recursive=True)

    print(f"إجمالي ملفات المرضى التي تم العثور عليها: {len(all_files)}")
    
    if limit and limit < len(all_files):
        all_files = all_files[:limit]
        
    df_list = []
    print(f"جاري قراءة وتجميع بيانات {len(all_files)} مريض...")
    
    for file in all_files:
        patient_id = os.path.basename(file).replace(".psv", "")
        patient_df = pd.read_csv(file, sep="|")
        patient_df["Patient_ID"] = patient_id
        df_list.append(patient_df)
        
    combined_df = pd.concat(df_list, ignore_index=True)
    return combined_df

# تحديد المسار الصحيح كما هو ظاهر في VS Code (فولدر data)
data_path = Path(__file__).resolve().parents[1] / "data"
df = load_physionet_data(data_path, limit=1000)

print("\n--- أبعاد البيانات (عدد السجلات x عدد الأعمدة) ---")
print(df.shape)

print("\n--- معاينة لأول 5 صفوف من البيانات ---")
print(df[["Patient_ID", "ICULOS", "HR", "Temp", "WBC", "SepsisLabel"]].head())

print("\n--- توزيع الحالات السليمة (0) مقابل المصابة (1) ---")
print(df["SepsisLabel"].value_counts())