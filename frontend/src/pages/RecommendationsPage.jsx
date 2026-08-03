// Рекомендации отдельной страницей (задача 110).
//
// Раньше это была третья полка на главной. Уехала сюда по двум причинам:
// главная перегружена, а сами советы — не то, что смотрят при каждом заходе.
// ⚠ Первый заход даёт пустой экран с кнопкой генерации — принято осознанно
// (решение Ксении): подбор тратит токены, и запускать его автоматически
// при открытии страницы значит платить за каждый случайный клик по меню.
// Со временем страница обрастёт настройками пожеланий (задача 114).
import { Link } from "react-router-dom";
import RecommendationShelf from "../components/RecommendationShelf";

function RecommendationsPage() {
  return (
    <div className="recommendations-page">
      <Link className="btn-ghost" to="/">
        ← К библиотеке
      </Link>

      <p className="muted recommendations-lead">
        Советы новых книг по вашим оценкам от 7 и выше. Claude и ChatGPT
        предлагают по пять каждый, совпавшие книги схлопываются.
      </p>

      {/* на своей странице полка — главный блок, поэтому её заголовок h1 */}
      <RecommendationShelf heading="h1" />
    </div>
  );
}

export default RecommendationsPage;
