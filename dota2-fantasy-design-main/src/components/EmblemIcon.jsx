import { emblemAsset } from '../data/assets.js';

/**
 * EmblemIcon — the fantasy_craft artwork, shown as artwork.
 *
 * These files are opaque 128px greyscale tiles with real illustration in them
 * (Roshan's face, an eye with radiating rays, bursting coins). An earlier
 * version used them as CSS masks with a flat tint, which reduced every one of
 * them to a solid-colour silhouette and threw the art away.
 *
 * So: rendered as an <img>, never tinted, never masked. Group colour lives on
 * the ring around the tile — that keeps the icon swappable to any design while
 * the colour stays fixed to the slot.
 */
export default function EmblemIcon({
  asset,
  size = 'var(--icon-tile)',
  label,
  ring = true,
  className = '',
}) {
  const url = emblemAsset(asset);

  return (
    <span
      className={`relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-sm ${className}`}
      style={{
        width: size,
        height: size,
        background: 'var(--n-950)',
        // The ring is the only thing carrying group colour. Inset so it reads
        // as a frame rather than a border that changes the tile's footprint.
        boxShadow: ring ? 'inset 0 0 0 1px var(--group-line, var(--color-border))' : 'none',
      }}
    >
      {url ? (
        <img
          src={url}
          alt={label ? `${label} emblem` : ''}
          aria-hidden={label ? undefined : 'true'}
          draggable={false}
          className="h-full w-full object-cover"
          style={{ imageRendering: 'auto' }}
        />
      ) : (
        <span className="label" style={{ fontSize: 9 }}>?</span>
      )}
    </span>
  );
}
