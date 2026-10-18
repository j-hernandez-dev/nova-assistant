/** Exact translations of Nova's built-in catalog text. Unknown provider text is
 * retained verbatim; this projection neither changes metadata nor model IDs. */
const ownText: Readonly<Record<string, readonly [string, string]>> = {
  'Alibaba コード特化。補完・生成・リファクタリングに強い。ツール呼び出し対応。': [
    'Especialista de Alibaba en código: autocompletado, generación y refactorización. Admite herramientas.',
    'Alibaba code specialist: completion, generation and refactoring. Supports tool calling.'],
  '7Bより高精度。複雑なロジックやマルチファイル編集に対応。': [
    'Más precisión que la variante 7B. Admite lógica compleja y edición de varios archivos.',
    'More accurate than the 7B variant. Supports complex logic and multi-file editing.'],
  'コーディング最高峰。GPT-4レベルに迫る精度。16GB+ VRAM推奨。': [
    'Especialista avanzado en código, con precisión cercana a GPT-4. Se recomiendan 16 GB o más de VRAM.',
    'Advanced coding specialist, with accuracy approaching GPT-4. 16 GB or more of VRAM recommended.'],
  'MoE構造で効率的。マルチファイル編集・デバッグに強い。': [
    'Arquitectura MoE eficiente. Orientado a edición de varios archivos y depuración.',
    'Efficient MoE architecture. Suited to multi-file editing and debugging.'],
  'Meta製コード特化。軽量だが基本的なコード生成は十分。': [
    'Especialista ligero en código de Meta, adecuado para generación básica.',
    'Lightweight Meta code specialist, suitable for basic code generation.'],
  'Code Llama大型版。7Bより精度向上。': [
    'Variante mayor de Code Llama, con más precisión que 7B.',
    'Larger Code Llama variant, with improved accuracy over 7B.'],
  'BigCode OSS。600以上の言語で学習。補完向き。': [
    'Modelo abierto de BigCode, entrenado con más de 600 lenguajes. Orientado al autocompletado.',
    'Open BigCode model, trained on more than 600 languages. Suited to completion.'],
  '最新Qwen 3.5。Vision+思考+ツール。サイズの割に非常に高性能。': [
    'Qwen 3.5 con visión, razonamiento y herramientas. Alto rendimiento para su tamaño.',
    'Qwen 3.5 with vision, reasoning and tools. Strong performance for its size.'],
  'Qwen 3.5中型。Vision対応、バランスの取れた推論力。': [
    'Qwen 3.5 de tamaño intermedio, con visión y razonamiento equilibrado.',
    'Mid-sized Qwen 3.5, with vision and balanced reasoning.'],
  'Qwen 3.5大型。フロンティアモデルに迫る品質。16GB+ VRAM推奨。': [
    'Variante grande de Qwen 3.5, con calidad cercana a modelos de frontera. Se recomiendan 16 GB o más de VRAM.',
    'Large Qwen 3.5 variant, approaching frontier-model quality. 16 GB or more of VRAM recommended.'],
  'Qwen 3。ツール呼び出し・推論に強い。日本語もそこそこ。エージェント向き。': [
    'Qwen 3 orientado a herramientas y razonamiento, con soporte moderado de japonés. Adecuado para agentes.',
    'Qwen 3 suited to tool calling and reasoning, with moderate Japanese support. Suitable for agents.'],
  'Qwen 3軽量版。8GB RAMでも動作。基本的なタスクに十分。': [
    'Variante ligera de Qwen 3, utilizable con 8 GB de RAM y orientada a tareas básicas.',
    'Lightweight Qwen 3 variant, usable with 8 GB of RAM and suited to basic tasks.'],
  'サイズと品質のバランスが良い。ツール呼び出し安定。': [
    'Equilibrio entre tamaño y calidad, con llamadas a herramientas estables.',
    'Balanced size and quality, with stable tool calling.'],
  '高品質推論。エージェントループに最適。24GB+ VRAM推奨。': [
    'Razonamiento de alta calidad, orientado a agentes. Se recomiendan 24 GB o más de VRAM.',
    'High-quality reasoning, suited to agent loops. 24 GB or more of VRAM recommended.'],
  'Meta製軽量モデル。高速レスポンス。簡単な質問向き。': [
    'Modelo ligero de Meta, con respuestas rápidas para preguntas sencillas.',
    'Lightweight Meta model, with fast responses for simple questions.'],
  'Meta製万能モデル。英語中心だが安定した品質。ツール対応。': [
    'Modelo general de Meta, centrado en inglés y con calidad estable. Admite herramientas.',
    'General Meta model, focused on English with stable quality. Supports tools.'],
  'Metaフラッグシップ。最高品質だが48GB+ VRAM必須。': [
    'Modelo insignia de Meta, de alta calidad; requiere 48 GB o más de VRAM.',
    'High-quality flagship Meta model; requires 48 GB or more of VRAM.'],
  'Google製軽量。シンプルなタスク向き。日本語は限定的。': [
    'Modelo ligero de Google para tareas sencillas. Soporte limitado de japonés.',
    'Lightweight Google model for simple tasks. Limited Japanese support.'],
  'Google中型。精度良好、日本語もそこそこ。ツール対応。': [
    'Modelo intermedio de Google, con buena precisión y soporte moderado de japonés. Admite herramientas.',
    'Mid-sized Google model, with good accuracy and moderate Japanese support. Supports tools.'],
  'Google最大OSS。推論・日本語とも高品質。16GB+ VRAM推奨。': [
    'Modelo abierto grande de Google, orientado a razonamiento y japonés. Se recomiendan 16 GB o más de VRAM.',
    'Large open Google model, suited to reasoning and Japanese. 16 GB or more of VRAM recommended.'],
  '欧州発の効率モデル。英語・仏語に強い。日本語は弱い。': [
    'Modelo europeo eficiente, orientado a inglés y francés. Soporte limitado de japonés.',
    'Efficient European model, suited to English and French. Limited Japanese support.'],
  'Microsoft製。数学・論理推論に強い。コード生成もそこそこ。': [
    'Modelo de Microsoft orientado a matemáticas y lógica, con capacidad moderada de generación de código.',
    'Microsoft model suited to mathematics and logical reasoning, with moderate code-generation ability.'],
  '最新の超小型Qwen 3.5。テスト・プロトタイプ向き。ツール対応。': [
    'Variante muy pequeña de Qwen 3.5 para pruebas y prototipos. Admite herramientas.',
    'Very small Qwen 3.5 variant for tests and prototypes. Supports tools.'],
  'Qwen 3.5小型。Vision対応。サイズの割に驚くほど有能。': [
    'Variante pequeña de Qwen 3.5, con visión y buena capacidad para su tamaño.',
    'Small Qwen 3.5 variant, with vision and strong ability for its size.'],
  '超小型。動作確認やドラフト生成向き。精度は限定的。': [
    'Modelo muy pequeño para pruebas de funcionamiento y borradores. Precisión limitada.',
    'Very small model for smoke tests and drafts. Limited accuracy.'],
  '小さいがツール呼び出し可能。簡単なタスクなら実用的。': [
    'Modelo pequeño con llamadas a herramientas, utilizable para tareas sencillas.',
    'Small model with tool calling, usable for simple tasks.'],
  'Microsoft小型推論モデル。数学・論理に特化。': [
    'Modelo pequeño de razonamiento de Microsoft, especializado en matemáticas y lógica.',
    'Small Microsoft reasoning model, focused on mathematics and logic.'],
  'Google最小モデル。超高速。精度は最低限。': [
    'Modelo mínimo de Google, muy rápido y con precisión básica.',
    'Minimal Google model, very fast with basic accuracy.'],
  'Meta最小。レスポンス速い。英語の簡単なタスク向き。': [
    'Modelo mínimo de Meta, rápido y orientado a tareas sencillas en inglés.',
    'Minimal Meta model, fast and suited to simple English tasks.'],
  '思考連鎖（CoT）推論の蒸留版。数学・論理問題に強い。': [
    'Variante destilada de razonamiento con cadena de pensamiento (CoT), orientada a matemáticas y lógica.',
    'Distilled chain-of-thought (CoT) reasoning variant, suited to mathematics and logic.'],
  'より深い推論。詳細な思考過程を表示。': [
    'Razonamiento más profundo, con exposición detallada del proceso de pensamiento.',
    'Deeper reasoning, with detailed thinking-process output.'],
  '高精度推論。複雑な数学・コーディング問題向き。24GB+ VRAM推奨。': [
    'Razonamiento preciso para problemas complejos de matemáticas y código. Se recomiendan 24 GB o más de VRAM.',
    'Accurate reasoning for complex mathematics and coding problems. 24 GB or more of VRAM recommended.'],
  'Qwen推論特化。長い思考連鎖で複雑な問題を解く。24GB+ VRAM推奨。': [
    'Qwen especializado en razonamiento prolongado para problemas complejos. Se recomiendan 24 GB o más de VRAM.',
    'Qwen specialized in extended reasoning for complex problems. 24 GB or more of VRAM recommended.'],
  'Cohere製多言語モデル。23言語対応。翻訳・多言語チャットに最適。': [
    'Modelo multilingüe de Cohere con 23 idiomas, orientado a traducción y conversación multilingüe.',
    'Multilingual Cohere model supporting 23 languages, suited to translation and multilingual chat.'],
  '大型多言語モデル。高品質な多言語生成。16GB+ VRAM推奨。': [
    'Modelo multilingüe grande, con generación de alta calidad. Se recomiendan 16 GB o más de VRAM.',
    'Large multilingual model, with high-quality generation. 16 GB or more of VRAM recommended.'],
  '国立情報学研究所（NII）開発。日本語特化。学術・ビジネス文書に強い。': [
    'Modelo del Instituto Nacional de Informática de Japón (NII), especializado en japonés y documentos académicos o empresariales.',
    'Model from Japan’s National Institute of Informatics (NII), focused on Japanese and academic or business documents.'],
  'ELYZA製日本語Llama 3。日本語NLPタスク全般に強い。実用的。': [
    'Llama 3 en japonés de ELYZA, orientado a tareas prácticas de procesamiento del lenguaje.',
    'Japanese Llama 3 from ELYZA, suited to practical natural-language processing tasks.'],
  'Liquid AI製日本語特化小型モデル。軽量で高速。簡単な日本語タスク向き。': [
    'Modelo pequeño y rápido de Liquid AI, especializado en tareas sencillas en japonés.',
    'Small, fast Liquid AI model, focused on simple Japanese tasks.'],
  'CyberAgent製。DeepSeek R1の日本語蒸留版。日本語での推論に強い。': [
    'Variante destilada en japonés de DeepSeek R1, de CyberAgent, orientada al razonamiento en japonés.',
    'CyberAgent’s Japanese distillation of DeepSeek R1, suited to Japanese reasoning.'],
  '富岳スパコンプロジェクト発。日本語命令チューニング済み。': [
    'Modelo del proyecto del supercomputador Fugaku, ajustado para instrucciones en japonés.',
    'Model from the Fugaku supercomputer project, instruction-tuned for Japanese.'],
  'Google Gemma 2日本語版。小型で高速。簡単な日本語会話向き。': [
    'Variante pequeña y rápida de Google Gemma 2 en japonés, para conversaciones sencillas.',
    'Small, fast Japanese Google Gemma 2 variant, for simple conversations.'],

  'エージェント': ['Agentes', 'Agents'], 'コード': ['Código', 'Code'],
  'コード生成': ['Generación de código', 'Code generation'], 'コード補完': ['Autocompletado de código', 'Code completion'],
  'ツール': ['Herramientas', 'Tools'], 'テスト用': ['Pruebas', 'Testing'],
  'デバッグ': ['Depuración', 'Debugging'], 'ビジネス': ['Empresa', 'Business'],
  'リファクタ': ['Refactorización', 'Refactoring'], '会話': ['Conversación', 'Conversation'],
  '多言語': ['Multilingüe', 'Multilingual'], '多言語対応': ['Soporte multilingüe', 'Multilingual support'],
  '学術': ['Académico', 'Academic'], '実用的': ['Uso práctico', 'Practical use'],
  '推論': ['Razonamiento', 'Reasoning'], '数学': ['Matemáticas', 'Mathematics'],
  '日本語': ['Japonés', 'Japanese'], '欧州言語': ['Idiomas europeos', 'European languages'],
  '汎用': ['General', 'General'], '翻訳': ['Traducción', 'Translation'],
  '補完': ['Autocompletado', 'Completion'], '複雑なロジック': ['Lógica compleja', 'Complex logic'],
  '詳細思考': ['Razonamiento detallado', 'Detailed reasoning'], '超軽量': ['Muy ligero', 'Very lightweight'],
  '軽量': ['Ligero', 'Lightweight'], '長考': ['Razonamiento prolongado', 'Extended reasoning'],
  '高品質翻訳': ['Traducción de alta calidad', 'High-quality translation'],
  '高精度推論': ['Razonamiento preciso', 'Accurate reasoning'], '高速': ['Rápido', 'Fast'],

  'Best quality. Vision + thinking + tools.': ['Alta calidad. Visión, razonamiento y herramientas.', 'Best quality. Vision + thinking + tools.'],
  'Strong reasoning. Great for agents.': ['Razonamiento sólido, orientado a agentes.', 'Strong reasoning. Great for agents.'],
  'Top-tier coding specialist.': ['Especialista avanzado en código.', 'Top-tier coding specialist.'],
  'Strong all-rounder for its size.': ['Modelo general capaz para su tamaño.', 'Strong all-rounder for its size.'],
  'Code specialist, great accuracy.': ['Especialista en código, con buena precisión.', 'Code specialist, great accuracy.'],
  'Balanced reasoning + tools.': ['Razonamiento equilibrado y herramientas.', 'Balanced reasoning + tools.'],
  'Good baseline with tool calling.': ['Opción base con llamadas a herramientas.', 'Good baseline with tool calling.'],
  'Compact code model.': ['Modelo compacto para código.', 'Compact code model.'],
  'Capable for its size.': ['Capaz para su tamaño.', 'Capable for its size.'],
  'Lightweight with tools.': ['Ligero, con herramientas.', 'Lightweight with tools.'],
  'Very compact, basic tasks.': ['Muy compacto, para tareas básicas.', 'Very compact, basic tasks.'],
  'Minimal. Testing only.': ['Mínimo. Sólo para pruebas.', 'Minimal. Testing only.'],
  'Locally installed model.': ['Modelo instalado localmente.', 'Locally installed model.'],
}

export function modelLibraryText(value: string, locale: 'es' | 'en'): string {
  const direct = Object.prototype.hasOwnProperty.call(ownText, value) ? ownText[value] : undefined
  if (direct) return direct[locale === 'es' ? 0 : 1]
  // Only the exact recommendation template plus a known built-in reason is
  // translated. New remote descriptions are never inferred or rewritten.
  const recommendation = /^Best for your (\d+)GB system\. (.+)$/.exec(value)
  if (recommendation && Object.prototype.hasOwnProperty.call(ownText, recommendation[2])) {
    return locale === 'es'
      ? `Opción recomendada para tu equipo de ${recommendation[1]} GB. ${ownText[recommendation[2]][0]}`
      : value
  }
  return value
}
