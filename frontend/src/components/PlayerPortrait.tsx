import { useState } from "react";
import { playerPortrait } from "../assets";

/**
 * Портрет игрока. Файл берётся из манифеста по нормализованному нику; если
 * сопоставления нет — показываем инициалы, а не битую картинку.
 */
export default function PlayerPortrait({
  teamName,
  nickname,
  size = 44,
}: {
  teamName: string | null | undefined;
  nickname: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  const src = playerPortrait(teamName, nickname);

  if (!src || failed) {
    return (
      <div
        className="flex shrink-0 items-center justify-center rounded-full border border-[#2C3138] bg-[#1C1F24] text-[11px] text-neutral-400"
        style={{ width: size, height: size }}
        title={nickname}
      >
        {nickname.slice(0, 2)}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={nickname}
      title={nickname}
      onError={() => setFailed(true)}
      className="shrink-0 rounded-full border border-[#2C3138] bg-[#1C1F24] object-cover object-top"
      style={{ width: size, height: size }}
    />
  );
}
