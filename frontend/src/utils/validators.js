import { z } from 'zod';

export function makeModuleSchema(module) {
  if (module.id === 'symptoms') {
    return z.object({ symptoms: z.string().trim().min(2, 'أدخل عرضاً واحداً على الأقل') }).superRefine((values, context) => {
      const symptoms = values.symptoms.split(/[\n,،;]+/).map((item) => item.trim()).filter(Boolean);
      if (!symptoms.length) context.addIssue({ code: 'custom', path: ['symptoms'], message: 'أدخل عرضاً واحداً على الأقل' });
    });
  }
  if (module.id === 'ddxplus') {
    return z.object({
      age: z.preprocess((value) => value === '' ? undefined : Number(value), z.number().min(0).max(120)),
      sex: z.string().min(1, 'اختر الجنس'),
      evidences: z.string().trim().min(3, 'أدخل رمز دليل واحداً على الأقل'),
    }).superRefine((values, context) => {
      const evidences = values.evidences.split(/[\n,،;]+/).map((item) => item.trim()).filter(Boolean);
      if (evidences.some((item) => !/^E_\d+(?:_@_.+)?$/.test(item))) {
        context.addIssue({ code: 'custom', path: ['evidences'], message: 'استخدم رموزاً بصيغة E_123 أو E_123_@_value' });
      }
    });
  }

  const shape = {};
  for (const field of module.fields || []) {
    if (field.type === 'file') continue;
    if (field.type === 'number') {
      let numberSchema = z.number({ error: 'أدخل قيمة رقمية صالحة' });
      if (field.min != null) numberSchema = numberSchema.min(field.min, `الحد الأدنى ${field.min}`);
      if (field.max != null) numberSchema = numberSchema.max(field.max, `الحد الأعلى ${field.max}`);
      shape[field.name] = z.preprocess(
        (value) => value === '' || value == null ? undefined : Number(value),
        field.required ? numberSchema : numberSchema.optional(),
      );
    } else {
      const textSchema = z.string().trim();
      shape[field.name] = field.required
        ? textSchema.min(1, 'هذا الحقل مطلوب')
        : z.preprocess((value) => value === '' ? undefined : value, textSchema.optional());
    }
  }
  const schema = z.object(shape);
  if (module.id === 'kidney') {
    return schema.superRefine((values, context) => {
      if (!Object.values(values).some((value) => value !== undefined && value !== '')) {
        context.addIssue({ code: 'custom', message: 'أدخل مؤشراً واحداً على الأقل.' });
      }
    });
  }
  return schema;
}

export function validateImage(file) {
  if (!file) return 'اختر ملف صورة أولاً.';
  if (file.size > 10 * 1024 * 1024) return 'حجم الصورة يتجاوز الحد المسموح (10 ميغابايت).';
  if (!['image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/tiff'].includes(file.type)) {
    return 'الصيغ المدعومة: JPEG وPNG وWEBP وBMP وTIFF.';
  }
  return '';
}
