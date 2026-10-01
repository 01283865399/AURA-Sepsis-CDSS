# System architecture

```mermaid
flowchart LR
    Browser[React and Vite<br/>frontend/] -->|HTTP and JSON| API[FastAPI<br/>backend/main.py]
    API --> Inference[Inference and SHAP<br/>backend/sepsis_service.py]
    API --> PDF[PDF export<br/>ReportLab]
    API --> XRay[X-ray screening and optional OCR]
    API --> SQLite[(Local SQLite<br/>data/patients.sqlite3)]
    API --> Supabase[(Optional Supabase<br/>server-side credentials)]
    Trainer[Training pipeline<br/>backend/train_sepsis.py] --> Data[Patient and image data<br/>data/]
    Trainer --> Models[Model artifacts<br/>backend/models/]
    Inference --> Models
```

The browser communicates with FastAPI; it never connects directly to the
database or receives Supabase server secrets. SQLite is the local-development
default. Supabase is selected explicitly through the API environment. Patient
datasets, local database files, and model artifacts are separate from source
code so deployments can manage them independently.
