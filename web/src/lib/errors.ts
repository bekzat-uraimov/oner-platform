import { ApiError } from "./api/catalog";

// The API's error details are English and written for developers; these are what people see.
const KNOWN: Record<string, string> = {
  "Slug already in use": "Такой адрес курса уже занят.",
  "Course has been purchased; unpublish it instead": "Курс уже покупали. Снимите его с публикации вместо удаления.",
  "That would leave no active admin": "Нельзя оставить сайт без активного администратора.",
  "That upload is already recorded as a material": "Этот файл уже добавлен.",
  "storage_key must come from /admin/materials/upload-url": "Файл загружен не через админку.",
  "Video uploads are unavailable": "Kinescope не подключён на этом сервере.",
  "Uploads are unavailable": "Хранилище R2 не подключено на этом сервере.",
  "Storage is unavailable": "Хранилище R2 не подключено на этом сервере.",
  "Downloads are unavailable": "Скачивание временно недоступно.",
  "Kinescope did not respond": "Kinescope не ответил. Попробуйте позже.",
  "Storage did not respond": "Хранилище не ответило. Попробуйте позже.",
  "Payment gateway unavailable": "Оплата временно недоступна. Попробуйте позже.",
  "Course is not for sale": "Этот курс пока нельзя купить.",
  "You already own this course": "Этот курс уже у вас.",
  "You do not own this course": "Этот курс ещё не куплен.",
  "Lesson has no video yet": "У урока пока нет видео.",
  "No upload in progress": "Загрузки нет.",
  "That user doesn't own that course": "У пользователя нет этого курса.",
  "Admin access required": "Нужны права администратора.",
  "Account disabled": "Аккаунт отключён.",
  "Course not found": "Курс не найден.",
  "Lesson not found": "Урок не найден.",
  "User not found": "Пользователь не найден.",
  "Purchase not found": "Покупка не найдена.",
  "Material not found": "Материал не найден.",
};

export function errorText(error: ApiError): string {
  if (error.status === 0) return error.message;
  if (KNOWN[error.message]) return KNOWN[error.message];
  if (error.message.startsWith("Only a paid purchase can be refunded")) return "Вернуть можно только оплаченную покупку.";
  if (error.status === 422) return "Проверьте заполненные поля.";
  if (error.status === 429) return "Слишком много запросов. Подождите минуту.";
  if (error.status >= 500) return "Сервер ответил ошибкой. Попробуйте позже.";
  return error.message;
}

export function describe(error: unknown, fallback = "Что-то пошло не так. Попробуйте ещё раз."): string {
  if (error instanceof ApiError) return errorText(error);
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}
