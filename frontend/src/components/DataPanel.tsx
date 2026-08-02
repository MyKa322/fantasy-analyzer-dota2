import { useState } from "react";
import { api } from "../api";
import { Button, Field, Notice, Panel, selectClass } from "./ui";

export default function DataPanel() {
  const [daysBack, setDaysBack] = useState(30);
  const [teamId, setTeamId] = useState("");
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const append = (line: string) =>
    setLog((current) => [`${new Date().toLocaleTimeString("ru")} — ${line}`, ...current]);

  const run = async (label: string, action: () => Promise<unknown>) => {
    setBusy(true);
    append(`${label}: старт`);
    try {
      const result = await action();
      append(`${label}: ${JSON.stringify(result)}`);
    } catch (e) {
      append(`${label}: ошибка — ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Panel
        title="Загрузка данных"
        subtitle="OpenDota без ключа: 60 запросов в минуту, 2000 в сутки. Тела матчей кэшируются на диск, повторный запуск лимит не тратит."
      >
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Глубина, дней">
            <select
              className={selectClass}
              value={daysBack}
              onChange={(e) => setDaysBack(Number(e.target.value))}
            >
              <option value={7}>7</option>
              <option value={30}>30</option>
              <option value={90}>90</option>
              <option value={180}>180</option>
            </select>
          </Field>
          <Button
            onClick={() => run("Лента про-матчей", () => api.ingestProFeed(daysBack, 10))}
            disabled={busy}
          >
            Загрузить про-матчи
          </Button>
          <Button
            variant="ghost"
            onClick={() => run("Сопоставление команд TI15", () => api.resolveTeams())}
            disabled={busy}
          >
            Сопоставить участников TI15
          </Button>
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-3">
          <Field label="ID команды" hint="OpenDota team_id — берётся из сопоставления выше">
            <input
              className={selectClass}
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              placeholder="например 2163"
            />
          </Field>
          <Button
            variant="ghost"
            onClick={() =>
              run(`История команды ${teamId}`, () =>
                api.ingestTeam(Number(teamId), Math.max(daysBack, 120)),
              )
            }
            disabled={busy || !teamId}
          >
            Загрузить историю команды
          </Button>
        </div>

        <div className="mt-4">
          <Notice kind="warn">
            Для проекций Fantasy годятся только матчи с разобранным реплеем — в
            остальных нет вардов, станов и участия в файтах. В ответе это поле
            <code className="mx-1 text-neutral-300">unparsed</code>.
          </Notice>
        </div>
      </Panel>

      <Panel title="Журнал">
        {log.length === 0 ? (
          <p className="text-sm text-neutral-500">Пока пусто</p>
        ) : (
          <pre className="max-h-80 overflow-y-auto text-xs whitespace-pre-wrap text-neutral-300">
            {log.join("\n")}
          </pre>
        )}
      </Panel>
    </div>
  );
}
