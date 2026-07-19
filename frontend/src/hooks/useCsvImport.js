// Импорт библиотеки из CSV (ревью 19.07 — вынесено из HomePage).
// Держит скрытый file-input, мутацию и текст отчёта об импорте.
import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";

export function useCsvImport() {
  const queryClient = useQueryClient();
  const inputRef = useRef(null);
  const [message, setMessage] = useState("");

  const mutation = useMutation({
    mutationFn: api.importCsv,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: keys.books });
      setMessage(
        `Импортировано: ${data.imported}, дубликаты: ${data.duplicates ?? 0}, ` +
          `пропущено: ${data.skipped}`,
      );
    },
  });

  function onFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    mutation.mutate(file);
    e.target.value = "";   // сбрасываем, чтобы тот же файл можно было выбрать снова
  }

  return {
    inputRef,
    onFileChange,
    trigger: () => inputRef.current?.click(),
    importing: mutation.isPending,
    message,
    error: mutation.isError ? mutation.error : null,
  };
}
