/** @typedef {{ condition: string, probability: number }} Prediction */

/** @typedef {{
 * endpoint: string,
 * model_name: string,
 * predictions: Prediction[],
 * medical_content?: Array<{condition: string, available: boolean, status: string,
 *   notice?: string, notice_ar?: string, content?: object}>,
 * persisted?: boolean,
 * research_only?: boolean,
 * notice?: string
 * }} PredictionResponse
 */

/** @typedef {{
 * id: string,
 * title: string,
 * description: string,
 * endpoint?: string,
 * transport: 'json' | 'image-form' | 'raw-image',
 * api: 'model' | 'clinical',
 * available: boolean,
 * fields?: Array<{ name: string, label: string, type?: string, required?: boolean,
 *   min?: number, max?: number, step?: number, options?: Array<{label: string, value: string}> }>
 * }} ModuleDefinition
 */

/** @typedef {{
 * id: string,
 * modelId: string,
 * createdAt: string,
 * modelName: string,
 * predictions: Prediction[],
 * researchOnly: boolean,
 * detail?: string
 * }} HistoryRecord
 */
