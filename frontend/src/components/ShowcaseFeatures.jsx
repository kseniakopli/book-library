// Блок «что умеет сервис» на публичной витрине (28.07).
//
// Тексты перенесены с лендинга (landing/index.html) — там они уже отобраны
// и выверены. Дублирование сознательное: лендинг живёт отдельным статическим
// файлом без сборки, тянуть его содержимое в SPA неоткуда. Меняешь здесь —
// проверь, не разошлось ли с лендингом.
//
// Порядок выбран Ксенией: сначала то, что гость только что видел на карточках
// книги (музыка, угощения), потом бумажная карточка, которая привела его сюда,
// и лишь затем «заведи свою библиотеку».
const FEATURES = [
  {
    title: "Музыка вечера",
    text: "Плейлист под конкретную книгу — каждый трек с пояснением, почему он подходит. Одной кнопкой собирается в Spotify.",
  },
  {
    title: "Угощения и ароматы",
    text: "Что заварить и чем наполнить комнату, чтобы совпало с текстом: от глинтвейна под скандинавский нуар до сандала под японскую прозу.",
  },
  {
    title: "Печатная карточка",
    text: "Карточка с символом книги, треками и QR на плейлист — вложить в книгу, которую даришь или отдаёшь почитать.",
  },
  {
    title: "Ваша библиотека",
    text: "Статусы и оценки, импорт из CSV, обложки и метаданные подтягиваются сами.",
  },
];

function ShowcaseFeatures() {
  return (
    <section className="showcase-features" aria-labelledby="features-heading">
      <h2 className="showcase-section-title" id="features-heading">
        Что такое nocturne
      </h2>
      <ul className="showcase-feature-grid">
        {FEATURES.map((feature) => (
          <li className="showcase-feature" key={feature.title}>
            <h3 className="showcase-feature-title">{feature.title}</h3>
            <p className="showcase-feature-text">{feature.text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default ShowcaseFeatures;
