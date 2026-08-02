import { crestAsset } from '../data/assets.js';

/**
 * TeamCrest — team logos in their own brand colour, never tinted.
 *
 * Unselected crests dim slightly rather than desaturating hard, so a team is
 * still recognisable by its colour while browsing.
 */
export default function TeamCrest({
  crestFile,
  name,
  size = 44,
  dim = false,
  eager = false,
  className = '',
}) {
  const url = crestAsset(crestFile);

  return (
    <span
      className={`inline-grid shrink-0 place-items-center ${className}`}
      style={{ width: `min(${size}px, 100%)`, aspectRatio: '1' }}
    >
      {url ? (
        <img
          src={url}
          alt={name ? `${name} crest` : ''}
          loading={eager ? 'eager' : 'lazy'}
          draggable={false}
          className="h-full w-full object-contain transition-opacity duration-fast"
          style={{ opacity: dim ? 0.45 : 1 }}
        />
      ) : (
        <span className="label">{name}</span>
      )}
    </span>
  );
}
