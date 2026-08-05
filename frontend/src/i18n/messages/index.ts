import { common, type Message } from "./common";
import { panels } from "./panels";
import { profiles } from "./profiles";

export type { Message };

/**
 * Все подписи интерфейса.
 *
 * Языки лежат рядом в одном объекте, а не по файлу на язык: так пропущенный
 * перевод виден при чтении словаря, а не только при сборке, и правка оригинала
 * не расходится с переводами по разным файлам. Все языки попадают в бандл —
 * это пара десятков килобайт, дешевле, чем догрузка словаря по сети на каждую
 * смену языка.
 */
export const messages = { ...common, ...panels, ...profiles };

export type MessageKey = keyof typeof messages;
