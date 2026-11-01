"""
تنزيل MedQuAD من HuggingFace
"""
from datasets import load_dataset
from pathlib import Path

OUTPUT_DIR = Path("D:/pri/project2028/data/medical_content/raw/medquad")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("📥 Downloading MedQuAD from HuggingFace...")
ds = load_dataset("mukulb/clustered_MEDQUAD_dataset_with_groups")

print(f"✅ Loaded dataset")
print(f"   Splits: {list(ds.keys())}")
print(f"   Total rows: {sum(len(ds[s]) for s in ds.keys())}")

# احفظ
ds.save_to_disk(str(OUTPUT_DIR))
print(f"✅ Saved to: {OUTPUT_DIR}")