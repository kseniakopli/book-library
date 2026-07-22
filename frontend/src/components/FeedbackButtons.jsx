// Кнопки 👍/👎 для AI-подборок (задача 26). Оценка копится у нас и потом
// пойдёт в промпт будущих генераций («профиль вкуса»), провайдерам не шлётся.
//
// ref — стабильный ключ цели ("atmosphere:5:music:Claude" / "recommendation:...").
// source (Claude/ChatGPT) — чтобы считать acceptance rate по провайдерам.
// Повторный клик по активной кнопке снимает оценку (toggle) — бэкенд так и делает.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";

function FeedbackButtons({ refKey, source }) {
  const queryClient = useQueryClient();

  // все оценки пользователя разом (один запрос на страницу) → состояние кнопок
  const { data } = useQuery({
    queryKey: keys.feedback,
    queryFn: api.getFeedback,
  });
  const current = data?.feedback?.[refKey] ?? null;

  const vote = useMutation({
    mutationFn: (verdict) => api.setFeedback({ ref: refKey, verdict, source }),
    onSuccess: (res) => {
      queryClient.setQueryData(keys.feedback, (prev) => {
        const map = { ...(prev?.feedback ?? {}) };
        if (res.verdict) map[refKey] = res.verdict;
        else delete map[refKey];
        return { feedback: map };
      });
    },
  });

  return (
    <div className="feedback" role="group" aria-label="Оценка подборки">
      <button
        type="button"
        className={"feedback-btn" + (current === "up" ? " active" : "")}
        onClick={() => vote.mutate("up")}
        disabled={vote.isPending}
        aria-pressed={current === "up"}
        aria-label="Понравилось"
        title="Понравилось"
      >
        👍
      </button>
      <button
        type="button"
        className={"feedback-btn" + (current === "down" ? " active" : "")}
        onClick={() => vote.mutate("down")}
        disabled={vote.isPending}
        aria-pressed={current === "down"}
        aria-label="Не понравилось"
        title="Не понравилось"
      >
        👎
      </button>
    </div>
  );
}

export default FeedbackButtons;
