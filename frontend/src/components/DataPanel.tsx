import { useState } from "react";
import { api } from "../api";
import { useT } from "../i18n";
import { Button, Field, Notice, Panel, selectClass } from "./ui";

export default function DataPanel() {
  const { t, locale } = useT();
  const [daysBack, setDaysBack] = useState(30);
  const [teamId, setTeamId] = useState("");
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const append = (line: string) =>
    setLog((current) => [
      `${new Date().toLocaleTimeString(locale)} — ${line}`,
      ...current,
    ]);

  const run = async (label: string, action: () => Promise<unknown>) => {
    setBusy(true);
    append(t("data.started", { label }));
    try {
      const result = await action();
      append(`${label}: ${JSON.stringify(result)}`);
    } catch (e) {
      append(t("data.failed", { label, message: (e as Error).message }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Panel title={t("data.title")} subtitle={t("data.subtitle")}>
        <div className="flex flex-wrap items-end gap-3">
          <Field label={t("data.days")}>
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
            onClick={() =>
              run(t("data.proFeedLabel"), () => api.ingestProFeed(daysBack, 10))
            }
            disabled={busy}
          >
            {t("data.proFeed")}
          </Button>
          <Button
            variant="ghost"
            onClick={() => run(t("data.resolveLabel"), () => api.resolveTeams())}
            disabled={busy}
          >
            {t("data.resolve")}
          </Button>
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-3">
          <Field label={t("data.teamId")} hint={t("data.teamIdHint")}>
            <input
              className={selectClass}
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              placeholder={t("data.teamIdPlaceholder")}
            />
          </Field>
          <Button
            variant="ghost"
            onClick={() =>
              run(t("data.teamHistoryLabel", { id: teamId }), () =>
                api.ingestTeam(Number(teamId), Math.max(daysBack, 120)),
              )
            }
            disabled={busy || !teamId}
          >
            {t("data.loadTeam")}
          </Button>
        </div>

        <div className="mt-4">
          <Notice kind="warn">
            {t("data.parsedWarning")}
            <code className="mx-1 text-neutral-300">unparsed</code>.
          </Notice>
        </div>
      </Panel>

      <Panel title={t("data.log")}>
        {log.length === 0 ? (
          <p className="text-sm text-neutral-500">{t("data.logEmpty")}</p>
        ) : (
          <pre className="max-h-80 overflow-y-auto text-xs whitespace-pre-wrap text-neutral-300">
            {log.join("\n")}
          </pre>
        )}
      </Panel>
    </div>
  );
}
